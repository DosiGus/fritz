from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.repositories.portions import UserPortionMemoryRepository
from app.schemas.parsed_food import ParsedFoodItem
from app.utils.fuzzy_matching import score


def _normalize_phrase(phrase: str) -> str:
    return " ".join(phrase.strip().lower().split())


def memory_phrase(item: ParsedFoodItem | dict, unit: str | None = None) -> str:
    """Build the canonical memory phrase for a parsed item.

    Lookup and record must agree on the phrase shape — otherwise the second
    occurrence of "eine Schüssel Haferflocken" would not retrieve what the
    first one stored.
    """
    if isinstance(item, dict):
        name = item.get("name") or item.get("item_name") or ""
        notes = item.get("notes")
        item_unit = unit if unit is not None else (item.get("unit") or "unknown")
    else:
        name = item.name
        notes = item.notes
        item_unit = unit if unit is not None else item.unit

    parts: list[str] = []
    if item_unit and item_unit != "unknown":
        parts.append(item_unit)
    parts.append(name)
    if notes:
        parts.append(notes)
    return " ".join(parts)


def lookup(phrase: str, user_id: uuid.UUID, db: Session, food_name: str | None = None) -> dict | None:
    """Return the best personal portion memory for a phrase.

    Exact phrase matches win. Fuzzy matches are accepted only when they are
    strong enough to avoid silently applying an unrelated personal habit.
    """
    normalized = _normalize_phrase(phrase)
    if not normalized:
        return None

    repo = UserPortionMemoryRepository(db)
    exact = repo.get_by_phrase(user_id, normalized)
    if exact:
        repo.increment_usage(exact)
        return {
            "phrase": exact.phrase,
            "food_name": exact.food_name,
            "grams": float(exact.grams) if exact.grams is not None else None,
            "ml": float(exact.ml) if exact.ml is not None else None,
            "confidence": 0.95,
        }

    best = None
    best_score = 0
    for memory in repo.get_for_user(user_id):
        candidates = [memory.phrase]
        if memory.food_name:
            candidates.append(memory.food_name)
        candidate_score = max(score(normalized, candidate) for candidate in candidates)
        if food_name and memory.food_name and memory.food_name.lower() == food_name.lower():
            candidate_score = max(candidate_score, 88)
        if candidate_score > best_score:
            best = memory
            best_score = candidate_score

    if not best or best_score < 82:
        return None

    repo.increment_usage(best)
    return {
        "phrase": best.phrase,
        "food_name": best.food_name,
        "grams": float(best.grams) if best.grams is not None else None,
        "ml": float(best.ml) if best.ml is not None else None,
        "confidence": round(best_score / 100, 2),
    }


def record(phrase: str, food_name: str, grams: float | None, ml: float | None, user_id: uuid.UUID, db: Session) -> None:
    normalized = _normalize_phrase(phrase)
    if not normalized:
        return

    repo = UserPortionMemoryRepository(db)
    existing = repo.get_by_phrase(user_id, normalized)
    if existing:
        existing.food_name = food_name
        existing.grams = grams
        existing.ml = ml
        repo.increment_usage(existing)
        return

    repo.create(
        user_id=user_id,
        phrase=normalized,
        food_name=food_name,
        grams=grams,
        ml=ml,
    )
