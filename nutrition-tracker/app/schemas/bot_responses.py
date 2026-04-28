from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Decision(BaseModel):
    action: Literal[
        "direct_save",
        "save_as_estimate",
        "ask_short_clarification",
        "ask_detailed_clarification",
    ]
    confidence: float
    reason: str
    post_save_action: Literal["ask_save_to_memory"] | None = None


class LoggedItemSummary(BaseModel):
    name: str
    grams: float | None = None
    ml: float | None = None
    kcal: float | None = None
    was_estimated: bool = False


class BotResponse(BaseModel):
    text: str
    decision: Decision | None = None
    inline_keyboard: list[list[dict]] | None = None
    logged_items: list[LoggedItemSummary] = Field(default_factory=list)
