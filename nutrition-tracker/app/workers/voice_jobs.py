from __future__ import annotations

import logging
import mimetypes
import uuid
from pathlib import Path
from typing import Any

from app.config import settings
from app.db.session import SessionLocal
from app.integrations.telegram_files import TelegramFileClient
from app.services.audit_service import AuditService
from app.services.food_pipeline import handle_food_message
from app.workers.worker import get_voice_queue

logger = logging.getLogger(__name__)

TRANSCRIPTION_PROMPT = (
    "Deutsch. Es geht um Ernährungstagebuch-Einträge. "
    "Typische Wörter: Cappuccino, Hafermilch, H-Milch, Skyr, Magerquark, "
    "Proteinshake, Haferflocken, Frühstück, Mittagessen, Abendessen, Gramm, kcal."
)


def enqueue_voice_job(file_id: str, user_id: str, chat_id: int) -> None:
    queue = get_voice_queue()
    queue.enqueue(
        process_voice_message,
        file_id=file_id,
        user_id=user_id,
        chat_id=chat_id,
        job_timeout=120,
    )
    logger.info("voice_job_enqueued", extra={"file_id": file_id, "user_id": user_id})


def process_voice_message(file_id: str, user_id: str, chat_id: int) -> None:
    voice_dir = Path(settings.voice_tmp_dir)
    voice_dir.mkdir(parents=True, exist_ok=True)
    local_path = voice_dir / f"{uuid.uuid4()}.ogg"

    tg_client = TelegramFileClient()
    try:
        downloaded = tg_client.download_to_disk(file_id, local_path)
        if not downloaded:
            logger.error("voice_download_failed", extra={"file_id": file_id})
            _audit_voice_event("voice_download_failed", user_id, {"file_id": file_id})
            _send_error_message(chat_id, "Sprachnachricht konnte nicht heruntergeladen werden.")
            return

        transcript = _transcribe(local_path)
        if not transcript:
            logger.warning("voice_transcription_empty", extra={"file_id": file_id})
            _audit_voice_event("voice_transcription_empty", user_id, {"file_id": file_id})
            _send_error_message(chat_id, "Sprachnachricht konnte nicht transkribiert werden.")
            return

        logger.info("voice_transcribed", extra={"user_id": user_id, "length": len(transcript)})

        with SessionLocal() as db:
            response = handle_food_message(uuid.UUID(user_id), transcript, source="voice", db=db)
        _send_message(
            chat_id,
            f"Ich habe verstanden:\n{transcript}\n\n{response.text}",
            inline_keyboard=response.inline_keyboard,
        )

    finally:
        _cleanup(local_path)
        tg_client.close()


def _transcribe(audio_path: Path) -> str | None:
    if not settings.openai_api_key:
        logger.error("transcription_error", extra={"error": "OPENAI_API_KEY is not configured"})
        return None

    try:
        import httpx

        content_type = mimetypes.guess_type(audio_path.name)[0] or "audio/ogg"
        with audio_path.open("rb") as audio_file:
            response = httpx.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                data={
                    "model": settings.openai_transcription_model,
                    "language": "de",
                    "prompt": TRANSCRIPTION_PROMPT,
                },
                files={"file": (audio_path.name, audio_file, content_type)},
                timeout=settings.openai_transcription_timeout,
            )
        response.raise_for_status()
        transcript = response.json().get("text", "")
        if not isinstance(transcript, str):
            logger.error("transcription_error", extra={"error": "OpenAI response did not contain text"})
            return None
        logger.info("openai_transcription_complete", extra={"model": settings.openai_transcription_model})
        return transcript.strip()
    except Exception as exc:
        logger.error("transcription_error", extra={"error": str(exc)})
        return None


def _send_error_message(chat_id: int, text: str) -> None:
    _send_message(chat_id, text)


def _send_message(chat_id: int, text: str, inline_keyboard: list[list[dict]] | None = None) -> None:
    try:
        import httpx
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if inline_keyboard:
            payload["reply_markup"] = {"inline_keyboard": inline_keyboard}
        httpx.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json=payload,
            timeout=10.0,
        )
    except Exception as exc:
        logger.error("send_message_failed", extra={"chat_id": chat_id, "error": str(exc)})


def _audit_voice_event(event_type: str, user_id: str, payload: dict | None = None) -> None:
    try:
        with SessionLocal() as db:
            AuditService(db).log(
                event_type=event_type,
                user_id=uuid.UUID(user_id),
                payload=payload or {},
            )
    except Exception as exc:
        logger.warning("voice_audit_failed", extra={"event_type": event_type, "error": str(exc)})


def _cleanup(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
            logger.debug("voice_file_deleted", extra={"path": str(path)})
    except OSError as exc:
        logger.warning("voice_cleanup_failed", extra={"path": str(path), "error": str(exc)})
