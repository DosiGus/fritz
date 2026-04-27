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

    def test_chicken_bowl_reis_uses_kcal(self):
        portion = resolve_portion(
            _item(name="Chicken Bowl Reis", quantity=1, unit="portion", confidence=0.75)
        )
        assert portion.default_kcal == 700


class TestSizedVariants:
    def test_pasta_plate_emits_size_options(self):
        portion = resolve_portion(_item(name="Pasta", quantity=1, unit="plate", confidence=0.5))
        assert portion.needs_clarification is True
        labels = [option["label"] for option in portion.options]
        assert labels[:3] == ["Klein", "Normal", "Groß"]
        assert labels[-1] == "Eigene Menge"


class TestSpecialClarification:
    def test_bowl_with_ingredient_emits_meal_variants(self):
        portion = resolve_portion(
            _item(name="Bowl", quantity=1, unit="bowl", notes="mit Hähnchen", confidence=0.4)
        )
        assert portion.needs_clarification is True
        labels = [option.get("label") for option in portion.options]
        assert "Reis + Hähnchen" in labels
        assert "Salat + Hähnchen" in labels

    def test_milch_in_kaffee_emits_custom_amount_options(self):
        portion = resolve_portion(
            _item(name="Milch", quantity=None, unit="unknown", notes="in Kaffee", confidence=0.4)
        )
        assert portion.needs_clarification is True
        ml_values = [option.get("ml") for option in portion.options if "ml" in option]
        assert ml_values == [10, 30, 125]


class TestUnresolvable:
    def test_unknown_food_unknown_unit_marks_clarification(self):
        portion = resolve_portion(
            _item(name="Wundermittel", quantity=None, unit="unknown", confidence=0.3)
        )
        assert portion.needs_clarification is True
        assert any(option.get("type") == "custom" for option in portion.options)
