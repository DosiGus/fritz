"""Tests for voice_jobs — all external I/O is mocked (no network)."""
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FILE_ID = "test_file_id_123"
USER_ID = str(uuid.uuid4())
CHAT_ID = 42


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_process_voice_message_happy_path():
    """Download ok → transcript ok → food pipeline called → file cleaned up."""
    mock_response = MagicMock()
    mock_response.text = "Gespeichert ✅\n250g Skyr"
    mock_response.inline_keyboard = None

    with (
        patch("app.workers.voice_jobs.TelegramFileClient") as MockClient,
        patch("app.workers.voice_jobs._transcribe", return_value="250g Skyr"),
        patch("app.workers.voice_jobs.handle_food_message", return_value=mock_response),
        patch("app.workers.voice_jobs.SessionLocal") as MockSession,
        patch("app.workers.voice_jobs._send_message") as mock_send,
        patch("app.workers.voice_jobs._cleanup") as mock_cleanup,
    ):
        mock_tg = MockClient.return_value
        mock_tg.download_to_disk.return_value = True
        MockSession.return_value.__enter__ = MagicMock(return_value=MagicMock())
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        from app.workers.voice_jobs import process_voice_message
        process_voice_message(FILE_ID, USER_ID, CHAT_ID)

    mock_tg.download_to_disk.assert_called_once()
    sent_text = mock_send.call_args.args[1]
    assert sent_text.startswith("Ich habe verstanden:\n250g Skyr")
    assert mock_response.text in sent_text
    assert mock_send.call_args.kwargs["inline_keyboard"] is None
    mock_cleanup.assert_called_once()
    mock_tg.close.assert_called_once()


def test_process_voice_message_sends_inline_keyboard():
    """Clarification buttons from the shared food pipeline survive voice jobs."""
    keyboard = [[{"text": "Klein", "callback_data": "clarify:0"}]]
    mock_response = MagicMock()
    mock_response.text = "Welche Portion passt?"
    mock_response.inline_keyboard = keyboard

    with (
        patch("app.workers.voice_jobs.TelegramFileClient") as MockClient,
        patch("app.workers.voice_jobs._transcribe", return_value="ein Teller Pasta"),
        patch("app.workers.voice_jobs.handle_food_message", return_value=mock_response),
        patch("app.workers.voice_jobs.SessionLocal") as MockSession,
        patch("app.workers.voice_jobs._send_message") as mock_send,
        patch("app.workers.voice_jobs._cleanup"),
    ):
        mock_tg = MockClient.return_value
        mock_tg.download_to_disk.return_value = True
        MockSession.return_value.__enter__ = MagicMock(return_value=MagicMock())
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        from app.workers.voice_jobs import process_voice_message
        process_voice_message(FILE_ID, USER_ID, CHAT_ID)

    sent_text = mock_send.call_args.args[1]
    assert sent_text.startswith("Ich habe verstanden:\nein Teller Pasta")
    assert mock_response.text in sent_text
    assert mock_send.call_args.kwargs["inline_keyboard"] == keyboard


# ---------------------------------------------------------------------------
# Download failure
# ---------------------------------------------------------------------------

def test_process_voice_message_download_fail():
    """Download failure → error message sent, cleanup still runs."""
    with (
        patch("app.workers.voice_jobs.TelegramFileClient") as MockClient,
        patch("app.workers.voice_jobs._send_error_message") as mock_err,
        patch("app.workers.voice_jobs._cleanup") as mock_cleanup,
    ):
        mock_tg = MockClient.return_value
        mock_tg.download_to_disk.return_value = False

        from app.workers.voice_jobs import process_voice_message
        process_voice_message(FILE_ID, USER_ID, CHAT_ID)

    mock_err.assert_called_once()
    error_text = mock_err.call_args[0][1]
    assert "heruntergeladen" in error_text
    mock_cleanup.assert_called_once()
    mock_tg.close.assert_called_once()


# ---------------------------------------------------------------------------
# Empty transcript
# ---------------------------------------------------------------------------

