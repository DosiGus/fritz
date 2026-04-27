from typing import Literal

from pydantic import BaseModel, Field


class ParsedFoodItem(BaseModel):
    name: str
    quantity: float | None = None
    unit: str = "unknown"
    preparation: str | None = "unknown"
    notes: str | None = None
    confidence: float = 0.0
    needs_clarification: bool = False
    options: list[dict] = Field(default_factory=list)


class ParsedFoodMessage(BaseModel):
    meal_type: str = "unknown"
    items: list[ParsedFoodItem] = Field(default_factory=list)
    overall_confidence: float = 0.0
    llm_called: bool = False
