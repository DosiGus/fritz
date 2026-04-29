"""Tests for portion_engine. Runs without DB by passing user_id=None and db=None."""

import pytest

from app.schemas.parsed_food import ParsedFoodItem
from app.services.portion_engine import resolve_portion


def _item(**kwargs):
    return ParsedFoodItem(**{"name": "X", "confidence": 0.9, "unit": "unknown", **kwargs})


class TestExplicitQuantity:
    def test_grams_pass_through(self):
        portion = resolve_portion(_item(name="Skyr", quantity=250, unit="g", confidence=0.95))
        assert portion.grams == 250
        assert portion.was_estimated is False
        assert portion.confidence >= 0.9

    def test_ml_with_density(self):
        portion = resolve_portion(_item(name="Milch", quantity=500, unit="ml", confidence=0.95))
        assert portion.ml == 500
        # Milk density 1.03 → 515g
        assert portion.grams == pytest.approx(515, rel=0.05)
        assert portion.was_estimated is False

    def test_kg_converted(self):
        portion = resolve_portion(_item(name="Reis", quantity=1, unit="kg", confidence=0.95))
        assert portion.grams == 1000


class TestPortionRules:
    def test_banana_uses_default_grams(self):
        portion = resolve_portion(_item(name="Banane", quantity=1, unit="piece", confidence=0.9))
        assert portion.grams == 120
        assert portion.was_estimated is True

    def test_two_eggs_scaled(self):
        portion = resolve_portion(_item(name="Ei", quantity=2, unit="piece", confidence=0.9))
        assert portion.grams == 120  # 2 × 60
        assert portion.was_estimated is True

    def test_doener_uses_default_kcal(self):
        portion = resolve_portion(_item(name="Döner", quantity=1, unit="piece", confidence=0.7))
        assert portion.default_kcal == 650
        assert portion.grams is None
        assert portion.was_estimated is True

    def test_mayo_tbsp_uses_15g_default(self):
        portion = resolve_portion(_item(name="Mayo", quantity=1, unit="tbsp", confidence=0.85))
        assert portion.grams == 15
        assert portion.was_estimated is True


class TestLLMSuppliedOptions:
    def test_options_carried_through_when_clarification_requested(self):
        item = _item(
            name="Bowl",
            unit="bowl",
            confidence=0.4,
            needs_clarification=True,
            options=[{"label": "Reis + Hähnchen", "default_kcal": 700}],
        )
        portion = resolve_portion(item)
        assert portion.needs_clarification is True
        assert portion.options[0]["label"] == "Reis + Hähnchen"


class TestUnresolvable:
    def test_unknown_food_unknown_unit_marks_clarification(self):
        portion = resolve_portion(
            _item(name="Wundermittel", quantity=None, unit="unknown", confidence=0.3)
        )
        assert portion.needs_clarification is True
        labels = [option.get("label") for option in portion.options]
        assert labels[:3] == ["Klein", "Normal", "Groß"]
        assert any(option.get("type") == "custom" for option in portion.options)
