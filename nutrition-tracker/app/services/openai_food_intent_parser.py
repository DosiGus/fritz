from __future__ import annotations

import json
import logging
import uuid

import httpx
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import settings
from app.schemas.food_intent import FOOD_INTENT_JSON_SCHEMA, FoodIntent
from app.services.audit_service import AuditService
from app.services.hard_fact_extractor import HardFact

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Du bist ein präziser Food-Intent-Parser für ein Nutrition-Tracking-Produkt.
Du strukturierst deutsche Alltagssprache aus Text und Sprachnachrichten in JSON.
Du berechnest keine Kalorien und erfindest keine Nährwerte.

Wichtige Regeln:
- Nutze "single" für einzeln gegessene Lebensmittel.
- Nutze "composite" für Bowls, Salate, Smoothies, Sandwiches, Pasta-Teller, Dönerboxen usw.
- Extrahiere Komponenten bei composite entries, z.B. Skyr, TK Mango, Honig.
- "mit X" ist normalerweise Komponente/Modifier, nicht separat gezählt.
- "extra", "dazu", "zusätzlich", "separat" oder eigene Menge macht ein Item eigenständig.
- Portionen wie klein/normal/groß als portion_size ausgeben.
- Harte Mengen aus dem Text beibehalten.
- Wenn du unsicher bist, fülle uncertainties statt zu raten.
"""


def parse_food_intent(
    text: str,
    facts: list[HardFact],
    db: Session | None = None,
    user_id: uuid.UUID | None = None,
) -> FoodIntent | None:
    if not settings.openai_api_key:
        return None

    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_food_intent_model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_prompt(text, facts)},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "food_intent",
                        "strict": True,
                        "schema": FOOD_INTENT_JSON_SCHEMA,
                    },
                },
            },
            timeout=settings.openai_food_intent_timeout,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        intent = FoodIntent.model_validate(json.loads(content))
    except (KeyError, TypeError, json.JSONDecodeError, ValidationError, httpx.HTTPError) as exc:
        logger.warning("food_intent_parse_failed", extra={"error": str(exc)})
        _audit(db, user_id, "food_intent_parse_failed", {"text": text, "error": str(exc)})
        return None

    _audit(db, user_id, "food_intent_parsed", {"text": text, "intent": intent.model_dump()})
    return intent


def _build_user_prompt(text: str, facts: list[HardFact]) -> str:
    facts_payload = [
        {"type": fact.type, "text": fact.text, "value": fact.value, "unit": fact.unit}
        for fact in facts
    ]
    return (
        "Extrahiere den Food Intent aus diesem Eintrag.\n"
        f"Text: {text!r}\n"
        f"Harte Fakten, die nicht verloren gehen dürfen: {json.dumps(facts_payload, ensure_ascii=False)}"
    )


def _audit(
    db: Session | None,
    user_id: uuid.UUID | None,
    event_type: str,
    payload: dict,
) -> None:
    if db is None:
        return
    AuditService(db).log(event_type=event_type, user_id=user_id, payload=payload)
