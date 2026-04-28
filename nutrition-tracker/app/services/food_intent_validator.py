from __future__ import annotations

import re
import uuid
from statistics import mean

from sqlalchemy.orm import Session

from app.schemas.parsed_food import ParsedFoodItem, ParsedFoodMessage
from app.services.audit_service import AuditService
from app.services.static_data import MEAL_CONTEXT_WORDS, canonicalize

_EXTRA_WORDS = {"extra", "dazu", "zusätzlich", "zusaetzlich", "separat"}


def validate_food_intent(
    parsed: ParsedFoodMessage,
    original_text: str,
    db: Session | None = None,
    user_id: uuid.UUID | None = None,
) -> ParsedFoodMessage:
    """Convert parser output into saveable food intent.

    The parser may surface ingredients or descriptive fragments as items. This
    validator keeps only independently consumed foods in `items` and attaches
    component/modifier text to its parent item as context.
    """
    if not parsed.items:
        return parsed

    items = [item.model_copy(deep=True) for item in parsed.items]
    main_items = [item for item in items if _is_saveable_main_item(item)]
    dropped: list[ParsedFoodItem] = []

    for item in items:
        if item in main_items:
            continue
        if _looks_like_component_phrase(item):
            item = _component_from_phrase(item)

        if _should_promote_to_main(item, original_text):
            item.role = "main"
            item.parent_name = None
            main_items.append(item)
            continue

        parent = _find_parent(item, main_items)
        if parent:
            _attach_context(parent, item)
        dropped.append(item)

    cleaned = [
        _clean_main_item(item)
        for item in main_items
        if not _looks_like_attribute_item(item) and not _looks_like_meal_context_item(item)
    ]
    overall = round(mean([item.confidence for item in cleaned]), 2) if cleaned else 0.0

    if dropped or len(cleaned) != len(parsed.items):
        _audit(
            db,
            user_id,
            "food_intent_validated",
            {
                "original_text": original_text,
                "kept": [item.model_dump() for item in cleaned],
                "dropped_or_attached": [item.model_dump() for item in dropped],
            },
        )

    return ParsedFoodMessage(
        meal_type=parsed.meal_type,
        items=cleaned,
        overall_confidence=overall,
        llm_called=parsed.llm_called,
    )


def _is_saveable_main_item(item: ParsedFoodItem) -> bool:
    return (
        item.role == "main"
        and not _looks_like_meal_context_item(item)
        and not _looks_like_attribute_item(item)
        and not _looks_like_component_phrase(item)
    )


def _should_promote_to_main(item: ParsedFoodItem, original_text: str) -> bool:
    if _looks_like_meal_context_item(item):
        return False
    if _looks_like_component_phrase(item):
        return False
    if item.parent_name and item.quantity is None:
        return False
    if item.role == "main":
        return True
    if item.quantity is not None and item.unit in {"g", "ml", "kg", "l", "piece", "slice", "portion", "plate", "bowl", "glass", "cup"}:
        return True
    lowered = original_text.lower()
    name = item.name.lower()
    return any(_extra_word_applies_to_item(lowered, name, word) for word in _EXTRA_WORDS)


def _extra_word_applies_to_item(lowered_text: str, lowered_name: str, word: str) -> bool:
    marker = re.search(rf"\b{word}\b", lowered_text)
    item = re.search(rf"\b{re.escape(lowered_name)}\b", lowered_text)
    if not marker or not item:
        return False
    # Separate markers describe the following phrase. They should not promote
    # ingredients that appeared earlier in a parent meal, e.g.
    # "Sandwich mit Hummus ... und dazu Pommes".
    return marker.start() <= item.start()


def _find_parent(item: ParsedFoodItem, main_items: list[ParsedFoodItem]) -> ParsedFoodItem | None:
    if item.parent_name:
        wanted = item.parent_name.lower()
        for parent in main_items:
            if parent.name.lower() == wanted:
                return parent
    if len(main_items) == 1:
        return main_items[0]
    return None


def _attach_context(parent: ParsedFoodItem, item: ParsedFoodItem) -> None:
    label = item.name
    if item.notes and item.notes.lower() not in {"unknown", "none"}:
        label = f"{label} ({item.notes})"
    if label not in parent.modifiers:
        parent.modifiers.append(label)
    parent.notes = _merge_notes(parent.notes, label)
    parent.confidence = round(min(parent.confidence, max(item.confidence, 0.80)), 2)


def _clean_main_item(item: ParsedFoodItem) -> ParsedFoodItem:
    item.role = "main"
    item.parent_name = None
    item.needs_clarification = bool(item.needs_clarification and item.unit == "unknown")
    return item


def _looks_like_attribute_item(item: ParsedFoodItem) -> bool:
    name = item.name.strip().lower()
    if len(name.split()) >= 7:
        return True
    return bool(re.search(
        r"\b(hat|hatte|haben|hatten|fett|protein|eiweiß|kohlenhydrate|zucker|kcal|kalorien|größe|groesse)\b",
        name,
    ))


def _looks_like_meal_context_item(item: ParsedFoodItem) -> bool:
    return item.name.strip().lower() in MEAL_CONTEXT_WORDS


def _looks_like_component_phrase(item: ParsedFoodItem) -> bool:
    if item.quantity is not None or item.unit not in {"unknown", ""}:
        return False
    return bool(re.search(
        r"\b(dafür|dafuer|damit|darin|dazu|hierfür|hierfuer|verwendet|benutzt|genommen|gemacht|zubereitet)\b",
        item.name.lower(),
    ))


def _component_from_phrase(item: ParsedFoodItem) -> ParsedFoodItem:
    copied = item.model_copy(deep=True)
    copied.role = "component"
    copied.name = _component_name(copied.name)
    copied.needs_clarification = False
    return copied


def _component_name(name: str) -> str:
    cleaned = re.sub(
        r"\b(dafür|dafuer|damit|darin|dazu|hierfür|hierfuer|verwendet|benutzt|genommen|gemacht|zubereitet|habe|hatte|ich)\b",
        " ",
        name,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return canonicalize(cleaned) if cleaned else name


def _merge_notes(existing: str | None, addition: str) -> str:
    values = []
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
