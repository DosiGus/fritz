from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


MealType = Literal["breakfast", "lunch", "dinner", "snack", "unknown"]
IntentUnit = Literal["g", "kg", "ml", "l", "piece", "slice", "tbsp", "tsp", "portion", "plate", "bowl", "glass", "cup", "unknown"]
PortionSize = Literal["small", "medium", "large", "unknown"]


class FoodIntentComponent(BaseModel):
    name: str
    amount_value: float | None = None
    amount_unit: IntentUnit = "unknown"
    portion_hint: str | None = None
    role: Literal["base", "component", "topping", "sauce", "modifier"] = "component"
    confidence: float = 0.0


class FoodIntentEntry(BaseModel):
    type: Literal["single", "composite"] = "single"
    name: str
    quantity: float | None = None
    unit: IntentUnit = "unknown"
    portion_size: PortionSize = "unknown"
    components: list[FoodIntentComponent] = Field(default_factory=list)
    modifiers: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class FoodIntent(BaseModel):
    meal_type: MealType = "unknown"
    entries: list[FoodIntentEntry] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    confidence: float = 0.0


FOOD_INTENT_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["meal_type", "entries", "uncertainties", "confidence"],
    "properties": {
        "meal_type": {"type": "string", "enum": ["breakfast", "lunch", "dinner", "snack", "unknown"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "type",
                    "name",
                    "quantity",
                    "unit",
                    "portion_size",
                    "components",
                    "modifiers",
                    "confidence",
                ],
                "properties": {
                    "type": {"type": "string", "enum": ["single", "composite"]},
                    "name": {"type": "string"},
                    "quantity": {"type": ["number", "null"]},
                    "unit": {
                        "type": "string",
                        "enum": ["g", "kg", "ml", "l", "piece", "slice", "tbsp", "tsp", "portion", "plate", "bowl", "glass", "cup", "unknown"],
                    },
                    "portion_size": {"type": "string", "enum": ["small", "medium", "large", "unknown"]},
                    "modifiers": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "components": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "name",
                                "amount_value",
                                "amount_unit",
                                "portion_hint",
                                "role",
                                "confidence",
                            ],
                            "properties": {
                                "name": {"type": "string"},
                                "amount_value": {"type": ["number", "null"]},
                                "amount_unit": {
                                    "type": "string",
                                    "enum": ["g", "kg", "ml", "l", "piece", "slice", "tbsp", "tsp", "portion", "plate", "bowl", "glass", "cup", "unknown"],
                                },
                                "portion_hint": {"type": ["string", "null"]},
                                "role": {"type": "string", "enum": ["base", "component", "topping", "sauce", "modifier"]},
                                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            },
                        },
                    },
                },
            },
        },
    },
}
