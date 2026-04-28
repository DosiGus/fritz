from __future__ import annotations

import logging
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.db.repositories.users import UserRepository
from app.db.session import SessionLocal
from app.services.audit_service import AuditService
from app.services.food_pipeline import handle_food_message

logger = logging.getLogger(__name__)


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = update.message.text

    with SessionLocal() as db:
        user_repo = UserRepository(db)
        db_user, _ = user_repo.get_or_create(
            telegram_user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code,
        )

        audit = AuditService(db)
        audit.log(
            event_type="message_received",
            user_id=db_user.id,
            payload={"source": "text", "length": len(text)},
        )
        response = handle_food_message(db_user.id, text, source="text", db=db)

    await update.message.reply_text(
        response.text,
        reply_markup=_to_markup(response.inline_keyboard),
    )


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    voice = update.message.voice

    from app.config import settings
    if not settings.voice_processing_enabled:
        await update.message.reply_text("Sprachnachrichten sind aktuell deaktiviert.")
        return

    if voice.duration > settings.max_voice_seconds:
        await update.message.reply_text(
            f"Sprachnachricht zu lang. Maximum: {settings.max_voice_seconds} Sekunden."
        )
        return

    await update.message.reply_text("🎙 Verarbeite deine Sprachnachricht...")

    from app.workers.voice_jobs import enqueue_voice_job
    with SessionLocal() as db:
        user_repo = UserRepository(db)
        db_user, _ = user_repo.get_or_create(
            telegram_user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code,
        )
        user_id = db_user.id

    enqueue_voice_job(
        file_id=voice.file_id,
        user_id=str(user_id),
        chat_id=update.effective_chat.id,
    )


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel":
        user = query.from_user
        with SessionLocal() as db:
            user_repo = UserRepository(db)
            db_user = user_repo.get_by_telegram_id(user.id)
            if db_user:
                from app.db.repositories.conversation_states import ConversationStateRepository
                state_repo = ConversationStateRepository(db)
                state = state_repo.get_active_for_user(db_user.id)
                state_repo.delete_for_user(db_user.id)
                AuditService(db).log(
                    event_type="conversation_cancelled",
                    user_id=db_user.id,
                    payload={"state_type": state.state_type if state else None},
                )
        await query.edit_message_text("❌ Abgebrochen.")
        return

    user = query.from_user
    with SessionLocal() as db:
        user_repo = UserRepository(db)
        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await query.edit_message_text("Starte zuerst mit /start.")
            return

        if data.startswith("template_save:"):
            from app.services.meal_template_service import prompt_save_template_name

            log_id = _uuid_from_callback(data)
            response = (
                prompt_save_template_name(log_id, db_user.id, db)
                if log_id
                else _invalid_callback_response()
            )
        elif data.startswith("template:"):
            from app.services.meal_template_service import log_template

            template_id = _uuid_from_callback(data)
            response = log_template(template_id, db_user.id, db) if template_id else _invalid_callback_response()
        elif data.startswith("edit:"):
            from app.services.edit_log_service import start_edit_log

            log_id = _uuid_from_callback(data)
            response = start_edit_log(log_id, db_user.id, db) if log_id else _invalid_callback_response()
        elif data.startswith("delete:"):
            from app.services.edit_log_service import delete_log

            log_id = _uuid_from_callback(data)
            response = delete_log(log_id, db_user.id, db) if log_id else _invalid_callback_response()
        elif data.startswith("confirm:"):
            from app.services.edit_log_service import confirm_log

            log_id = _uuid_from_callback(data)
            response = confirm_log(log_id, db_user.id, db) if log_id else _invalid_callback_response()
        else:
            from app.services.clarification_service import resolve_clarification

            response = resolve_clarification(data, db_user.id, db)

    await query.edit_message_text(
        response.text,
        reply_markup=_to_markup(response.inline_keyboard),
    )


def _to_markup(keyboard: list[list[dict]] | None) -> InlineKeyboardMarkup | None:
    if not keyboard:
        return None
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(button["text"], callback_data=button["callback_data"]) for button in row]
        for row in keyboard
    ])


def _uuid_from_callback(callback_data: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(callback_data.split(":", 1)[1])
    except (IndexError, ValueError):
        logger.warning("invalid_callback_uuid", extra={"callback_prefix": callback_data.split(":", 1)[0]})
        return None


def _invalid_callback_response():
    from app.schemas.bot_responses import BotResponse

    return BotResponse(text="Diese Auswahl konnte ich nicht zuordnen.")
