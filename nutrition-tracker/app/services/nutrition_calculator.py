from __future__ import annotations

from app.schemas.nutrition import NutritionMatch, NutritionSummary


def calculate_for_item(match: NutritionMatch, grams: float) -> dict:
    """Returns kcal, protein, carbs, fat for the given gram amount."""
    factor = grams / 100.0
    return {
        "kcal": round((match.kcal_100g or 0) * factor, 1),
        "protein": round((match.protein_100g or 0) * factor, 1),
        "carbs": round((match.carbs_100g or 0) * factor, 1),
        "fat": round((match.fat_100g or 0) * factor, 1),
    }


def sum_items(items: list[dict]) -> NutritionSummary:
    return NutritionSummary(
        total_kcal=round(sum(i.get("kcal", 0) for i in items), 1),
        total_protein=round(sum(i.get("protein", 0) for i in items), 1),
        total_carbs=round(sum(i.get("carbs", 0) for i in items), 1),
        total_fat=round(sum(i.get("fat", 0) for i in items), 1),
    )
