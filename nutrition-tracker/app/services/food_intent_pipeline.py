from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.schemas.parsed_food import ParsedFoodMessage
from app.services.audit_service import AuditService
from app.services.food_intent_adapter import food_intent_to_parsed
from app.services.food_intent_validator import validate_food_intent
from app.services.hard_fact_extractor import extract_hard_facts
from app.services.openai_food_intent_parser import parse_food_intent
from app.services.recipe_decomposer import decompose_recipes


def parse_with_food_intent_v2(
    text: str,
    db: Session,
    user_id: uuid.UUID,
) -> ParsedFoodMessage | None:
    if not settings.food_intent_v2_enabled:
        return None

    facts = extract_hard_facts(text)
    intent = parse_food_intent(text, facts, db=db, user_id=user_id)
    if intent is None:
        return None

    parsed = food_intent_to_parsed(intent, facts)
    parsed = validate_food_intent(parsed, text, db=db, user_id=user_id)
    parsed = decompose_recipes(parsed, text, db=db, user_id=user_id)

    AuditService(db).log(
        event_type="food_intent_v2_used",
        user_id=user_id,
        payload={
            "text": text,
            "facts": [
                {"type": fact.type, "text": fact.text, "value": fact.value, "unit": fact.unit}
                for fact in facts
            ],
            "parsed": parsed.model_dump(),
        },
    )
    return parsed
