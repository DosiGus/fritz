from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

import sentry_sdk
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import (
    ApiRequestLog,
    AuditEvent,
    ConversationState,
    FoodAlias,
    FoodLog,
    FoodLogItem,
    MealTemplate,
    MealTemplateItem,
    NutritionItem,
    PortionRule,
    User,
    UserGoal,
    UserPortionMemory,
)
from app.db.repositories.audit_events import AuditEventRepository
from app.db.repositories.food_logs import FoodLogRepository
from app.db.repositories.nutrition_items import FoodAliasRepository, NutritionItemRepository
from app.db.repositories.portions import PortionRuleRepository
from app.db.repositories.users import UserRepository
from app.db.session import get_db


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=503, detail="Admin API is disabled until ADMIN_TOKEN is configured.")
    if not x_admin_token or not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(status_code=401, detail="Invalid admin token.")


router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today_start() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Overview / Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
def admin_stats(db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    log_repo = FoodLogRepository(db)
    audit_repo = AuditEventRepository(db)

    today = _today_start()

    return {
        "total_users": user_repo.count(),
        "logs_today": log_repo.count_today(),
        "audit_events_today": audit_repo.count_since(today),
    }


@router.post("/sentry-test")
def admin_sentry_test(db: Session = Depends(get_db)):
    if not settings.sentry_dsn:
        raise HTTPException(status_code=503, detail="SENTRY_DSN is not configured.")

    event_id = sentry_sdk.capture_message("admin_sentry_test", level="warning")
    _audit_admin_action(db, "sentry_test_sent", {"sentry_event_id": event_id})
    return {"sent": True, "event_id": event_id}


@router.get("/metrics")
def admin_metrics(db: Session = Depends(get_db)):
    """Aggregated operational metrics for the Admin Dashboard."""
    today = _today_start()

    # --- failed logs (status = 'failed' OR 'deleted') ---
    failed_logs = (
        db.query(FoodLog)
        .filter(FoodLog.status.in_(["failed", "deleted"]))
        .count()
    )

    # --- pending reviews (status = 'pending_confirmation') ---
    pending_reviews = (
        db.query(FoodLog)
        .filter(FoodLog.status == "pending_confirmation")
        .count()
    )

    # --- nutrition_match_failed events today ---
    nutrition_match_failed = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.event_type == "nutrition_match_failed",
            AuditEvent.created_at >= today,
        )
        .count()
    )
    nutrition_reviews_total = db.query(AuditEvent).filter(AuditEvent.event_type == "nutrition_review_needed").count()
    nutrition_reviews_resolved = len(_resolved_review_ids(db))
    nutrition_reviews_open = max(nutrition_reviews_total - nutrition_reviews_resolved, 0)

    # --- API errors today ---
    api_errors = (
        db.query(ApiRequestLog)
        .filter(
            ApiRequestLog.success == False,  # noqa: E712
            ApiRequestLog.created_at >= today,
        )
        .count()
    )

    # --- LLM errors today ---
    llm_errors = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.event_type.in_(["llm_error", "llm_timeout", "llm_parse_error"]),
            AuditEvent.created_at >= today,
        )
        .count()
    )

    # --- Voice errors today ---
    voice_errors = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.event_type.in_(
                ["voice_download_failed", "voice_transcription_empty", "transcription_error", "voice_error"]
            ),
            AuditEvent.created_at >= today,
        )
        .count()
    )

    # --- Clarification abort rate ---
    clarification_asked = (
        db.query(AuditEvent)
        .filter(AuditEvent.event_type == "clarification_asked")
        .count()
    )
    clarification_resolved = (
        db.query(AuditEvent)
        .filter(AuditEvent.event_type == "clarification_resolved")
        .count()
    )
    clarification_open = max(clarification_asked - clarification_resolved, 0)
    clarification_abort_rate = (
        round(clarification_open / clarification_asked, 3)
        if clarification_asked > 0
        else None
    )

    return {
        "failed_logs": failed_logs,
        "pending_reviews": pending_reviews,
        "nutrition_match_failed_today": nutrition_match_failed,
        "nutrition_reviews_open": nutrition_reviews_open,
        "nutrition_reviews_resolved": nutrition_reviews_resolved,
        "api_errors_today": api_errors,
        "llm_errors_today": llm_errors,
        "voice_errors_today": voice_errors,
        "clarification_asked_total": clarification_asked,
        "clarification_resolved_total": clarification_resolved,
        "clarification_open_total": clarification_open,
        "clarification_abort_rate": clarification_abort_rate,
    }


# ---------------------------------------------------------------------------
# Top Foods
# ---------------------------------------------------------------------------

