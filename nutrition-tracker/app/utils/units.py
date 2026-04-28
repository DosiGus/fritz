"""Unit normalization for food quantity parsing."""

from __future__ import annotations

# Maps raw unit strings (lowercase, stripped) → normalized unit token
_UNIT_ALIASES: dict[str, str] = {
    # Weight
    "g": "g",
    "gr": "g",
    "gramm": "g",
    "gram": "g",
    "grams": "g",
    "kg": "kg",
    "kilogramm": "kg",
    "kilo": "kg",
    # Volume
    "ml": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "l": "l",
    "liter": "l",
    "liters": "l",
    "litre": "l",
    # Count
    "stück": "piece",
    "stk": "piece",
    "stk.": "piece",
    "piece": "piece",
    "pieces": "piece",
    "portion": "portion",
    "portionen": "portion",
    "portionsweise": "portion",
    # Bread
    "scheibe": "slice",
    "scheiben": "slice",
    "slice": "slice",
    "slices": "slice",
    # Spoon
    "el": "tbsp",
    "esslöffel": "tbsp",
    "tl": "tsp",
    "teelöffel": "tsp",
    "tbsp": "tbsp",
    "tsp": "tsp",
    # Container
    "glas": "glass",
    "glasses": "glass",
    "glass": "glass",
    "tasse": "cup",
    "cup": "cup",
    "becher": "cup",
    "teller": "plate",
    "plate": "plate",
    "schüssel": "bowl",
    "bowl": "bowl",
}

_GRAMS_PER_UNIT: dict[str, float] = {
    "kg": 1000.0,
}

_ML_PER_UNIT: dict[str, float] = {
    "l": 1000.0,
}


def normalize_unit(raw: str) -> str:
    """Normalize a raw unit string to a canonical token."""
    return _UNIT_ALIASES.get(raw.strip().lower(), raw.strip().lower())


def to_grams(quantity: float, unit: str) -> float | None:
    """Convert quantity+unit to grams. Returns None if unit is non-weight."""
    norm = normalize_unit(unit)
    if norm == "g":
        return quantity
    if norm in _GRAMS_PER_UNIT:
        return quantity * _GRAMS_PER_UNIT[norm]
    return None


def to_ml(quantity: float, unit: str) -> float | None:
    """Convert quantity+unit to millilitres. Returns None if unit is non-volume."""
    norm = normalize_unit(unit)
    if norm == "ml":
        return quantity
    if norm in _ML_PER_UNIT:
        return quantity * _ML_PER_UNIT[norm]
    return None


def is_weight_unit(unit: str) -> bool:
    return normalize_unit(unit) in ("g", "kg")


def is_volume_unit(unit: str) -> bool:
    return normalize_unit(unit) in ("ml", "l")
