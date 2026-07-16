from __future__ import annotations

from statistics import mean

from app.schemas.food_intent import FoodIntent, FoodIntentEntry
from app.schemas.parsed_food import ParsedFoodItem, ParsedFoodMessage
from app.services.hard_fact_extractor import HardFact


def food_intent_to_parsed(intent: FoodIntent, facts: list[HardFact]) -> ParsedFoodMessage:
    """Convert the LLM's FoodIntent into the internal ParsedFoodMessage format.

    The LLM is the source of truth. We only enforce hard facts the regex extractor
    found in the original text (so the LLM cannot drop them).
    """
    items: list[ParsedFoodItem] = []
    single_entry = len(intent.entries) == 1

    for entry in intent.entries:
        quantity = _enforced_quantity(entry, facts, single_entry)
        items.append(
            ParsedFoodItem(
                name=entry.name,
                quantity=quantity,
                unit=entry.unit,
                role="main",
                notes=_notes_for_entry(entry),
                modifiers=entry.modifiers,
                confidence=_clamp(entry.confidence),
            )
        )

        for component in entry.components:
            has_explicit_amount = (
                component.amount_value is not None and component.amount_unit != "unknown"
            )
            items.append(
                ParsedFoodItem(
                    name=component.name,
                    quantity=component.amount_value if has_explicit_amount else None,
                    unit=component.amount_unit if has_explicit_amount else "unknown",
                    role="main" if has_explicit_amount else "component",
                    parent_name=entry.name,
                    notes=component.portion_hint,
                    confidence=_clamp(component.confidence or entry.confidence),
                )
            )

    overall = round(mean([item.confidence for item in items]), 2) if items else _clamp(intent.confidence)
    return ParsedFoodMessage(
        meal_type=_enforced_meal_type(intent, facts),
        items=items,
        overall_confidence=overall,
        llm_called=True,
    )


def _enforced_quantity(entry: FoodIntentEntry, facts: list[HardFact], single_entry: bool) -> float | None:
    if entry.quantity is not None:
        return entry.quantity
    if not single_entry:
        return None
    quantity_facts = [fact for fact in facts if fact.type == "quantity" and isinstance(fact.value, (int, float))]
    if len(quantity_facts) == 1:
        return float(quantity_facts[0].value)
    return None


def _enforced_meal_type(intent: FoodIntent, facts: list[HardFact]) -> str:
    for fact in facts:
        if fact.type == "meal_type" and isinstance(fact.value, str):
            return fact.value
    return intent.meal_type


def _notes_for_entry(entry: FoodIntentEntry) -> str | None:
    values = []
    if entry.portion_size != "unknown":
        values.append(entry.portion_size)
    values.extend(entry.modifiers)
    return "; ".join(values) if values else None


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
