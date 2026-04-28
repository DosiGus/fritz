from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_TELEGRAM_FILE_API = "https://api.telegram.org"


class TelegramFileClient:
    """Downloads files from Telegram servers using the Bot API."""

    def __init__(self, bot_token: str | None = None) -> None:
        self._token = bot_token or settings.telegram_bot_token
        self._client = httpx.Client(base_url=_TELEGRAM_FILE_API, timeout=30.0)

    def get_file_path(self, file_id: str) -> str | None:
        try:
            response = self._client.get(f"/bot{self._token}/getFile", params={"file_id": file_id})
            response.raise_for_status()
            data = response.json()
            if data.get("ok"):
                return data["result"]["file_path"]
            return None
        except httpx.HTTPError as exc:
            logger.warning("tg_get_file_path_failed", extra={"file_id": file_id, "error": str(exc)})
            return None

    def download_to_disk(self, file_id: str, destination: Path) -> Path | None:
        file_path = self.get_file_path(file_id)
        if not file_path:
            return None

        url = f"/file/bot{self._token}/{file_path}"
        try:
            response = self._client.get(url)
            response.raise_for_status()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(response.content)
            logger.info("tg_file_downloaded", extra={"file_id": file_id, "path": str(destination)})
            return destination
        except httpx.HTTPError as exc:
            logger.warning("tg_download_failed", extra={"file_id": file_id, "error": str(exc)})
            return None

    def close(self) -> None:
        self._client.close()
