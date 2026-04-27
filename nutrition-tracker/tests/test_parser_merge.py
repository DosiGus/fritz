"""Tests for the merge spec between rule and LLM parsers."""

import pytest

from app.schemas.parsed_food import ParsedFoodItem, ParsedFoodMessage
from app.services.parser_merge import merge, should_call_llm


def _msg(items, conf=None):
    items = [ParsedFoodItem(**i) if not isinstance(i, ParsedFoodItem) else i for i in items]
    overall = (
        conf
        if conf is not None
        else (sum(i.confidence for i in items) / len(items) if items else 0.0)
    )
    return ParsedFoodMessage(items=items, overall_confidence=overall)


class TestShouldCallLlm:
    def test_skips_when_high_confidence(self):
        rule = _msg([{"name": "Skyr", "quantity": 250, "unit": "g", "confidence": 0.95}])
        assert should_call_llm("250g Skyr", rule) is False

    def test_calls_when_low_confidence(self):
        rule = _msg([{"name": "Bowl", "quantity": 1, "unit": "bowl", "confidence": 0.4,
                      "needs_clarification": True}])
        assert should_call_llm("eine Bowl mit Hähnchen", rule) is True

    def test_calls_when_no_items(self):
        rule = _msg([])
        assert should_call_llm("???", rule) is True

    def test_calls_when_unknown_unit_clarification(self):
        rule = _msg([
            {"name": "Kaffee", "quantity": 1, "unit": "cup", "confidence": 0.9},
            {"name": "Milch", "quantity": None, "unit": "unknown", "confidence": 0.4,
             "needs_clarification": True},
        ])
        assert should_call_llm("ein Kaffee mit Milch", rule) is True

    def test_pasta_plate_special_case_skips_llm(self):
        rule = _msg([{"name": "Pasta", "quantity": 1, "unit": "plate", "confidence": 0.5}])
        assert should_call_llm("ein Teller Pasta", rule) is False

    def test_meal_verb_lowers_threshold(self):
        # Use Skyr (not Pasta plate, which has its own LLM-skip special case).
        rule = _msg(
            [{"name": "Skyr", "quantity": 250, "unit": "g", "confidence": 0.8}],
            conf=0.8,
        )
        # "hatte" + confidence < 0.85 → call LLM.
        assert should_call_llm("Ich hatte 250g Skyr", rule) is True


class TestMergeHallucinationGuard:
    def test_blocks_llm_item_not_in_text(self):
        rule = _msg([{"name": "Skyr", "quantity": 250, "unit": "g", "confidence": 0.95}])
        llm = _msg([
            {"name": "Skyr", "quantity": 250, "unit": "g", "confidence": 0.9},
            {"name": "Pizza", "quantity": 1, "unit": "piece", "confidence": 0.7},  # hallucinated
        ])
        merged = merge(rule, llm, original_text="250g Skyr")
        assert [i.name for i in merged.items] == ["Skyr"]

    def test_keeps_grounded_llm_only_item(self):
        rule = _msg([])
        llm = _msg([{"name": "Skyr", "quantity": 250, "unit": "g", "confidence": 0.9}])
        merged = merge(rule, llm, original_text="250g Skyr")
        assert [i.name for i in merged.items] == ["Skyr"]


class TestMergeQuantityPriority:
    def test_rule_explicit_grams_beats_llm(self):
        rule = _msg([{"name": "Skyr", "quantity": 250, "unit": "g", "confidence": 0.95}])
        llm = _msg([{"name": "Skyr", "quantity": 200, "unit": "g", "confidence": 0.6}])
        merged = merge(rule, llm, original_text="250g Skyr")
        assert merged.items[0].quantity == 250

    def test_llm_fills_missing_rule_quantity(self):
        rule = _msg([{"name": "Banane", "quantity": None, "unit": "unknown", "confidence": 0.4}])
        llm = _msg([{"name": "Banane", "quantity": 1, "unit": "piece", "confidence": 0.8}])
        merged = merge(rule, llm, original_text="eine Banane")
        assert merged.items[0].quantity == 1

    def test_llm_called_flag_is_set(self):
        rule = _msg([{"name": "Skyr", "quantity": 250, "unit": "g", "confidence": 0.95}])
        llm = _msg([])
        merged = merge(rule, llm, original_text="250g Skyr")
        assert merged.llm_called is True
