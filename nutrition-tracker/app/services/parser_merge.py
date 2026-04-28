from __future__ import annotations

import re
import uuid
from statistics import mean

from Levenshtein import distance as levenshtein_distance
from sqlalchemy.orm import Session

from app.schemas.parsed_food import ParsedFoodItem, ParsedFoodMessage
from app.services.audit_service import AuditService
from app.services.rule_parser import has_meal_verb, unused_span_chars
from app.services.static_data import FOOD_ALIASES, PARSER_STOPWORDS, canonicalize

_EXPLICIT_WEIGHT_VOLUME_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(g|kg|ml|l)\b", re.IGNORECASE)
_SPECIFIC_PREPARATIONS = {"cooked", "grilled", "fried", "raw"}


def should_call_llm(text: str, rule_result: ParsedFoodMessage) -> bool:
    if _is_known_rule_clarification(rule_result):
        return False
    if any(item.needs_clarification and item.unit == "unknown" for item in rule_result.items):
        return True
    if rule_result.overall_confidence < 0.6:
        return True
    if not rule_result.items:
        return True
    if unused_span_chars(text, rule_result.items) > 8:
        return True
    if has_meal_verb(text) and rule_result.overall_confidence < 0.85:
        return True
    return False


def _is_known_rule_clarification(rule_result: ParsedFoodMessage) -> bool:
    if len(rule_result.items) != 1:
        return False
    item = rule_result.items[0]
    return item.name == "Pasta" and item.unit == "plate" and item.confidence >= 0.50


def merge(
    rule: ParsedFoodMessage,
    llm: ParsedFoodMessage,
    original_text: str,
    db: Session | None = None,
    user_id: uuid.UUID | None = None,
) -> ParsedFoodMessage:
    """Merge Rule and LLM parser outputs according to codex_agent_prompt.md."""
    rule_items = [_canonical_item(item) for item in rule.items]
    llm_items = []
    for item in llm.items:
        canonical = _canonical_item(item)
        if _llm_item_is_grounded(canonical, original_text):
            llm_items.append(canonical)
        else:
            _audit(
                db,
                user_id,
                "llm_hallucination_blocked",
                {"item_name": item.name, "original_text": original_text},
            )

    conflicts = 0
    merged: dict[str, ParsedFoodItem] = {}

    for item in rule_items:
        merged[_key(item.name)] = item

    for llm_item in llm_items:
        key = _key(llm_item.name)
        if key not in merged:
            merged[key] = llm_item
            continue

        merged_item, conflict = _merge_item(merged[key], llm_item, original_text, db, user_id)
        conflicts += int(conflict)
        merged[key] = merged_item

    items = list(merged.values())
    if _llm_should_win_multiword(rule_items, llm_items):
        items = _collapse_multiword(rule_items, llm_items)
        conflicts += 1

    overall = round(mean([item.confidence for item in items]), 2) if items else 0.0
    if conflicts:
        overall = max(0.0, round(overall - 0.05, 2))

    return ParsedFoodMessage(
        meal_type=llm.meal_type if llm.meal_type != "unknown" else rule.meal_type,
        items=items,
        overall_confidence=overall,
        llm_called=True,
    )


def mark_llm_skipped(
    rule: ParsedFoodMessage,
    db: Session | None = None,
    user_id: uuid.UUID | None = None,
    reason: str = "rule_confidence_sufficient",
) -> ParsedFoodMessage:
    rule.llm_called = False
    _audit(db, user_id, "llm_skipped", {"reason": reason, "rule": rule.model_dump()})
    return rule


def _merge_item(
    rule_item: ParsedFoodItem,
    llm_item: ParsedFoodItem,
    original_text: str,
    db: Session | None,
    user_id: uuid.UUID | None,
) -> tuple[ParsedFoodItem, bool]:
    conflict = False
    decision = "rule"
    reason = "rule_default"

    if _rule_has_explicit_weight_volume(rule_item, original_text):
        merged = rule_item.model_copy(deep=True)
        decision = "rule"
        reason = "rule_explicit_weight_volume"
    elif rule_item.quantity is not None and llm_item.quantity is None:
        merged = rule_item.model_copy(deep=True)
        decision = "rule"
        reason = "rule_explicit_quantity"
    elif rule_item.quantity is None and llm_item.quantity is not None:
        merged = llm_item.model_copy(deep=True)
        decision = "llm"
        reason = "llm_quantity_fills_missing_rule_quantity"
    elif _same_piece_value(rule_item, llm_item):
        merged = rule_item.model_copy(deep=True)
        decision = "rule"
        reason = "same_piece_or_portion_value"
    elif rule_item.unit != llm_item.unit:
        merged = rule_item.model_copy(deep=True)
        conflict = True
        decision = "rule"
        reason = "unit_conflict_rule_normalizes_units"
    elif rule_item.quantity is None and llm_item.quantity is None:
        merged = llm_item.model_copy(deep=True)
        merged.needs_clarification = True
        conflict = True
        decision = "llm"
        reason = "both_missing_quantity_llm_context"
    else:
        merged = rule_item.model_copy(deep=True)

    merged.name = canonicalize(merged.name)
    merged.role = _merge_role(rule_item, llm_item)
    merged.parent_name = rule_item.parent_name or llm_item.parent_name
    merged.notes = _merge_notes(rule_item.notes, llm_item.notes)
    merged.modifiers = _merge_modifiers(rule_item.modifiers, llm_item.modifiers)
    merged.preparation = _merge_preparation(rule_item.preparation, llm_item.preparation)
    merged.confidence = round(max(rule_item.confidence, llm_item.confidence) - 0.05, 2)

    if conflict:
        _audit(
            db,
            user_id,
            "parser_merge_conflict",
            {
                "rule_item": rule_item.model_dump(),
                "llm_item": llm_item.model_dump(),
                "decision": decision,
                "reason": reason,
            },
        )

    return merged, conflict


