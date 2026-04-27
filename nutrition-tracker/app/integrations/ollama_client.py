import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=settings.ollama_base_url,
            timeout=settings.ollama_timeout,
        )

    def generate(self, prompt: str, model: str | None = None, format: str | None = "json") -> str | None:
        payload = {
            "model": model or settings.ollama_model,
            "prompt": prompt,
            "stream": False,
        }
        if format:
            payload["format"] = format

        try:
            response = self._client.post("/api/generate", json=payload)
            response.raise_for_status()
            return response.json().get("response")
        except httpx.HTTPError as exc:
            logger.warning("ollama_generate_failed", extra={"error": str(exc)})
            return None

    def chat(self, messages: list[dict], model: str | None = None, format: str | None = "json") -> str | None:
        payload = {
            "model": model or settings.ollama_model,
            "messages": messages,
            "stream": False,
        }
        if format:
            payload["format"] = format

        try:
            response = self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            return response.json().get("message", {}).get("content")
        except httpx.HTTPError as exc:
            logger.warning("ollama_chat_failed", extra={"error": str(exc)})
            return None

    def is_available(self) -> bool:
        try:
            self._client.get("/api/tags", timeout=3.0)
            return True
        except httpx.HTTPError:
            return False

    def close(self) -> None:
        self._client.close()
