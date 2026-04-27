"""Tests for confidence_engine.decide. Verifies the threshold ladder and the
clarification-priority rule."""

import pytest

from app.schemas.nutrition import NutritionMatch
from app.schemas.portions import ResolvedPortion
from app.services.confidence_engine import decide


def _portion(confidence=0.9, needs_clarification=False, options=None, default_kcal=None, grams=None):
    return ResolvedPortion(
        item_name="x",
        grams=grams,
        default_kcal=default_kcal,
        confidence=confidence,
        was_estimated=grams is None and default_kcal is None,
        needs_clarification=needs_clarification,
        options=options or [],
    )


def _match(confidence=0.9):
    return NutritionMatch(canonical_name="x", source="test", confidence=confidence)


class TestThresholdLadder:
    def test_high_confidence_direct_save(self):
        decision = decide([_portion(confidence=0.95, grams=250)], [_match(0.95)])
        assert decision.action == "direct_save"

    def test_medium_confidence_save_as_estimate(self):
        decision = decide([_portion(confidence=0.75, grams=180)], [_match(0.85)])
        assert decision.action == "save_as_estimate"

    def test_low_medium_short_clarification(self):
        # No clarification flag, but mean below 0.70 falls into ask_short.
        decision = decide([_portion(confidence=0.55, grams=100)], [_match(0.95)])
        assert decision.action == "ask_short_clarification"

    def test_very_low_detailed_clarification(self):
        decision = decide([_portion(confidence=0.30, grams=50)], [_match(0.30)])
        assert decision.action == "ask_detailed_clarification"


class TestClarificationFlag:
    def test_portion_clarification_short(self):
        decision = decide(
            [_portion(confidence=0.5, needs_clarification=True, options=[
                {"label": "Klein", "grams": 250},
                {"label": "Normal", "grams": 350},
            ])],
            [None],
        )
        assert decision.action == "ask_short_clarification"

    def test_meal_variant_routes_to_detailed(self):
        decision = decide(
            [_portion(confidence=0.4, needs_clarification=True, options=[
                {"label": "Reis + Hähnchen", "default_kcal": 700},
                {"label": "Salat + Hähnchen", "default_kcal": 450},
            ])],
            [None],
        )
        assert decision.action == "ask_detailed_clarification"


class TestEmpty:
    def test_no_items_detailed_clarification(self):
        decision = decide([], [])
        assert decision.action == "ask_detailed_clarification"


class TestDefaultKcalFallback:
    def test_default_kcal_keeps_portion_confidence(self):
        # Döner: default_kcal=650 with confidence 0.70, no nutrition match needed.
        decision = decide([_portion(confidence=0.70, default_kcal=650)], [None])
        assert decision.action == "save_as_estimate"
        assert decision.confidence == pytest.approx(0.70, abs=0.05)
