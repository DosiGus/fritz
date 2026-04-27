"""Tests for nutrition_calculator: per-item kcal/macros and totals."""

import pytest

from app.schemas.nutrition import NutritionMatch
from app.services.nutrition_calculator import calculate_for_item, sum_items


def _match(**kwargs):
    return NutritionMatch(
        canonical_name=kwargs.get("name", "x"),
        kcal_100g=kwargs.get("kcal", 100),
        protein_100g=kwargs.get("protein", 10),
        carbs_100g=kwargs.get("carbs", 20),
        fat_100g=kwargs.get("fat", 5),
        source="test",
        confidence=0.9,
    )


class TestCalculateForItem:
    def test_doubles_at_200g(self):
        result = calculate_for_item(_match(kcal=100, protein=10, carbs=20, fat=5), 200)
        assert result == {"kcal": 200, "protein": 20, "carbs": 40, "fat": 10}

    def test_halves_at_50g(self):
        result = calculate_for_item(_match(kcal=100, protein=10, carbs=20, fat=5), 50)
        assert result["kcal"] == 50
        assert result["protein"] == 5

    def test_handles_missing_macros(self):
        match = NutritionMatch(canonical_name="x", kcal_100g=64, source="test", confidence=0.9)
        result = calculate_for_item(match, 250)
        assert result["kcal"] == pytest.approx(160, abs=1)
        assert result["protein"] == 0
        assert result["carbs"] == 0
        assert result["fat"] == 0


class TestSumItems:
    def test_totals(self):
        items = [
            {"kcal": 100, "protein": 10, "carbs": 5, "fat": 2},
            {"kcal": 250, "protein": 5, "carbs": 30, "fat": 8},
        ]
        summary = sum_items(items)
        assert summary.total_kcal == 350
        assert summary.total_protein == 15
        assert summary.total_carbs == 35
        assert summary.total_fat == 10

    def test_empty(self):
        summary = sum_items([])
        assert summary.total_kcal == 0
        assert summary.total_protein == 0