def _canonical_item(item: ParsedFoodItem) -> ParsedFoodItem:
    copied = item.model_copy(deep=True)
    copied.name = _canonical_name(copied.name)
    return copied


def _canonical_name(name: str) -> str:
    direct = FOOD_ALIASES.get(name.lower())
    if direct:
        return direct
    return canonicalize(name)


def _llm_item_is_grounded(item: ParsedFoodItem, original_text: str) -> bool:
    lowered = original_text.lower()
    if item.name.lower() in lowered:
        return True

    original_tokens = _tokens(original_text)
    item_tokens = [token for token in _tokens(item.name) if token not in PARSER_STOPWORDS]
    if not item_tokens:
        return False

    for item_token in item_tokens:
        if any(item_token == token or levenshtein_distance(item_token, token) <= 2 for token in original_tokens):
            return True
    return False


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[A-Za-zÄÖÜäöüß]+|\d+(?:[.,]\d+)?", text)]


def _key(name: str) -> str:
    return name.strip().lower()


def _rule_has_explicit_weight_volume(rule_item: ParsedFoodItem, original_text: str) -> bool:
    if rule_item.unit not in {"g", "ml"}:
        return False
    return bool(_EXPLICIT_WEIGHT_VOLUME_RE.search(original_text))


def _same_piece_value(rule_item: ParsedFoodItem, llm_item: ParsedFoodItem) -> bool:
    units = {"piece", "slice", "portion", "plate", "bowl", "glass", "cup"}
    return (
        rule_item.unit == llm_item.unit
        and rule_item.unit in units
        and rule_item.quantity is not None
        and llm_item.quantity is not None
        and float(rule_item.quantity) == float(llm_item.quantity)
    )


def _merge_notes(rule_notes: str | None, llm_notes: str | None) -> str | None:
    values = []
    for note in (rule_notes, llm_notes):
        if note and note not in values:
            values.append(note)
    return "; ".join(values) if values else None


def _merge_modifiers(rule_modifiers: list[str], llm_modifiers: list[str]) -> list[str]:
    values = []
    for modifier in [*rule_modifiers, *llm_modifiers]:
        if modifier and modifier not in values:
            values.append(modifier)
    return values


def _merge_role(rule_item: ParsedFoodItem, llm_item: ParsedFoodItem) -> str:
    if rule_item.role != "main":
        return rule_item.role
    if llm_item.role != "main" and rule_item.quantity is None:
        return llm_item.role
    return "main"


def _merge_preparation(rule_prep: str | None, llm_prep: str | None) -> str | None:
    if llm_prep in _SPECIFIC_PREPARATIONS:
        return llm_prep
    if rule_prep in _SPECIFIC_PREPARATIONS:
        return rule_prep
    return rule_prep or llm_prep or "unknown"


def _llm_should_win_multiword(
    rule_items: list[ParsedFoodItem],
    llm_items: list[ParsedFoodItem],
) -> bool:
    if len(rule_items) < 2:
        return False
    rule_names = " ".join(item.name.lower() for item in rule_items)
    for llm_item in llm_items:
        llm_name = llm_item.name.lower()
        if len(llm_name.split()) < 2:
            continue
        if llm_name in rule_names or FOOD_ALIASES.get(llm_name):
            return True
    return False


def _collapse_multiword(
    rule_items: list[ParsedFoodItem],
    llm_items: list[ParsedFoodItem],
) -> list[ParsedFoodItem]:
    for llm_item in llm_items:
        if len(llm_item.name.split()) >= 2:
            return [llm_item]
    return rule_items


def _audit(
    db: Session | None,
    user_id: uuid.UUID | None,
    event_type: str,
    payload: dict,
) -> None:
    if db is None:
        return
    AuditService(db).log(event_type=event_type, user_id=user_id, payload=payload)
