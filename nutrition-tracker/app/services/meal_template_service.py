from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import MealTemplate
from app.db.repositories.conversation_states import ConversationStateRepository
from app.db.repositories.food_logs import FoodLogItemRepository, FoodLogRepository
from app.db.repositories.meal_templates import MealTemplateRepository
from app.schemas.bot_responses import BotResponse, Decision, LoggedItemSummary
from app.services.audit_service import AuditService


def log_template(template_id: uuid.UUID, user_id: uuid.UUID, db: Session) -> BotResponse:
    template = db.get(MealTemplate, template_id)
    if not template or template.user_id != user_id:
        return BotResponse(text="Standardmahlzeit nicht gefunden.")

    log = FoodLogRepository(db).create(
        user_id=user_id,
        raw_text=f"template:{template.template_name}",
        source="template",
        meal_type="unknown",
        total_kcal=float(template.total_kcal or 0),
        total_protein=float(template.total_protein or 0),
        total_carbs=float(template.total_carbs or 0),
        total_fat=float(template.total_fat or 0),
        confidence=0.95,
        status="saved",
    )
    item_repo = FoodLogItemRepository(db)
    logged_items: list[LoggedItemSummary] = []
    for item in template.items:
        item_repo.create(
            food_log_id=log.id,
            original_name=item.original_name,
            canonical_name=item.canonical_name,
            quantity=float(item.quantity) if item.quantity is not None else None,
            unit=item.unit,
            grams=float(item.grams) if item.grams is not None else None,
            kcal=float(item.kcal) if item.kcal is not None else None,
            protein=float(item.protein) if item.protein is not None else None,
            carbs=float(item.carbs) if item.carbs is not None else None,
            fat=float(item.fat) if item.fat is not None else None,
            source=item.source,
            source_id=item.source_id,
            confidence=float(item.confidence) if item.confidence is not None else None,
            was_estimated=item.was_estimated,
        )
        logged_items.append(
            LoggedItemSummary(
                name=item.canonical_name or item.original_name or template.template_name,
                grams=float(item.grams) if item.grams is not None else None,
                kcal=float(item.kcal) if item.kcal is not None else None,
                was_estimated=item.was_estimated,
            )
        )

    AuditService(db).log(
        event_type="meal_template_logged",
        user_id=user_id,
        payload={"template_id": str(template_id), "food_log_id": str(log.id), "items": len(logged_items)},
    )
    return BotResponse(
        text=(
            f"Gespeichert\n\n{template.template_name}\n\n"
            f"Gesamt: {float(template.total_kcal or 0):.0f} kcal"
        ),
        decision=Decision(action="direct_save", confidence=0.95, reason="template"),
        logged_items=logged_items,
    )


def prompt_save_template_name(food_log_id: uuid.UUID, user_id: uuid.UUID, db: Session) -> BotResponse:
    log = FoodLogRepository(db).get_by_id(food_log_id)
    if not log or log.user_id != user_id or log.status != "saved":
        return BotResponse(text="Diesen Eintrag kann ich nicht als Standardmahlzeit speichern.")

    ConversationStateRepository(db).delete_for_user(user_id)
    ConversationStateRepository(db).create(
        user_id=user_id,
        state_type="save_template_name",
        payload={"food_log_id": str(food_log_id)},
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    AuditService(db).log(
        event_type="meal_template_name_requested",
        user_id=user_id,
        payload={"food_log_id": str(food_log_id)},
    )
    return BotResponse(text="Wie soll die Standardmahlzeit heißen?")


def resolve_template_name(text: str, user_id: uuid.UUID, db: Session) -> BotResponse | None:
    state_repo = ConversationStateRepository(db)
    state = state_repo.get_active_for_user(user_id)
    if not state or state.state_type != "save_template_name":
        return None

    name = " ".join(text.strip().split())
    if not name:
        return BotResponse(text="Bitte sende mir einen Namen für die Standardmahlzeit.")

    state_repo.delete_for_user(user_id)
    template = save_as_template(uuid.UUID(state.payload["food_log_id"]), name, user_id, db)
    if template is None:
        return BotResponse(text="Diesen Eintrag konnte ich nicht als Standardmahlzeit speichern.")
    return BotResponse(text=f"Gespeichert als Standardmahlzeit: {template.template_name}")


def save_as_template(food_log_id: uuid.UUID, name: str, user_id: uuid.UUID, db: Session) -> MealTemplate | None:
    log = FoodLogRepository(db).get_by_id(food_log_id)
    if not log or log.user_id != user_id:
        return None

    repo = MealTemplateRepository(db)
    existing = repo.get_by_name(user_id, name)
    if existing:
        existing.total_kcal = log.total_kcal
        existing.total_protein = log.total_protein
        existing.total_carbs = log.total_carbs
        existing.total_fat = log.total_fat
        db.commit()
        db.refresh(existing)
        template = existing
    else:
        template = repo.create(
            user_id=user_id,
            template_name=name,
            total_kcal=float(log.total_kcal or 0),
            total_protein=float(log.total_protein or 0),
            total_carbs=float(log.total_carbs or 0),
            total_fat=float(log.total_fat or 0),
        )

    item_repo = FoodLogItemRepository(db)
    template_items = []
    for item in item_repo.get_for_log(log.id):
        template_items.append(
            {
                "original_name": item.original_name,
                "canonical_name": item.canonical_name,
                "quantity": float(item.quantity) if item.quantity is not None else None,
                "unit": item.unit,
                "grams": float(item.grams) if item.grams is not None else None,
                "kcal": float(item.kcal) if item.kcal is not None else None,
                "protein": float(item.protein) if item.protein is not None else None,
                "carbs": float(item.carbs) if item.carbs is not None else None,
                "fat": float(item.fat) if item.fat is not None else None,
                "source": item.source,
                "source_id": item.source_id,
                "confidence": float(item.confidence) if item.confidence is not None else None,
                "was_estimated": item.was_estimated,
            }
        )
    repo.replace_items(template, template_items)

    AuditService(db).log(
        event_type="meal_template_saved",
        user_id=user_id,
        payload={
            "template_id": str(template.id),
            "food_log_id": str(food_log_id),
            "name": name,
            "items": len(template_items),
        },
    )
    return template