@router.get("/top-foods")
def admin_top_foods(limit: int = 20, db: Session = Depends(get_db)):
    """Most logged foods by canonical name."""
    rows = (
        db.query(FoodLogItem.canonical_name, func.count(FoodLogItem.id).label("count"))
        .filter(FoodLogItem.canonical_name.isnot(None))
        .group_by(FoodLogItem.canonical_name)
        .order_by(func.count(FoodLogItem.id).desc())
        .limit(limit)
        .all()
    )
    return [{"canonical_name": r.canonical_name, "count": r.count} for r in rows]


@router.get("/unknown-foods")
def admin_unknown_foods(limit: int = 20, db: Session = Depends(get_db)):
    """Most frequent unknown / unmatched food names from audit events."""
    food_name = AuditEvent.payload["normalized"].as_string()
    rows = (
        db.query(
            food_name.label("food_name"),
            func.count(AuditEvent.id).label("count"),
        )
        .filter(AuditEvent.event_type == "nutrition_match_failed")
        .filter(food_name.isnot(None))
        .group_by(food_name)
        .order_by(func.count(AuditEvent.id).desc())
        .limit(limit)
        .all()
    )
    return [{"food_name": r.food_name, "count": r.count} for r in rows]


# ---------------------------------------------------------------------------
# Failed Logs
# ---------------------------------------------------------------------------

@router.get("/failed-logs")
def admin_failed_logs(limit: int = 50, db: Session = Depends(get_db)):
    logs = (
        db.query(FoodLog)
        .filter(FoodLog.status.in_(["failed", "pending_confirmation"]))
        .order_by(FoodLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(log.id),
            "user_id": str(log.user_id),
            "raw_text": log.raw_text,
            "source": log.source,
            "status": log.status,
            "confidence": float(log.confidence) if log.confidence else None,
            "logged_at": log.logged_at.isoformat(),
        }
        for log in logs
    ]


@router.get("/api-errors")
def admin_api_errors(limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.query(ApiRequestLog)
        .filter(ApiRequestLog.success == False)  # noqa: E712
        .order_by(ApiRequestLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(row.id),
            "service": row.service,
            "endpoint": row.endpoint,
            "method": row.method,
            "status_code": row.status_code,
            "error": row.error,
            "duration_ms": float(row.duration_ms) if row.duration_ms is not None else None,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/llm-errors")
def admin_llm_errors(limit: int = 50, db: Session = Depends(get_db)):
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.event_type.in_(["llm_error", "llm_timeout", "llm_parse_error"]))
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_audit_event_response(event) for event in events]


@router.get("/voice-errors")
def admin_voice_errors(limit: int = 50, db: Session = Depends(get_db)):
    events = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.event_type.in_(
                ["voice_download_failed", "voice_transcription_empty", "transcription_error", "voice_error"]
            )
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_audit_event_response(event) for event in events]


