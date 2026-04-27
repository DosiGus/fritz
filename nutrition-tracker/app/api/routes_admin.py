from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.repositories.users import UserRepository
from app.db.repositories.food_logs import FoodLogRepository
from app.db.repositories.nutrition_items import NutritionItemRepository, FoodAliasRepository
from app.db.repositories.audit_events import AuditEventRepository
from app.db.session import get_db

router = APIRouter(tags=["admin"])


@router.get("/stats")
def admin_stats(db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    log_repo = FoodLogRepository(db)
    audit_repo = AuditEventRepository(db)

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    return {
        "total_users": user_repo.count(),
        "logs_today": log_repo.count_today(),
        "audit_events_today": audit_repo.count_since(today_start),
    }


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
        items = db.query(__import__("app.db.models", fromlist=["NutritionItem"]).NutritionItem).limit(limit).all()
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
    from app.db.models import AuditEvent

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
