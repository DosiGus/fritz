from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.utils.text_numbers import parse_number
from app.utils.units import normalize_unit


@dataclass(frozen=True)
class HardFact:
    type: Literal["quantity", "amount", "portion_size", "meal_type", "separate_marker"]
    text: str
    value: float | str | None = None
    unit: str | None = None


_WORD_RE = re.compile(r"[A-Za-zÄÖÜäöüß]+|\d+(?:[.,]\d+)?")
_AMOUNT_RE = re.compile(r"(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g|ml|l)\b", re.IGNORECASE)


def extract_hard_facts(text: str) -> list[HardFact]:
    facts: list[HardFact] = []
    facts.extend(_extract_amounts(text))
    facts.extend(_extract_quantity_words(text))
    facts.extend(_extract_portion_sizes(text))
    facts.extend(_extract_meal_type(text))
    facts.extend(_extract_separate_markers(text))
    return facts


def _extract_amounts(text: str) -> list[HardFact]:
    facts = []
    for match in _AMOUNT_RE.finditer(text):
        value = float(match.group("num").replace(",", "."))
        unit = normalize_unit(match.group("unit").lower())
        if unit == "kg":
            value *= 1000
            unit = "g"
        elif unit == "l":
            value *= 1000
            unit = "ml"
        facts.append(HardFact(type="amount", text=match.group(0), value=value, unit=unit))
    return facts


def _extract_quantity_words(text: str) -> list[HardFact]:
    facts = []
    for token in _WORD_RE.findall(text):
        value = parse_number(token.lower())
        if value is not None:
            facts.append(HardFact(type="quantity", text=token, value=value))
    return facts


def _extract_portion_sizes(text: str) -> list[HardFact]:
    patterns = [
        ("small", r"\b(klein|kleine|kleinen|kleiner|bisschen|wenig|small)\b"),
        ("medium", r"\b(normal|normale|mittlere|mittel|medium)\b"),
        ("large", r"\b(groß|große|gross|grosse|viel|large)\b"),
    ]
    facts = []
    for value, pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            facts.append(HardFact(type="portion_size", text=value, value=value))
    return facts


def _extract_meal_type(text: str) -> list[HardFact]:
    patterns = [
        ("breakfast", r"\b(frühstück|fruehstueck|morgens)\b"),
        ("lunch", r"\b(mittag|mittagessen|mittags)\b"),
        ("dinner", r"\b(abendessen|abends|abend)\b"),
        ("snack", r"\b(snack|zwischenmahlzeit)\b"),
    ]
    for value, pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return [HardFact(type="meal_type", text=value, value=value)]
    return []


def _extract_separate_markers(text: str) -> list[HardFact]:
    return [
        HardFact(type="separate_marker", text=match.group(0), value=match.group(0).lower())
        for match in re.finditer(r"\b(extra|dazu|zusätzlich|zusaetzlich|separat)\b", text, re.IGNORECASE)
    ]