@router.get("/nutrition-reviews")
def admin_nutrition_reviews(include_resolved: bool = False, limit: int = 50, db: Session = Depends(get_db)):
    review_events = (
        db.query(AuditEvent)
        .filter(AuditEvent.event_type == "nutrition_review_needed")
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    resolved_ids = _resolved_review_ids(db)
    rows = []
    for event in review_events:
        resolved = str(event.id) in resolved_ids
        if resolved and not include_resolved:
            continue
        item = _audit_event_response(event)
        item["resolved"] = resolved
        rows.append(item)
    return rows


# ---------------------------------------------------------------------------
# Existing list endpoints
# ---------------------------------------------------------------------------

@router.get("/users")
def admin_list_users(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    users = repo.list_all(limit=limit, offset=offset)
    return [
        {
            "id": str(u.id),
            "telegram_user_id": u.telegram_user_id,
            "username": u.username,
            "first_name": u.first_name,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.get("/nutrition-items")
def admin_list_nutrition_items(verified: bool | None = None, limit: int = 50, db: Session = Depends(get_db)):
    repo = NutritionItemRepository(db)
    if verified is False:
        items = repo.list_unverified(limit=limit)
    else:
        items = db.query(NutritionItem).limit(limit).all()
    return [
        {
            "id": str(i.id),
            "canonical_name": i.canonical_name,
            "kcal_100g": float(i.kcal_100g) if i.kcal_100g else None,
            "source": i.source,
            "verified": i.verified,
        }
        for i in items
    ]


@router.get("/food-aliases")
def admin_list_food_aliases(db: Session = Depends(get_db)):
    repo = FoodAliasRepository(db)
    aliases = repo.list_all()
    return [
        {
            "id": str(a.id),
            "alias": a.alias,
            "canonical_name": a.canonical_name,
            "language": a.language,
            "confidence": float(a.confidence),
        }
        for a in aliases
    ]


@router.get("/audit-events")
def admin_list_audit_events(event_type: str | None = None, limit: int = 100, db: Session = Depends(get_db)):
    q = db.query(AuditEvent).order_by(AuditEvent.created_at.desc())
    if event_type:
        q = q.filter(AuditEvent.event_type == event_type)
    events = q.limit(limit).all()
    return [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "user_id": str(e.user_id) if e.user_id else None,
            "payload": e.payload,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


# ---------------------------------------------------------------------------
# Action: Add Food Alias
# ---------------------------------------------------------------------------

class AddFoodAliasRequest(BaseModel):
    alias: str
    canonical_name: str
    language: str = "de"
    confidence: float = 0.8


@router.post("/food-aliases")
def admin_add_food_alias(body: AddFoodAliasRequest, db: Session = Depends(get_db)):
    repo = FoodAliasRepository(db)
    existing = repo.get_by_alias(body.alias, body.language)
    if existing:
        raise HTTPException(status_code=409, detail="Alias already exists for this language.")
    alias = repo.create(
        alias=body.alias,
        canonical_name=body.canonical_name,
        language=body.language,
        confidence=body.confidence,
    )
    _audit_admin_action(
        db,
        "food_alias_created",
        {
            "alias_id": str(alias.id),
            "alias": alias.alias,
            "canonical_name": alias.canonical_name,
            "language": alias.language,
            "confidence": float(alias.confidence),
        },
    )
    return {"id": str(alias.id), "alias": alias.alias, "canonical_name": alias.canonical_name}


# ---------------------------------------------------------------------------
# Action: Add Portion Rule
# ---------------------------------------------------------------------------

class AddPortionRuleRequest(BaseModel):
    food_name: str | None = None
    food_category: str | None = None
    unit_text: str
    default_grams: float | None = None
    min_grams: float | None = None
    max_grams: float | None = None
    default_kcal: float | None = None
    country: str = "DE"
    confidence: float = 0.7
    source: str | None = None


class ResolveNutritionReviewRequest(BaseModel):
    resolution: str = "resolved"
    note: str | None = None
    canonical_name: str | None = None
    alias: str | None = None
    kcal_100g: float | None = None
    protein_100g: float | None = None
    carbs_100g: float | None = None
    fat_100g: float | None = None


def _audit_admin_action(db: Session, action: str, payload: dict) -> None:
    AuditEventRepository(db).create(
        event_type="admin_action",
        payload={"action": action, **payload},
    )


def _audit_event_response(event: AuditEvent) -> dict:
    return {
        "id": str(event.id),
        "event_type": event.event_type,
        "user_id": str(event.user_id) if event.user_id else None,
        "payload": event.payload,
        "created_at": event.created_at.isoformat(),
    }


def _resolved_review_ids(db: Session) -> set[str]:
    events = db.query(AuditEvent).filter(AuditEvent.event_type == "nutrition_review_resolved").all()
    return {
        str((event.payload or {}).get("review_event_id"))
        for event in events
        if (event.payload or {}).get("review_event_id")
    }


@router.post("/portion-rules")
def admin_add_portion_rule(body: AddPortionRuleRequest, db: Session = Depends(get_db)):
    repo = PortionRuleRepository(db)
    rule = repo.create(
        unit_text=body.unit_text,
        food_name=body.food_name,
        food_category=body.food_category,
        default_grams=body.default_grams,
        min_grams=body.min_grams,
        max_grams=body.max_grams,
        default_kcal=body.default_kcal,
        country=body.country,
        confidence=body.confidence,
        source=body.source,
    )
    _audit_admin_action(
        db,
        "portion_rule_created",
        {
            "portion_rule_id": str(rule.id),
            "food_name": rule.food_name,
            "unit_text": rule.unit_text,
            "default_grams": float(rule.default_grams) if rule.default_grams else None,
            "default_kcal": float(rule.default_kcal) if rule.default_kcal else None,
        },
    )
    return {
        "id": str(rule.id),
        "food_name": rule.food_name,
        "unit_text": rule.unit_text,
        "default_grams": float(rule.default_grams) if rule.default_grams else None,
        "default_kcal": float(rule.default_kcal) if rule.default_kcal else None,
    }


# ---------------------------------------------------------------------------
# Action: Verify Nutrition Item
# ---------------------------------------------------------------------------

@router.post("/nutrition-items/{item_id}/verify")
def admin_verify_nutrition_item(item_id: str, db: Session = Depends(get_db)):
    repo = NutritionItemRepository(db)
    try:
        uid = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID.")
    item = db.query(NutritionItem).filter(NutritionItem.id == uid).first()
    if not item:
        raise HTTPException(status_code=404, detail="Nutrition item not found.")
    repo.verify(item)
    _audit_admin_action(
        db,
        "nutrition_item_verified",
        {"nutrition_item_id": str(item.id), "canonical_name": item.canonical_name},
    )
    return {"id": item_id, "canonical_name": item.canonical_name, "verified": True}


@router.post("/nutrition-reviews/{event_id}/resolve")
def admin_resolve_nutrition_review(
    event_id: str,
    body: ResolveNutritionReviewRequest,
    db: Session = Depends(get_db),
):
    try:
        uid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID.")

    review = db.query(AuditEvent).filter(AuditEvent.id == uid, AuditEvent.event_type == "nutrition_review_needed").first()
    if not review:
        raise HTTPException(status_code=404, detail="Nutrition review not found.")

    created_item = None
    if body.canonical_name and body.kcal_100g is not None:
        created_item = NutritionItemRepository(db).create(
            canonical_name=body.canonical_name,
            kcal_100g=body.kcal_100g,
            protein_100g=body.protein_100g,
            carbs_100g=body.carbs_100g,
            fat_100g=body.fat_100g,
            source="admin",
            source_id=str(review.id),
            verified=True,
        )

    created_alias = None
    alias = body.alias or _alias_from_review(review)
    if alias and body.canonical_name:
        existing = FoodAliasRepository(db).get_by_alias(alias)
        if existing is None:
            created_alias = FoodAliasRepository(db).create(
                alias=alias,
                canonical_name=body.canonical_name,
                language="de",
                confidence=0.95,
            )

    payload = {
        "review_event_id": str(review.id),
        "resolution": body.resolution,
        "note": body.note,
        "canonical_name": body.canonical_name,
        "alias": alias,
        "nutrition_item_id": str(created_item.id) if created_item else None,
        "food_alias_id": str(created_alias.id) if created_alias else None,
    }
    AuditEventRepository(db).create(event_type="nutrition_review_resolved", payload=payload)
    _audit_admin_action(db, "nutrition_review_resolved", payload)

    return {
        "review_event_id": str(review.id),
        "resolved": True,
        "nutrition_item_id": str(created_item.id) if created_item else None,
        "food_alias_id": str(created_alias.id) if created_alias else None,
    }


def _alias_from_review(review: AuditEvent) -> str | None:
    payload = review.payload or {}
    items = payload.get("items") or []
    if items:
        return str(items[0]).strip().lower()
    raw_text = str(payload.get("raw_text") or "").strip().lower()
    return raw_text or None


# ---------------------------------------------------------------------------
# Database Browser
# ---------------------------------------------------------------------------

DB_TABLE_REGISTRY: dict[str, type] = {
    "users": User,
    "user_goals": UserGoal,
    "food_logs": FoodLog,
    "food_log_items": FoodLogItem,
    "nutrition_items": NutritionItem,
    "food_aliases": FoodAlias,
    "portion_rules": PortionRule,
    "user_portion_memory": UserPortionMemory,
    "meal_templates": MealTemplate,
    "meal_template_items": MealTemplateItem,
    "conversation_states": ConversationState,
    "audit_events": AuditEvent,
    "api_request_logs": ApiRequestLog,
}


@router.get("/db/tables")
def admin_db_tables(db: Session = Depends(get_db)):
    """List all known tables with their row counts."""
    out = []
    for name, model in DB_TABLE_REGISTRY.items():
        try:
            count = db.query(model).count()
        except Exception:
            count = None
        out.append({"name": name, "count": count})
    return out


@router.get("/db/{table_name}")
def admin_db_table(
    table_name: str,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Paginated rows from a whitelisted table, ordered by created_at desc when available."""
    model = DB_TABLE_REGISTRY.get(table_name)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Unknown table '{table_name}'.")

    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    columns = [c.name for c in model.__table__.columns]
    order_col = getattr(model, "created_at", None)
    if order_col is None:
        order_col = list(model.__table__.primary_key.columns)[0]

    rows = (
        db.query(model)
        .order_by(order_col.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    total = db.query(model).count()

    serialized = []
    for row in rows:
        serialized.append({col: jsonable_encoder(getattr(row, col)) for col in columns})

    return {
        "table": table_name,
        "columns": columns,
        "rows": serialized,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------------------------
# Dashboard UI (public — page is unauthenticated, but every API call from
# the page sends the X-Admin-Token header and hits the protected endpoints)
# ---------------------------------------------------------------------------

public_router = APIRouter(tags=["admin-ui"])

_DASHBOARD_HTML_PATH = Path(__file__).resolve().parent.parent / "static" / "admin_dashboard.html"


@public_router.get("/admin/dashboard", response_class=HTMLResponse)
def admin_dashboard():
    if not _DASHBOARD_HTML_PATH.exists():
        raise HTTPException(status_code=500, detail="Dashboard HTML missing.")
    return HTMLResponse(_DASHBOARD_HTML_PATH.read_text(encoding="utf-8"))
