from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.repositories.portions import PortionRuleRepository
from app.schemas.parsed_food import ParsedFoodItem
from app.schemas.portions import ResolvedPortion
from app.services.audit_service import AuditService
from app.services.static_data import (
    VOLUME_DENSITY,
    get_portion_rule,
    has_sized_variants,
    sized_variants,
)
from app.services.user_memory_service import lookup as lookup_memory, memory_phrase
from app.utils.units import normalize_unit, to_grams, to_ml


def resolve_portion(
    item: ParsedFoodItem,
    user_id: uuid.UUID | None = None,
    db: Session | None = None,
) -> ResolvedPortion:
    """Resolve a parsed food item into grams/ml, default kcal, or options.

    Explicit g/ml quantities are deterministic. Ambiguous portions use personal
    memory first, then portion rules, then clarification options.
    """
    unit = normalize_unit(item.unit or "unknown")
    quantity = item.quantity if item.quantity is not None else None

    explicit = _resolve_explicit_quantity(item, unit, quantity)
    if explicit:
        _audit(db, user_id, "portion_resolved", item, explicit, "explicit_quantity")
        return explicit

    memory = _resolve_memory(item, unit, user_id, db)
    if memory:
        _audit(db, user_id, "portion_resolved", item, memory, "user_memory")
        return memory

    special = _resolve_special_clarification(item, unit)
    if special:
        _audit(db, user_id, "portion_clarification_needed", item, special, "special_case")
        return special

    rule = _lookup_rule(item.name, unit, db)
    if rule:
        resolved = _resolve_from_rule(item, unit, quantity, rule)
        _audit(db, user_id, "portion_resolved", item, resolved, "portion_rule")
        return resolved

    unresolved = ResolvedPortion(
        item_name=item.name,
        confidence=min(item.confidence or 0.4, 0.45),
        was_estimated=True,
        needs_clarification=True,
        options=_generic_size_options(),
    )
    _audit(db, user_id, "portion_clarification_needed", item, unresolved, "no_rule")
    return unresolved


def _resolve_explicit_quantity(
    item: ParsedFoodItem,
    unit: str,
    quantity: float | None,
) -> ResolvedPortion | None:
    if quantity is None:
        return None

    grams = to_grams(quantity, unit)
    if grams is not None:
        return ResolvedPortion(
            item_name=item.name,
            grams=round(grams, 1),
            confidence=max(item.confidence, 0.9),
            was_estimated=False,
        )

    ml = to_ml(quantity, unit)
    if ml is not None:
        density = VOLUME_DENSITY.get(item.name, 1.0)
        return ResolvedPortion(
            item_name=item.name,
            grams=round(ml * density, 1),
            ml=round(ml, 1),
            confidence=max(item.confidence, 0.9),
            was_estimated=False,
        )

    return None


def _resolve_memory(
    item: ParsedFoodItem,
    unit: str,
    user_id: uuid.UUID | None,
    db: Session | None,
) -> ResolvedPortion | None:
    if not user_id or db is None:
        return None

    phrase = memory_phrase(item, unit)
    memory = lookup_memory(phrase=phrase, user_id=user_id, db=db, food_name=item.name)
    if not memory:
        return None

    grams = memory.get("grams")
    ml = memory.get("ml")
    if grams is None and ml is None:
        return None

    confidence = max(float(memory.get("confidence", 0.9)), 0.9)
    return ResolvedPortion(
        item_name=item.name,
        grams=grams,
        ml=ml,
        confidence=round(confidence, 2),
        was_estimated=True,
    )


def _resolve_special_clarification(item: ParsedFoodItem, unit: str) -> ResolvedPortion | None:
    sauce = _resolve_sauce_or_spread(item, unit)
    if sauce:
        return sauce

    if item.name == "Bowl" and unit == "bowl":
        return ResolvedPortion(
            item_name=item.name,
            confidence=min(item.confidence or 0.4, 0.4),
            was_estimated=True,
            needs_clarification=True,
            options=[
                {"label": "Reis + Hähnchen", "default_kcal": 700},
                {"label": "Salat + Hähnchen", "default_kcal": 450},
                {"label": "Poke / Fisch", "default_kcal": 600},
                {"label": "Andere", "type": "custom"},
            ],
        )

    if item.name == "Milch" and unit == "unknown" and item.notes:
        return ResolvedPortion(
            item_name=item.name,
            confidence=min(item.confidence or 0.4, 0.4),
            was_estimated=True,
            needs_clarification=True,
            options=[
                {"label": "Schuss (10ml)", "ml": 10},
                {"label": "Etwas (30ml)", "ml": 30},
                {"label": "Halbes Glas (125ml)", "ml": 125},
                {"label": "Eigene Menge", "type": "custom"},
            ],
        )

    if item.needs_clarification and item.options:
        return ResolvedPortion(
            item_name=item.name,
            confidence=item.confidence,
            was_estimated=True,
            needs_clarification=True,
            options=item.options,
        )

    return None


