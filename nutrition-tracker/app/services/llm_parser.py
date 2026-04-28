from __future__ import annotations

import json
import logging
import uuid

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.integrations.ollama_client import OllamaClient
from app.schemas.parsed_food import ParsedFoodMessage
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Du bist ein Parser für Ernährungseinträge.
Extrahiere Lebensmittel, Mengen, Einheiten, Zubereitung, Mahlzeitentyp und semantische Rollen.
Gib ausschließlich valides JSON im vorgegebenen Schema zurück.
Berechne keine Kalorien und erfinde keine Nährwerte.
Wenn Menge oder Einheit unklar ist, setze quantity auf null und unit auf "unknown".
Unterscheide Haupt-Items von Bestandteilen und Beschreibungen:
- role="main": eigenständig gegessen/getrunken, z.B. "2 Cappuccino", "200g Reis extra".
- role="component": Bestandteil eines Haupt-Items ohne eigene Menge, z.B. "mit H-Milch" in "Cappuccino mit H-Milch".
- role="modifier": Zubereitungs-/Portionshinweis, z.B. "normale Größe", "ohne Zucker".
- role="attribute": reine Info zu einem anderen Item, z.B. "Die Milch hat 3,6% Fett".
Setze parent_name, wenn component/modifier/attribute ein Haupt-Item beschreibt.
Speichere "mit X" ohne eigene Menge nicht als separates main item. Bei "extra", "dazu", "zusätzlich" oder eigener Menge ist es ein main item."""

_SCHEMA_HINT = {
    "meal_type": "unknown|breakfast|lunch|dinner|snack",
    "items": [
        {
            "name": "string",
            "quantity": "number|null",
            "unit": "g|ml|piece|slice|tbsp|tsp|portion|plate|bowl|glass|cup|unknown",
            "role": "main|component|modifier|attribute",
            "parent_name": "string|null",
            "preparation": "raw|cooked|fried|grilled|unknown",
            "notes": "string|null",
            "modifiers": ["string"],
            "confidence": "number 0..1",
        }
    ],
    "overall_confidence": "number 0..1",
}


def parse(text: str, db: Session | None = None, user_id: uuid.UUID | None = None) -> ParsedFoodMessage:
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
            _audit_llm_error(db, user_id, "llm_parse_error", {"attempt": attempt + 1, "text": text})
    finally:
        client.close()

    _audit_llm_error(db, user_id, "llm_error", {"reason": "empty_result", "text": text})
    return ParsedFoodMessage(items=[], overall_confidence=0.0, llm_called=True)


def _audit_llm_error(
    db: Session | None,
    user_id: uuid.UUID | None,
    event_type: str,
    payload: dict,
) -> None:
    if db is None:
        return
    AuditService(db).log(event_type=event_type, user_id=user_id, payload=payload)


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
    if item.role != "main" and not item.parent_name and item.notes:
        item.parent_name = item.notes.removeprefix("in ").strip() or None
    return item


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