def test_process_voice_message_empty_transcript():
    """Successful download but empty transcript → error message sent."""
    with (
        patch("app.workers.voice_jobs.TelegramFileClient") as MockClient,
        patch("app.workers.voice_jobs._transcribe", return_value=""),
        patch("app.workers.voice_jobs._send_error_message") as mock_err,
        patch("app.workers.voice_jobs._cleanup") as mock_cleanup,
    ):
        mock_tg = MockClient.return_value
        mock_tg.download_to_disk.return_value = True

        from app.workers.voice_jobs import process_voice_message
        process_voice_message(FILE_ID, USER_ID, CHAT_ID)

    mock_err.assert_called_once()
    mock_cleanup.assert_called_once()


# ---------------------------------------------------------------------------
# Transcription raises exception
# ---------------------------------------------------------------------------

def test_process_voice_message_transcription_exception():
    """_transcribe returns None on exception (already handled inside _transcribe)."""
    with (
        patch("app.workers.voice_jobs.TelegramFileClient") as MockClient,
        patch("app.workers.voice_jobs._transcribe", return_value=None),
        patch("app.workers.voice_jobs._send_error_message") as mock_err,
        patch("app.workers.voice_jobs._cleanup") as mock_cleanup,
    ):
        mock_tg = MockClient.return_value
        mock_tg.download_to_disk.return_value = True

        from app.workers.voice_jobs import process_voice_message
        process_voice_message(FILE_ID, USER_ID, CHAT_ID)

    mock_err.assert_called_once()
    mock_cleanup.assert_called_once()


# ---------------------------------------------------------------------------
# _transcribe unit tests
# ---------------------------------------------------------------------------

def test_transcribe_returns_none_without_openai_api_key(tmp_path):
    target = tmp_path / "voice.ogg"
    target.write_bytes(b"fake audio")

    from app.workers import voice_jobs

    with patch.object(voice_jobs.settings, "openai_api_key", ""):
        result = voice_jobs._transcribe(target)

    assert result is None


def test_transcribe_uses_openai_audio_api(tmp_path):
    target = tmp_path / "voice.ogg"
    target.write_bytes(b"fake audio")

    mock_response = MagicMock()
    mock_response.json.return_value = {"text": "zwei Cappuccino mit Hafermilch"}

    from app.workers import voice_jobs

    with (
        patch.object(voice_jobs.settings, "openai_api_key", "test-key"),
        patch.object(voice_jobs.settings, "openai_transcription_model", "gpt-4o-transcribe"),
        patch("httpx.post", return_value=mock_response) as mock_post,
    ):
        result = voice_jobs._transcribe(target)

    assert result == "zwei Cappuccino mit Hafermilch"
    mock_response.raise_for_status.assert_called_once()
    call = mock_post.call_args
    assert call.args[0] == "https://api.openai.com/v1/audio/transcriptions"
    assert call.kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert call.kwargs["data"]["model"] == "gpt-4o-transcribe"
    assert call.kwargs["data"]["language"] == "de"
    assert call.kwargs["files"]["file"][0] == "voice.ogg"


def test_transcribe_returns_none_on_openai_exception(tmp_path):
    target = tmp_path / "voice.ogg"
    target.write_bytes(b"fake audio")

    from app.workers import voice_jobs

    with (
        patch.object(voice_jobs.settings, "openai_api_key", "test-key"),
        patch("httpx.post", side_effect=RuntimeError("network down")),
    ):
        result = voice_jobs._transcribe(target)

    assert result is None


def test_send_message_includes_reply_markup():
    keyboard = [[{"text": "Normal", "callback_data": "clarify:1"}]]
    with patch("httpx.post") as mock_post:
        from app.workers.voice_jobs import _send_message

        _send_message(CHAT_ID, "Welche Portion passt?", inline_keyboard=keyboard)

    payload = mock_post.call_args.kwargs["json"]
    assert payload["chat_id"] == CHAT_ID
    assert payload["text"] == "Welche Portion passt?"
    assert payload["reply_markup"] == {"inline_keyboard": keyboard}


# ---------------------------------------------------------------------------
# _cleanup
# ---------------------------------------------------------------------------

def test_cleanup_deletes_existing_file(tmp_path):
    target = tmp_path / "voice.ogg"
    target.write_bytes(b"fake audio")

    from app.workers.voice_jobs import _cleanup
    _cleanup(target)

    assert not target.exists()


def test_cleanup_is_safe_for_missing_file(tmp_path):
    target = tmp_path / "nonexistent.ogg"
    from app.workers.voice_jobs import _cleanup
    _cleanup(target)  # must not raise
