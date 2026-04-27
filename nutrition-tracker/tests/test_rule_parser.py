"""Focused tests for rule_parser. Goldstandard inputs are covered separately;
this file pins down edge cases (German number words, kg/l conversion, multi-item
splits, hallucination-resistance triggers)."""

import pytest

from app.services.rule_parser import (
    has_meal_verb,
    parse,
    unused_span_chars,
)


class TestExplicitWeights:
    def test_grams(self):
        msg = parse("250g Skyr")
        assert len(msg.items) == 1
        assert msg.items[0].name == "Skyr"
        assert msg.items[0].quantity == 250
        assert msg.items[0].unit == "g"
        assert msg.items[0].confidence >= 0.9

    def test_kg_normalized_to_g(self):
        msg = parse("1.5kg Reis")
        assert msg.items[0].unit == "g"
        assert msg.items[0].quantity == 1500

    def test_ml(self):
        msg = parse("500ml Milch")
        assert msg.items[0].unit == "ml"
        assert msg.items[0].quantity == 500

    def test_l_normalized_to_ml(self):
        msg = parse("0.5l Wasser")
        assert msg.items[0].unit == "ml"
        assert msg.items[0].quantity == 500

    def test_comma_decimal(self):
        msg = parse("1,5kg Reis")
        assert msg.items[0].quantity == 1500


class TestPieces:
    def test_one_banana(self):
        msg = parse("1 Banane")
        assert msg.items[0].name == "Banane"
        assert msg.items[0].unit == "piece"
        assert msg.items[0].quantity == 1

    def test_two_eggs(self):
        msg = parse("2 Eier")
        assert msg.items[0].name == "Ei"
        assert msg.items[0].quantity == 2

    def test_german_number_word(self):
        msg = parse("zwei Eier")
        assert msg.items[0].name == "Ei"
        assert msg.items[0].quantity == 2

    def test_one_doener_uses_kcal_default(self):
        msg = parse("1 Döner")
        assert msg.items[0].name == "Döner"
        assert msg.items[0].confidence == pytest.approx(0.70, abs=0.01)


class TestSlices:
    def test_one_slice(self):
        msg = parse("eine Scheibe Brot")
        assert msg.items[0].name == "Brot"
        assert msg.items[0].unit == "slice"
        assert msg.items[0].quantity == 1


class TestContainers:
    def test_pasta_plate_keeps_low_confidence(self):
        msg = parse("ein Teller Pasta")
        assert msg.items[0].name == "Pasta"
        assert msg.items[0].unit == "plate"
        # Pasta plate is sized → ambiguous → low confidence so portion engine
        # generates options.
        assert msg.items[0].confidence <= 0.55

    def test_haferflocken_bowl(self):
        msg = parse("eine Schüssel Haferflocken")
        assert msg.items[0].name == "Haferflocken"
        assert msg.items[0].unit == "bowl"

    def test_bowl_with_ingredient_marks_clarification(self):
        msg = parse("eine Bowl mit Hähnchen")
        item = msg.items[0]
        assert item.name == "Bowl"
        assert item.unit == "bowl"
        assert item.needs_clarification is True
        assert item.notes and "Hähnchen" in item.notes


class TestMultiItem:
    def test_three_items_comma_und(self):
        msg = parse("250g Skyr, 1 Banane und 30g Whey")
        names = [i.name for i in msg.items]
        assert names == ["Skyr", "Banane", "Whey Protein"]

    def test_two_items_und_only(self):
        msg = parse("zwei Eier und eine Scheibe Brot")
        assert [i.name for i in msg.items] == ["Ei", "Brot"]


class TestCompoundFoods:
    def test_doenerbox_pommes(self):
        msg = parse("Dönerbox mit Pommes")
        assert len(msg.items) == 1
        assert msg.items[0].name == "Dönerbox Pommes"

    def test_chicken_bowl_reis(self):
        msg = parse("Chicken Bowl mit Reis")
        assert len(msg.items) == 1
        assert msg.items[0].name == "Chicken Bowl Reis"


class TestSplitOnMit:
    def test_kaffee_mit_milch_splits_into_two_items(self):
        msg = parse("ein Kaffee mit Milch")
        assert len(msg.items) == 2
        assert msg.items[0].name == "Kaffee"
        assert msg.items[1].name == "Milch"
        assert msg.items[1].quantity is None
        assert msg.items[1].needs_clarification is True


class TestMealVerbHelper:
    def test_detects_hatte(self):
        assert has_meal_verb("Ich hatte ein Müsli")

    def test_detects_gegessen(self):
        assert has_meal_verb("habe Pasta gegessen")

    def test_no_verb(self):
        assert not has_meal_verb("250g Skyr")


class TestUnusedSpanChars:
    def test_clean_input_has_no_leftover(self):
        msg = parse("250g Skyr")
        assert unused_span_chars("250g Skyr", msg.items) == 0

    def test_extra_words_count_as_unused(self):
        msg = parse("ein Teller Pasta")
        # Filler words (article, container) are stripped → no unused leftover.
        assert unused_span_chars("ein Teller Pasta", msg.items) == 0
