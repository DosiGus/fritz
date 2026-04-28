from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.repositories.conversation_states import ConversationStateRepository
from app.db.repositories.food_logs import FoodLogRepository
from app.schemas.bot_responses import BotResponse
from app.services.audit_service import AuditService


def start_edit_last(user_id: uuid.UUID, db: Session) -> BotResponse:
    last_log = FoodLogRepository(db).get_last_for_user(user_id)
    if not last_log:
        return BotResponse(text="Kein Eintrag zum Bearbeiten gefunden.")

    return start_edit_log(last_log.id, user_id, db)


def start_edit_log(log_id: uuid.UUID, user_id: uuid.UUID, db: Session) -> BotResponse:
    log = FoodLogRepository(db).get_by_id(log_id)
    if not log or log.user_id != user_id or log.status != "saved":
        return BotResponse(text="Diesen Eintrag kann ich nicht bearbeiten.")

    state_repo = ConversationStateRepository(db)
    state_repo.delete_for_user(user_id)
    state_repo.create(
        user_id=user_id,
        state_type="edit_last",
        payload={"food_log_id": str(log.id)},
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    AuditService(db).log(
        event_type="edit_last_started",
        user_id=user_id,
        payload={"food_log_id": str(log.id), "source": "button"},
    )
    return BotResponse(
        text=(
            "Sende mir den korrigierten Eintrag als neue Nachricht.\n"
            "Der letzte Eintrag wird ersetzt. Mit /cancel brichst du ab."
        )
    )


def delete_log(log_id: uuid.UUID, user_id: uuid.UUID, db: Session) -> BotResponse:
    repo = FoodLogRepository(db)
    log = repo.get_by_id(log_id)
    if not log or log.user_id != user_id or log.status != "saved":
        return BotResponse(text="Diesen Eintrag kann ich nicht löschen.")

    repo.soft_delete(log)
    AuditService(db).log(
        event_type="food_log_deleted",
        user_id=user_id,
        payload={"food_log_id": str(log.id), "source": "button"},
    )
    return BotResponse(text="Gelöscht. Der Eintrag zählt nicht mehr in deinem Tagesstand.")


def confirm_log(log_id: uuid.UUID, user_id: uuid.UUID, db: Session) -> BotResponse:
    log = FoodLogRepository(db).get_by_id(log_id)
    if not log or log.user_id != user_id or log.status != "saved":
        return BotResponse(text="Diesen Eintrag konnte ich nicht bestätigen.")

    AuditService(db).log(
        event_type="food_log_confirmed",
        user_id=user_id,
        payload={"food_log_id": str(log.id), "source": "button"},
    )
    return BotResponse(text="Passt, bleibt gespeichert.")
