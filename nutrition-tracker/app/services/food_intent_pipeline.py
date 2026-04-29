from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.schemas.parsed_food import ParsedFoodMessage
from app.services.audit_service import AuditService
from app.services.deterministic_food_parser import parse_deterministic_food
from app.services.food_intent_adapter import food_intent_to_parsed
from app.services.food_intent_validator import validate_food_intent
from app.services.hard_fact_extractor import extract_hard_facts
from app.services.openai_food_intent_parser import parse_food_intent


def parse_with_food_intent_v2(
    text: str,
    db: Session,
    user_id: uuid.UUID,
) -> ParsedFoodMessage | None:
    """Parse food text with local deterministic parsing before OpenAI fallback.

    Pipeline:
      text -> hard facts -> deterministic parser
                       -> OpenAI intent -> adapter -> validator
    """
    facts = extract_hard_facts(text)
    deterministic = parse_deterministic_food(text, facts)
    if deterministic is not None:
        _audit_parse(db, user_id, "deterministic_food_parser_used", text, facts, deterministic)
        return deterministic

    intent = parse_food_intent(text, facts, db=db, user_id=user_id)
    if intent is None:
        _audit_parse_failed(db, user_id, text, facts)
        return deterministic

    parsed = food_intent_to_parsed(intent, facts)
    parsed = validate_food_intent(parsed, text, db=db, user_id=user_id)

    _audit_parse(db, user_id, "food_intent_v2_used", text, facts, parsed)
    return parsed


def _audit_parse(
    db: Session,
    user_id: uuid.UUID,
    event_type: str,
    text: str,
    facts,
    parsed: ParsedFoodMessage,
) -> None:
    AuditService(db).log(
        event_type=event_type,
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


def _audit_parse_failed(db: Session, user_id: uuid.UUID, text: str, facts) -> None:
    AuditService(db).log(
        event_type="food_parser_unavailable",
        user_id=user_id,
        payload={
            "text": text,
            "facts": [
                {"type": fact.type, "text": fact.text, "value": fact.value, "unit": fact.unit}
                for fact in facts
            ],
        },
    )
