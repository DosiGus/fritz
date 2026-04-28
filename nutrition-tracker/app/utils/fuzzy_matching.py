from __future__ import annotations

from thefuzz import fuzz


def best_match(query: str, candidates: list[str], threshold: int = 70) -> tuple[str, int] | None:
    """Return (best_candidate, score) or None if no match above threshold."""
    if not candidates:
        return None

    best: tuple[str, int] | None = None
    for candidate in candidates:
        score = fuzz.token_sort_ratio(query.lower(), candidate.lower())
        if score >= threshold:
            if best is None or score > best[1]:
                best = (candidate, score)
    return best


def score(a: str, b: str) -> int:
    return fuzz.token_sort_ratio(a.lower(), b.lower())
