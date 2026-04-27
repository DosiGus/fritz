import logging
import uuid
from pathlib import Path

from app.config import settings
from app.db.session import SessionLocal
from app.integrations.telegram_files import TelegramFileClient
from app.services.food_pipeline import handle_food_message
from app.workers.worker import get_voice_queue

logger = logging.getLogger(__name__)


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
            _send_error_message(chat_id, "Sprachnachricht konnte nicht heruntergeladen werden.")
            return

        transcript = _transcribe(local_path)
        if not transcript:
            logger.warning("voice_transcription_empty", extra={"file_id": file_id})
            _send_error_message(chat_id, "Sprachnachricht konnte nicht transkribiert werden.")
            return

        logger.info("voice_transcribed", extra={"user_id": user_id, "length": len(transcript)})

        with SessionLocal() as db:
            response = handle_food_message(uuid.UUID(user_id), transcript, source="voice", db=db)
        _send_message(chat_id, response.text)

    finally:
        _cleanup(local_path)
        tg_client.close()


def _transcribe(audio_path: Path) -> str | None:
    try:
        from faster_whisper import WhisperModel  # type: ignore[import]
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(audio_path), language="de")
        return " ".join(segment.text for segment in segments).strip()
    except Exception as exc:
        logger.error("transcription_error", extra={"error": str(exc)})
        return None


def _send_error_message(chat_id: int, text: str) -> None:
    _send_message(chat_id, text)


def _send_message(chat_id: int, text: str) -> None:
    try:
        import httpx
        httpx.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10.0,
        )
    except Exception as exc:
        logger.error("send_message_failed", extra={"chat_id": chat_id, "error": str(exc)})


def _cleanup(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
            logger.debug("voice_file_deleted", extra={"path": str(path)})
    except OSError as exc:
        logger.warning("voice_cleanup_failed", extra={"path": str(path), "error": str(exc)})
