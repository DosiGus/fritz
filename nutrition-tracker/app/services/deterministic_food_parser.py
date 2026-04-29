from __future__ import annotations

import re
from statistics import mean

from app.schemas.parsed_food import ParsedFoodItem, ParsedFoodMessage
from app.services.hard_fact_extractor import HardFact
from app.utils.text_numbers import parse_number
from app.utils.units import normalize_unit


_AMOUNT_RE = re.compile(
    r"^(?P<quantity>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g|gr|gramm|ml|l)\s+(?P<food>.+)$",
    re.IGNORECASE,
)
_QUANTITY_UNIT_RE = re.compile(
    r"^(?P<quantity>\d+(?:[.,]\d+)?|[A-Za-zÄÖÜäöüß]+)\s+"
    r"(?P<unit>stück|stk\.?|scheibe|scheiben|glas|tasse|becher|teller|schüssel|bowl|portion(?:en)?)\s+"
    r"(?P<food>.+)$",
    re.IGNORECASE,
)
_QUANTITY_FOOD_RE = re.compile(
    r"^(?P<quantity>\d+(?:[.,]\d+)?|[A-Za-zÄÖÜäöüß]+)\s+(?P<food>.+)$",
    re.IGNORECASE,
)

_COMPLEX_MARKERS = {
    " mit ",
    " dazu ",
    " extra ",
    " zusätzlich ",
    " zusaetzlich ",
    " separat ",
    " aus ",
}

_FILLER_PREFIX_RE = re.compile(
    r"^(?:ich\s+hatt(?:e|est)?\s+|hatte\s+ich\s+|zum\s+\w+\s+|heute\s+|gerade\s+)+",
    re.IGNORECASE,
)

_CANONICAL_FOODS = {
    "apfel": "Apfel",
    "banane": "Banane",
    "bananen": "Banane",
    "brot": "Brot",
    "cappuccino": "Cappuccino",
    "ei": "Ei",
    "eier": "Ei",
    "haferflocken": "Haferflocken",
    "kaffee": "Kaffee",
    "magerquark": "Magerquark",
    "milch": "Milch",
    "orange": "Orange",
    "pasta": "Pasta",
    "reis": "Reis",
    "skyr": "Skyr",
    "toast": "Toast",
    "whey": "Whey Protein",
    "whey protein": "Whey Protein",
}

_COUNT_UNITS_BY_FOOD = {
    "Cappuccino": "cup",
    "Kaffee": "cup",
}


def parse_deterministic_food(text: str, facts: list[HardFact]) -> ParsedFoodMessage | None:
    """Parse only high-confidence simple food logs without network or LLM calls."""
    segments = _segments(text)
    if not segments:
        return None

    items = []
    for segment in segments:
        item = _parse_segment(segment)
        if item is None:
            return None
        items.append(item)

    confidence = round(mean([item.confidence for item in items]), 2)
    return ParsedFoodMessage(
        meal_type=_meal_type(facts),
        items=items,
        overall_confidence=confidence,
        llm_called=False,
    )


def _segments(text: str) -> list[str]:
    cleaned = _FILLER_PREFIX_RE.sub("", text.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    if _has_complex_marker(cleaned):
        return []

    parts = re.split(r"\s*,\s*|\s+\bund\b\s+", cleaned, flags=re.IGNORECASE)
    return [part.strip(" .") for part in parts if part.strip(" .")]


def _has_complex_marker(text: str) -> bool:
    padded = f" {text.lower()} "
    return any(marker in padded for marker in _COMPLEX_MARKERS)


def _parse_segment(segment: str) -> ParsedFoodItem | None:
    segment = _strip_meal_context(segment)

    amount = _AMOUNT_RE.match(segment)
    if amount:
        quantity = _parse_float(amount.group("quantity"))
        food = _canonical_food(amount.group("food"), allow_unknown=True)
        if quantity is None or food is None:
            return None
        return ParsedFoodItem(
            name=food,
            quantity=quantity,
            unit=normalize_unit(amount.group("unit")),
            confidence=0.95,
        )

    quantity_unit = _QUANTITY_UNIT_RE.match(segment)
    if quantity_unit:
        quantity = _parse_quantity(quantity_unit.group("quantity"))
        food = _canonical_food(quantity_unit.group("food"), allow_unknown=False)
        if quantity is None or food is None:
            return None
        return ParsedFoodItem(
            name=food,
            quantity=quantity,
            unit=normalize_unit(quantity_unit.group("unit")),
            confidence=0.88,
        )

    quantity_food = _QUANTITY_FOOD_RE.match(segment)
    if quantity_food:
        quantity = _parse_quantity(quantity_food.group("quantity"))
        food = _canonical_food(quantity_food.group("food"), allow_unknown=True)
        if quantity is None or food is None:
            return None
        return ParsedFoodItem(
            name=food,
            quantity=quantity,
            unit=_COUNT_UNITS_BY_FOOD.get(food, "piece"),
            confidence=0.86 if food in _CANONICAL_FOODS.values() else 0.78,
        )

    return None


def _strip_meal_context(segment: str) -> str:
    value = segment.strip()
    value = re.sub(
        r"^(?:zum\s+)?(?:frühstück|mittagessen|abendessen|snack)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\s+zum\s+(?:frühstück|mittagessen|abendessen|snack)$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"^(?:frühstück|mittagessen|abendessen|snack)\s+", "", value, flags=re.IGNORECASE)
    return value.strip()


def _canonical_food(raw: str, allow_unknown: bool) -> str | None:
    normalized = _normalize_food_text(raw)
    if not normalized:
        return None
    known = _CANONICAL_FOODS.get(normalized)
    if known:
        return known
    if not allow_unknown:
        return None
    return " ".join(part.capitalize() for part in normalized.split())


def _normalize_food_text(raw: str) -> str:
    value = raw.strip().strip(".")
    value = re.sub(r"^(?:eine?|einen|zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn)\s+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value)
    return value.lower()


def _parse_quantity(raw: str) -> float | None:
    parsed = _parse_float(raw)
    if parsed is not None:
        return parsed
    return parse_number(raw.lower())


def _parse_float(raw: str) -> float | None:
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return None


def _meal_type(facts: list[HardFact]) -> str:
    for fact in facts:
        if fact.type == "meal_type" and isinstance(fact.value, str):
            return fact.value
    return "unknown"