def _resolve_sauce_or_spread(item: ParsedFoodItem, unit: str) -> ResolvedPortion | None:
    if unit not in {"unknown", "tbsp", "tsp"}:
        return None

    lowered = f"{item.name} {item.notes or ''} {' '.join(item.modifiers)}".lower()
    grams_by_name = {
        "Mayo": 15,
        "Hummus": 30,
        "Auberginencreme": 30,
    }
    grams = grams_by_name.get(item.name)
    if grams is None:
        if any(word in lowered for word in ("sauce", "dressing", "creme", "aioli", "senf", "ketchup")):
            grams = 20
        else:
            return None

    if any(word in lowered for word in ("etwas", "bisschen", "wenig", "klein", "kleine")):
        grams = min(grams, 15)

    return ResolvedPortion(
        item_name=item.name,
        grams=float(grams),
        confidence=max(min(item.confidence or 0.75, 0.85), 0.75),
        was_estimated=True,
    )


def _lookup_rule(food_name: str, unit: str, db: Session | None) -> Any | None:
    if db is not None:
        repo = PortionRuleRepository(db)
        rule = repo.get_by_food_and_unit(food_name, unit)
        if rule:
            return rule

    return get_portion_rule(food_name, unit)


def _resolve_from_rule(
    item: ParsedFoodItem,
    unit: str,
    quantity: float | None,
    rule: Any,
) -> ResolvedPortion:
    qty = quantity or 1.0
    confidence = min(float(rule.confidence), item.confidence or float(rule.confidence))

    if _rule_has_sized_variants(item.name, unit, rule):
        size = _size_from_item_notes(item)
        if size:
            variant = _variant_for_size(item.name, unit, size)
            if variant and variant.default_grams is not None:
                return ResolvedPortion(
                    item_name=item.name,
                    grams=round(float(variant.default_grams) * qty, 1),
                    confidence=round(max(confidence, float(variant.confidence)), 2),
                    was_estimated=True,
                )
        return ResolvedPortion(
            item_name=item.name,
            confidence=round(confidence, 2),
            was_estimated=True,
            needs_clarification=True,
            options=_sized_options(item.name, unit),
        )

    if rule.default_grams is not None:
        return ResolvedPortion(
            item_name=item.name,
            grams=round(float(rule.default_grams) * qty, 1),
            confidence=round(confidence, 2),
            was_estimated=True,
        )

    if rule.default_kcal is not None:
        return ResolvedPortion(
            item_name=item.name,
            default_kcal=round(float(rule.default_kcal) * qty, 1),
            confidence=round(confidence, 2),
            was_estimated=True,
        )

    return ResolvedPortion(
        item_name=item.name,
        confidence=round(min(confidence, 0.5), 2),
        was_estimated=True,
        needs_clarification=True,
        options=_generic_size_options(),
    )


def _rule_has_sized_variants(food_name: str, unit: str, rule: Any) -> bool:
    if getattr(rule, "sized", False):
        return True
    if has_sized_variants(food_name, unit):
        return True
    return bool(_sized_options(food_name, unit, include_custom=False))


def _sized_options(food_name: str, unit: str, include_custom: bool = True) -> list[dict]:
    labels = ["Klein", "Normal", "Groß"]
    options = []
    for label, variant in zip(labels, sized_variants(food_name, unit)):
        options.append({"label": label, "grams": float(variant.default_grams)})
    if not options and food_name == "Pasta" and unit == "plate":
        options = [
            {"label": "Klein", "grams": 250},
            {"label": "Normal", "grams": 350},
            {"label": "Groß", "grams": 500},
        ]
    if include_custom:
        options.append({"label": "Eigene Menge", "type": "custom"})
    return options


def _size_from_item_notes(item: ParsedFoodItem) -> str | None:
    text = f"{item.notes or ''} {' '.join(item.modifiers)}".lower()
    if any(word in text for word in ("small", "klein", "kleine", "wenig")):
        return "small"
    if any(word in text for word in ("large", "groß", "grosse", "gross", "viel")):
        return "large"
    if any(word in text for word in ("medium", "normal", "mittel")):
        return "medium"
    return None


def _variant_for_size(food_name: str, unit: str, size: str) -> Any | None:
    index = {"small": 0, "medium": 1, "large": 2}.get(size)
    variants = sized_variants(food_name, unit)
    if index is None or index >= len(variants):
        return None
    return variants[index]


def _generic_size_options() -> list[dict]:
    return [
        {"label": "Klein", "grams": 100},
        {"label": "Normal", "grams": 200},
        {"label": "Groß", "grams": 350},
        {"label": "Eigene Menge", "type": "custom"},
    ]


def _audit(
    db: Session | None,
    user_id: uuid.UUID | None,
    event_type: str,
    item: ParsedFoodItem,
    portion: ResolvedPortion,
    reason: str,
) -> None:
    if db is None:
        return
    AuditService(db).log(
        event_type=event_type,
        user_id=user_id,
        payload={
            "item": item.model_dump(),
            "portion": portion.model_dump(),
            "reason": reason,
        },
    )
