from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ParsedFoodItem(BaseModel):
    name: str
    quantity: float | None = None
    unit: str = "unknown"
    role: Literal["main", "component", "modifier", "attribute"] = "main"
    parent_name: str | None = None
    preparation: str | None = "unknown"
    notes: str | None = None
    modifiers: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    needs_clarification: bool = False
    options: list[dict] = Field(default_factory=list)


class ParsedFoodMessage(BaseModel):
    meal_type: str = "unknown"
    items: list[ParsedFoodItem] = Field(default_factory=list)
    overall_confidence: float = 0.0
    llm_called: bool = False
