from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.repositories.food_logs import FoodLogRepository
from app.db.repositories.meal_templates import MealTemplateRepository
from app.schemas.bot_responses import BotResponse, Decision
from app.services.audit_service import AuditService


def log_template(template_id: uuid.UUID, user_id: uuid.UUID, db: Session) -> BotResponse:
    template = db.get(__import__("app.db.models", fromlist=["MealTemplate"]).MealTemplate, template_id)
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
    AuditService(db).log(
        event_type="meal_template_logged",
        user_id=user_id,
        payload={"template_id": str(template_id), "food_log_id": str(log.id)},
    )
    return BotResponse(
        text=(
            f"Gespeichert\n\n{template.template_name}\n\n"
            f"Gesamt: {float(template.total_kcal or 0):.0f} kcal"
        ),
        decision=Decision(action="direct_save", confidence=0.95, reason="template"),
    )


def save_as_template(food_log_id: uuid.UUID, name: str, user_id: uuid.UUID, db: Session) -> None:
    log = FoodLogRepository(db).get_by_id(food_log_id)
    if not log or log.user_id != user_id:
        return

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

    AuditService(db).log(
        event_type="meal_template_saved",
        user_id=user_id,
        payload={"template_id": str(template.id), "food_log_id": str(food_log_id), "name": name},
    )
