"""Tests for clarification helpers that don't require a real database session."""

import pytest

from app.services.clarification_service import (
    _keyboard_for_options,
    _option_from_callback,
    _parse_amount,
    _question_type,
    _meal_variant_name,
)


class TestQuestionType:
    def test_meal_variant_detected(self):
        options = [{"label": "Reis + Hähnchen"}, {"label": "Salat + Hähnchen"}]
        assert _question_type(options) == "meal_variant"

    def test_custom_amount_detected(self):
        options = [{"label": "Schuss", "ml": 10}, {"label": "Etwas", "ml": 30}]
        assert _question_type(options) == "custom_amount"

    def test_portion_size_default(self):
        options = [{"label": "Klein", "grams": 250}, {"label": "Normal", "grams": 350}]
        assert _question_type(options) == "portion_size"


class TestKeyboardLayout:
    def test_groups_options_into_rows_of_two(self):
        options = [{"label": f"O{i}"} for i in range(5)]
        keyboard = _keyboard_for_options(options)
        # 5 options → 3 rows of buttons + 1 cancel row.
        assert len(keyboard) == 4
        assert keyboard[-1][0]["callback_data"] == "cancel"


class TestParseAmount:
    def test_grams(self):
        assert _parse_amount("80g")["grams"] == 80
        assert _parse_amount("80 g")["grams"] == 80

    def test_ml(self):
        assert _parse_amount("125ml")["ml"] == 125

    def test_l_to_ml(self):
        assert _parse_amount("0.5l")["ml"] == 500

    def test_invalid(self):
        assert _parse_amount("ein bisschen") is None


class TestOptionFromCallback:
    def test_milk_callback(self):
        option = _option_from_callback("milk:30", payload={})
        assert option == {"label": "30ml", "ml": 30}

    def test_milk_custom(self):
        option = _option_from_callback("milk:custom", payload={})
        assert option == {"type": "custom"}

    def test_portion_size_small(self):
        option = _option_from_callback("portion:Pasta:small", payload={})
        assert option == {"label": "small", "grams": 250}

    def test_unknown_returns_none(self):
        assert _option_from_callback("unknown:thing", payload={}) is None


class TestMealVariantName:
    def test_known_label(self):
        assert _meal_variant_name({"label": "Reis + Hähnchen"}) == "Chicken Bowl Reis"

    def test_unknown_label(self):
        assert _meal_variant_name({"label": "Andere"}) is None
