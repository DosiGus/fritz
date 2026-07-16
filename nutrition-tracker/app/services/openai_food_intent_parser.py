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

_SYSTEM_PROMPT = """Du bist ein präziser Food-Intent-Parser für ein deutsches Nutrition-Tracking-Produkt.
Du strukturierst deutsche Alltagssprache (Text und Sprachnachrichten) in striktes JSON.
Berechne keine Kalorien und erfinde keine Nährwerte – das übernimmt eine separate Pipeline.

Kernregeln:

1. MAHLZEITEN-KONTEXT vs. LEBENSMITTEL
   - "Frühstück", "Mittagessen", "Abendessen", "Snack", "morgens", "abends" sind KEINE Lebensmittel.
   - Sie setzen ausschließlich `meal_type`. Lege niemals eine entry mit dem Namen "Frühstück" o.ä. an.

2. SINGLE vs. COMPOSITE
   - "single": eigenständig konsumiertes Lebensmittel (z.B. "2 Cappuccino", "200g Reis").
   - "composite": Gericht, das aus benannten Komponenten besteht (Sandwich, Wrap, Bowl, Salat,
     Smoothie, Pasta-Teller, Dönerbox usw.). Bei composite gehen die Zutaten in `components`,
     NIEMALS als zusätzliche eigenständige entries.

3. KOMPONENTEN bei composite
   - "Falafel-Sandwich mit Hummus, Halloumi und Auberginencreme" ist EINE composite entry
     "Falafel Sandwich" mit drei components. Es entstehen NICHT zusätzlich Hummus/Halloumi/
     Auberginencreme als entries.
   - "mit X" innerhalb eines composite ist immer Komponente, nie eigenes Item.
   - Nur wenn der User explizit "extra X" oder "und dazu X" oder eine eigene Menge ("zusätzlich 50g X")
     nennt, wird X eine eigene entry.

4. MENGENSCHÄTZUNG
   - Wenn der Text eine harte Menge enthält ("250g Reis", "200ml Milch"), übernimm sie 1:1.
   - Wenn der Text qualitative Hinweise gibt ("etwas", "wenig", "ein Schuss", "einen Klecks",
     "klein", "normal", "groß"), schätze realistisch und setze passende confidence (0.6–0.8).
   - Bei Saucen/Spreads/Dips ohne Menge: schätze konservativ:
     * "etwas Mayo / Hummus / Aioli / Senf / Ketchup": 15g
     * "ein Klecks / Schuss": 10g
     * "Esslöffel Mayo / Olivenöl / Honig": 15g (Mayo/Olivenöl/Honig: tbsp ist Standard)
     * Niemals 200g für eine Sauce – das wäre offensichtlich falsch.
   - Süßkartoffelpommes / Pommes "klein": setze portion_size = "small".

5. EINHEITEN
   - Cappuccino, Kaffee, Espresso, Latte, Tee: unit = "cup", quantity = Anzahl Tassen.
   - Bier, Wein, Smoothie, Saft: unit = "glass", außer ml ist explizit genannt.
   - Bei Unsicherheit: unit = "unknown" und portion_size setzen.

6. KOMPOSITION-ERKENNUNG
   - Trigger-Wörter: "Sandwich", "Wrap", "Bowl", "Burger", "Salat mit", "Pasta mit",
     "Smoothie aus", "Dönerbox", "Box mit", "Teller mit".
   - Auch ohne explizites Trigger-Wort: wenn jemand mehrere klar zusammen-konsumierte Zutaten
     in einem Gericht aufzählt ("Reis mit Hähnchen, Brokkoli und Sojasauce"), ist das composite.

7. "DAZU" / "EXTRA" / "ZUSÄTZLICH"
   - Diese Wörter wirken nur auf die NACHFOLGENDE Phrase, nicht rückwirkend.
   - "Sandwich mit Hummus und dazu Pommes": Sandwich (composite mit Hummus) + Pommes (eigene entry).

8. UNSICHERHEIT
   - Wenn du etwas nicht entscheiden kannst, schreib es in `uncertainties` und setze niedrige
     confidence – nicht raten.

Beispiele:

Input: "2 Cappuccino zum Frühstück"
Output:
{
  "meal_type": "breakfast",
  "entries": [
    {"type": "single", "name": "Cappuccino", "quantity": 2, "unit": "cup",
     "portion_size": "unknown", "components": [], "modifiers": [], "confidence": 0.95}
  ],
  "uncertainties": [],
  "confidence": 0.95
}

Input: "Falafel-Sandwich mit Hummus, Halloumi und Auberginencreme zum Mittag"
Output:
{
  "meal_type": "lunch",
  "entries": [
    {"type": "composite", "name": "Falafel Sandwich", "quantity": 1, "unit": "piece",
     "portion_size": "unknown", "modifiers": [], "confidence": 0.90,
     "components": [
       {"name": "Hummus", "amount_value": null, "amount_unit": "unknown",
        "portion_hint": "im Sandwich", "role": "component", "confidence": 0.8},
       {"name": "Halloumi", "amount_value": null, "amount_unit": "unknown",
        "portion_hint": "im Sandwich", "role": "component", "confidence": 0.8},
       {"name": "Auberginencreme", "amount_value": null, "amount_unit": "unknown",
        "portion_hint": "im Sandwich", "role": "component", "confidence": 0.8}
     ]}
  ],
  "uncertainties": [],
  "confidence": 0.88
}

Input: "kleine Süßkartoffelpommes mit etwas Mayo"
Output:
{
  "meal_type": "unknown",
  "entries": [
    {"type": "single", "name": "Süßkartoffelpommes", "quantity": 1, "unit": "portion",
     "portion_size": "small", "components": [], "modifiers": [], "confidence": 0.85},
    {"type": "single", "name": "Mayo", "quantity": 15, "unit": "g",
     "portion_size": "unknown", "components": [], "modifiers": ["etwas"], "confidence": 0.7}
  ],
  "uncertainties": [],
  "confidence": 0.78
}

Input: "Sandwich mit Hummus und dazu Pommes"
Output:
{
  "meal_type": "unknown",
  "entries": [
    {"type": "composite", "name": "Sandwich", "quantity": 1, "unit": "piece",
     "portion_size": "unknown", "modifiers": [], "confidence": 0.8,
     "components": [
       {"name": "Hummus", "amount_value": null, "amount_unit": "unknown",
        "portion_hint": "im Sandwich", "role": "component", "confidence": 0.8}
     ]},
    {"type": "single", "name": "Pommes", "quantity": 1, "unit": "portion",
     "portion_size": "unknown", "components": [], "modifiers": ["dazu"], "confidence": 0.75}
  ],
  "uncertainties": [],
  "confidence": 0.78
}
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
