from __future__ import annotations

from pydantic import BaseModel


class NutritionMatch(BaseModel):
    canonical_name: str
    kcal_100g: float | None = None
    protein_100g: float | None = None
    carbs_100g: float | None = None
    fat_100g: float | None = None
    source: str
    source_id: str | None = None
    confidence: float


class NutritionSummary(BaseModel):
    total_kcal: float
    total_protein: float
    total_carbs: float
    total_fat: float
