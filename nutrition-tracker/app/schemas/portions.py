from __future__ import annotations

from pydantic import BaseModel, Field


class ResolvedPortion(BaseModel):
    item_name: str
    grams: float | None = None
    ml: float | None = None
    default_kcal: float | None = None
    confidence: float
    was_estimated: bool
    needs_clarification: bool = False
    options: list[dict] = Field(default_factory=list)
