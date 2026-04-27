import logging

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
                ConversationStateRepository(db).delete_for_user(db_user.id)
        await query.edit_message_text("❌ Abgebrochen.")
        return

    user = query.from_user
    with SessionLocal() as db:
        user_repo = UserRepository(db)
        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await query.edit_message_text("Starte zuerst mit /start.")
            return

        if data.startswith("template:"):
            from app.services.meal_template_service import log_template

            import uuid

            response = log_template(uuid.UUID(data.split(":", 1)[1]), db_user.id, db)
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
