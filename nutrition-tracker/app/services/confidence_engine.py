from __future__ import annotations

from app.schemas.bot_responses import Decision
from app.schemas.nutrition import NutritionMatch
from app.schemas.portions import ResolvedPortion


def decide(portions: list[ResolvedPortion], matches: list[NutritionMatch | None]) -> Decision:
    """Aggregate portion and nutrition confidence into a save/clarify decision."""
    if not portions:
        return Decision(
            action="ask_detailed_clarification",
            confidence=0.0,
            reason="no_items",
        )

    item_scores = _item_scores(portions, matches)
    confidence = round(sum(item_scores) / len(item_scores), 2)
    needs_clarification = any(portion.needs_clarification for portion in portions)

    if needs_clarification:
        action = (
            "ask_detailed_clarification"
            if confidence < 0.50 or _needs_detailed_clarification(portions)
            else "ask_short_clarification"
        )
        return Decision(
            action=action,
            confidence=confidence,
            reason="portion_or_match_needs_clarification",
        )

    if confidence >= 0.85:
        action = "direct_save"
    elif confidence >= 0.70:
        action = "save_as_estimate"
    elif confidence >= 0.50:
        action = "ask_short_clarification"
    else:
        action = "ask_detailed_clarification"

    post_save_action = (
        "ask_save_to_memory"
        if action == "save_as_estimate" and _has_memory_worthy_estimate(portions)
        else None
    )

    return Decision(
        action=action,
        confidence=confidence,
        reason=_reason_for_action(action),
        post_save_action=post_save_action,
    )


def _has_memory_worthy_estimate(portions: list[ResolvedPortion]) -> bool:
    """A grams/ml estimate from a container/cup phrase is worth remembering.

    default_kcal-only estimates (Döner, Dönerbox) cannot be improved by
    storing a per-user gram value, so we don't ask.
    """
    for portion in portions:
        if not portion.was_estimated:
            continue
        if portion.default_kcal is not None:
            continue
        if portion.grams is None and portion.ml is None:
            continue
        return True
    return False


def _item_scores(
    portions: list[ResolvedPortion],
    matches: list[NutritionMatch | None],
) -> list[float]:
    scores = []
    for idx, portion in enumerate(portions):
        match = matches[idx] if idx < len(matches) else None
        nutrition_score = match.confidence if match else _nutrition_fallback_confidence(portion)
        scores.append(round(min(portion.confidence, nutrition_score), 2))
    return scores


def _nutrition_fallback_confidence(portion: ResolvedPortion) -> float:
    if portion.default_kcal is not None:
        return portion.confidence
    if portion.needs_clarification:
        return portion.confidence
    return 0.50


def _needs_detailed_clarification(portions: list[ResolvedPortion]) -> bool:
    for portion in portions:
        labels = {str(option.get("label", "")).lower() for option in portion.options}
        if {"reis + hähnchen", "salat + hähnchen"} & labels:
            return True
    return False


def _reason_for_action(action: str) -> str:
    return {
        "direct_save": "high_confidence",
        "save_as_estimate": "medium_confidence_estimate",
        "ask_short_clarification": "medium_low_confidence",
        "ask_detailed_clarification": "low_confidence",
    }[action]
