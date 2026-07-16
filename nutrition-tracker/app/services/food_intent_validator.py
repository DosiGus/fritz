from __future__ import annotations

import uuid
from statistics import mean

from sqlalchemy.orm import Session

from app.schemas.parsed_food import ParsedFoodItem, ParsedFoodMessage
from app.services.audit_service import AuditService


def validate_food_intent(
    parsed: ParsedFoodMessage,
    original_text: str,
    db: Session | None = None,
    user_id: uuid.UUID | None = None,
) -> ParsedFoodMessage:
    """Filter the LLM output for downstream pipeline.

    The LLM is responsible for classifying entries (single/composite) and roles
    (main/component). Here we only do safety filtering: keep main items, attach
    component names as context to their parent, drop empties.
    """
    if not parsed.items:
        return parsed

    items = [item.model_copy(deep=True) for item in parsed.items]
    main_items = [item for item in items if item.role == "main"]
    components = [item for item in items if item.role != "main"]

    for component in components:
        parent = _find_parent(component, main_items)
        if parent is None:
            continue
        _attach_component_as_context(parent, component)

    overall = round(mean([item.confidence for item in main_items]), 2) if main_items else 0.0

    if components:
        _audit(
            db,
            user_id,
            "food_intent_validated",
            {
                "original_text": original_text,
                "kept": [item.model_dump() for item in main_items],
                "attached_components": [item.model_dump() for item in components],
            },
        )

    return ParsedFoodMessage(
        meal_type=parsed.meal_type,
        items=main_items,
        overall_confidence=overall,
        llm_called=parsed.llm_called,
    )


def _find_parent(component: ParsedFoodItem, main_items: list[ParsedFoodItem]) -> ParsedFoodItem | None:
    if component.parent_name:
        wanted = component.parent_name.lower()
        for parent in main_items:
            if parent.name.lower() == wanted:
                return parent
    if len(main_items) == 1:
        return main_items[0]
    return None


def _attach_component_as_context(parent: ParsedFoodItem, component: ParsedFoodItem) -> None:
    label = component.name
    if label not in parent.modifiers:
        parent.modifiers.append(label)
    parent.notes = _merge_notes(parent.notes, label)


def _merge_notes(existing: str | None, addition: str) -> str:
    values: list[str] = []
    for value in (existing, addition):
        if value and value not in values:
            values.append(value)
    return "; ".join(values)


def _audit(
    db: Session | None,
    user_id: uuid.UUID | None,
    event_type: str,
    payload: dict,
) -> None:
    if db is None:
        return
    AuditService(db).log(event_type=event_type, user_id=user_id, payload=payload)
