from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from app.integrations.ollama_client import OllamaClient
from app.schemas.parsed_food import ParsedFoodMessage

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Du bist ein Parser für Ernährungseinträge.
Extrahiere Lebensmittel, Mengen, Einheiten, Zubereitung und Mahlzeitentyp.
Gib ausschließlich valides JSON im vorgegebenen Schema zurück.
Berechne keine Kalorien und erfinde keine Nährwerte.
Wenn Menge oder Einheit unklar ist, setze quantity auf null und unit auf "unknown"."""

_SCHEMA_HINT = {
    "meal_type": "unknown|breakfast|lunch|dinner|snack",
    "items": [
        {
            "name": "string",
            "quantity": "number|null",
            "unit": "g|ml|piece|slice|tbsp|tsp|portion|plate|bowl|glass|cup|unknown",
            "preparation": "raw|cooked|fried|grilled|unknown",
            "notes": "string|null",
            "confidence": "number 0..1",
        }
    ],
    "overall_confidence": "number 0..1",
}


def parse(text: str) -> ParsedFoodMessage:
    """Use Ollama as a structure-only fallback parser.

    Failures return an empty low-confidence result. The caller decides whether
    to merge or ask a clarification.
    """
    prompt = _build_prompt(text)
    client = OllamaClient()
    try:
        for attempt in range(2):
            raw = client.chat(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                format="json",
            )
            parsed = _parse_response(raw)
            if parsed:
                parsed.llm_called = True
                return parsed
            logger.warning("llm_parse_invalid_json", extra={"attempt": attempt + 1})
    finally:
        client.close()

    return ParsedFoodMessage(items=[], overall_confidence=0.0, llm_called=True)


def _build_prompt(text: str) -> str:
    return (
        "Extrahiere aus diesem Ernährungseintrag nur Struktur.\n"
        f"Text: {text!r}\n\n"
        "Schema:\n"
        f"{json.dumps(_SCHEMA_HINT, ensure_ascii=False)}"
    )


def _parse_response(raw: str | None) -> ParsedFoodMessage | None:
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if "items" not in payload and "food" in payload:
        payload["items"] = payload.pop("food")
    if "overall_confidence" not in payload:
        items = payload.get("items") or []
        confidences = [float(item.get("confidence", 0.0)) for item in items if isinstance(item, dict)]
        payload["overall_confidence"] = sum(confidences) / len(confidences) if confidences else 0.0

    try:
        message = ParsedFoodMessage.model_validate(payload)
    except ValidationError as exc:
        logger.warning("llm_parse_validation_failed", extra={"error": str(exc)})
        return None

    message.items = [_sanitize_item(item) for item in message.items]
    message.overall_confidence = _clamp(message.overall_confidence)
    return message


def _sanitize_item(item):
    item.confidence = _clamp(item.confidence)
    if not item.unit:
        item.unit = "unknown"
    if item.quantity is None:
        item.unit = item.unit or "unknown"
    return item


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
