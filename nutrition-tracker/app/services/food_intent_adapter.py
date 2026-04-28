from __future__ import annotations

from statistics import mean

from app.schemas.food_intent import FoodIntent, FoodIntentEntry
from app.schemas.parsed_food import ParsedFoodItem, ParsedFoodMessage
from app.services.hard_fact_extractor import HardFact
from app.services.static_data import canonicalize


def food_intent_to_parsed(intent: FoodIntent, facts: list[HardFact]) -> ParsedFoodMessage:
    items: list[ParsedFoodItem] = []
    single_entry = len(intent.entries) == 1

    for entry in intent.entries:
        quantity = _enforced_quantity(entry, facts, single_entry)
        name = canonicalize(entry.name)
        unit = _normalized_entry_unit(name, entry.unit)
        notes = _notes_for_entry(entry)

        items.append(
            ParsedFoodItem(
                name=name,
                quantity=quantity,
                unit=unit,
                role="main",
                notes=notes,
                modifiers=entry.modifiers,
                confidence=_clamp(entry.confidence),
            )
        )

        for component in entry.components:
            amount_value, amount_unit = _component_amount(component.amount_value, component.amount_unit)
            items.append(
                ParsedFoodItem(
                    name=canonicalize(component.name),
                    quantity=amount_value,
                    unit=amount_unit,
                    role="component" if amount_value is None else "main",
                    parent_name=name,
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


def _component_amount(value: float | None, unit: str) -> tuple[float | None, str]:
    if value is None:
        return None, "unknown"
    return value, unit


def _normalized_entry_unit(name: str, unit: str) -> str:
    if name in {"Cappuccino", "Kaffee", "Espresso"} and unit in {"piece", "portion", "unknown"}:
        return "cup"
    return unit


def _notes_for_entry(entry: FoodIntentEntry) -> str | None:
    values = []
    if entry.portion_size != "unknown":
        values.append(entry.portion_size)
    values.extend(entry.modifiers)
    return "; ".join(values) if values else None


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
