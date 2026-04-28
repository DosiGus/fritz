from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.schemas.parsed_food import ParsedFoodItem, ParsedFoodMessage
from app.services.audit_service import AuditService


@dataclass(frozen=True)
class RecipeComponent:
    name: str
    grams_by_size: dict[str, float]
    aliases: tuple[str, ...]
    required: bool = False


@dataclass(frozen=True)
class RecipePattern:
    name: str
    trigger_terms: tuple[str, ...]
    base_components: tuple[RecipeComponent, ...]
    optional_components: tuple[RecipeComponent, ...]
    default_components_when_plain: bool = False


SKYR_BOWL = RecipePattern(
    name="Skyr Bowl",
    trigger_terms=("skyr bowl", "skyrbowl"),
    base_components=(
        RecipeComponent("Skyr", {"small": 150, "medium": 250, "large": 350}, ("skyr",), required=True),
    ),
    optional_components=(
        RecipeComponent("Mango", {"small": 60, "medium": 100, "large": 150}, ("mango", "mangos", "tk mango", "tk mangos")),
        RecipeComponent("Honig", {"small": 10, "medium": 15, "large": 20}, ("honig",)),
        RecipeComponent("Banane", {"small": 60, "medium": 100, "large": 120}, ("banane", "bananen")),
        RecipeComponent("Beeren", {"small": 60, "medium": 100, "large": 150}, ("beeren", "beerenmix")),
        RecipeComponent("Erdbeere", {"small": 60, "medium": 100, "large": 150}, ("erdbeere", "erdbeeren")),
        RecipeComponent("Whey Protein", {"small": 15, "medium": 25, "large": 30}, ("whey", "whey protein", "proteinpulver")),
    ),
)

OATMEAL_BOWL = RecipePattern(
    name="Oatmeal Bowl",
    trigger_terms=("oatmeal bowl", "oat bowl", "porridge", "haferflocken bowl", "hafer bowl"),
    base_components=(
        RecipeComponent("Haferflocken", {"small": 40, "medium": 60, "large": 80}, ("haferflocken", "oats", "porridge"), required=True),
    ),
    optional_components=(
        RecipeComponent("Milch", {"small": 100, "medium": 150, "large": 220}, ("milch", "h-milch", "hmilch")),
        RecipeComponent("Hafermilch", {"small": 100, "medium": 150, "large": 220}, ("hafermilch", "hafer milch")),
        RecipeComponent("Banane", {"small": 60, "medium": 100, "large": 120}, ("banane", "bananen")),
        RecipeComponent("Mango", {"small": 60, "medium": 100, "large": 150}, ("mango", "mangos", "tk mango", "tk mangos")),
        RecipeComponent("Beeren", {"small": 60, "medium": 100, "large": 150}, ("beeren", "beerenmix")),
        RecipeComponent("Honig", {"small": 5, "medium": 10, "large": 15}, ("honig",)),
        RecipeComponent("Erdnussbutter", {"small": 10, "medium": 15, "large": 25}, ("erdnussbutter", "peanut butter")),
        RecipeComponent("Whey Protein", {"small": 15, "medium": 25, "large": 30}, ("whey", "whey protein", "proteinpulver")),
    ),
)

SMOOTHIE = RecipePattern(
    name="Smoothie",
    trigger_terms=("smoothie", "shake", "proteinshake", "protein shake"),
    base_components=(),
    optional_components=(
        RecipeComponent("Banane", {"small": 80, "medium": 120, "large": 160}, ("banane", "bananen")),
        RecipeComponent("Mango", {"small": 80, "medium": 120, "large": 180}, ("mango", "mangos", "tk mango", "tk mangos")),
        RecipeComponent("Beeren", {"small": 80, "medium": 120, "large": 180}, ("beeren", "beerenmix")),
        RecipeComponent("Erdbeere", {"small": 80, "medium": 120, "large": 180}, ("erdbeere", "erdbeeren")),
        RecipeComponent("Skyr", {"small": 100, "medium": 150, "large": 220}, ("skyr",)),
        RecipeComponent("Joghurt", {"small": 100, "medium": 150, "large": 220}, ("joghurt",)),
        RecipeComponent("Milch", {"small": 150, "medium": 250, "large": 350}, ("milch", "h-milch", "hmilch")),
        RecipeComponent("Hafermilch", {"small": 150, "medium": 250, "large": 350}, ("hafermilch", "hafer milch")),
        RecipeComponent("Whey Protein", {"small": 15, "medium": 25, "large": 30}, ("whey", "whey protein", "proteinpulver")),
    ),
)

RICE_BOWL = RecipePattern(
    name="Rice Bowl",
    trigger_terms=("rice bowl", "reis bowl", "reisbowl", "bowl mit reis"),
    base_components=(
        RecipeComponent("Reis", {"small": 120, "medium": 180, "large": 250}, ("reis",), required=True),
    ),
    optional_components=(
        RecipeComponent("Hähnchen", {"small": 100, "medium": 150, "large": 220}, ("hähnchen", "huhn", "chicken")),
        RecipeComponent("Avocado", {"small": 50, "medium": 80, "large": 120}, ("avocado",)),
        RecipeComponent("Paprika", {"small": 50, "medium": 80, "large": 120}, ("paprika",)),
        RecipeComponent("Tomate", {"small": 50, "medium": 80, "large": 120}, ("tomate", "tomaten")),
        RecipeComponent("Gurke", {"small": 50, "medium": 80, "large": 120}, ("gurke",)),
        RecipeComponent("Brokkoli", {"small": 60, "medium": 100, "large": 150}, ("brokkoli",)),
        RecipeComponent("Olivenöl", {"small": 5, "medium": 10, "large": 15}, ("olivenöl", "öl")),
    ),
)

PASTA_PLATE = RecipePattern(
    name="Pasta Plate",
    trigger_terms=("pasta", "nudeln", "spaghetti", "penne"),
    base_components=(
        RecipeComponent("Pasta", {"small": 250, "medium": 350, "large": 500}, ("pasta", "nudeln", "spaghetti", "penne"), required=True),
    ),
    optional_components=(
        RecipeComponent("Hähnchen", {"small": 80, "medium": 120, "large": 180}, ("hähnchen", "huhn", "chicken")),
        RecipeComponent("Tomate", {"small": 80, "medium": 120, "large": 180}, ("tomate", "tomaten", "tomatensauce")),
        RecipeComponent("Olivenöl", {"small": 5, "medium": 10, "large": 15}, ("olivenöl", "öl")),
        RecipeComponent("Butter", {"small": 5, "medium": 10, "large": 15}, ("butter",)),
    ),
    default_components_when_plain=False,
)

_PATTERNS = (SKYR_BOWL, OATMEAL_BOWL, SMOOTHIE, RICE_BOWL, PASTA_PLATE)


def decompose_recipes(
    parsed: ParsedFoodMessage,
    original_text: str,
    db: Session | None = None,
    user_id: uuid.UUID | None = None,
) -> ParsedFoodMessage:
    """Expand known composite meals into transparent, calculable components."""
    lowered = original_text.lower()
    context_text = _context_text(parsed, lowered)
    expanded_items: list[ParsedFoodItem] = []
    changed = False
    consumed_component_keys: set[str] = set()

    for item in parsed.items:
        if _component_key(item) in consumed_component_keys:
            continue

        pattern = _matching_pattern(item, context_text)
        if not pattern:
            expanded_items.append(item)
            continue

        components = _components_for_pattern(pattern, context_text)
        if not _should_decompose(pattern, components):
            expanded_items.append(item)
            continue

        size = _detect_size(context_text)
        expanded_items.extend(_items_from_components(pattern.name, components, size, item.confidence))
        consumed_component_keys.update(_component_key_from_name(component.name) for component in components)
        changed = True

    if not changed:
        return parsed

    result = ParsedFoodMessage(
        meal_type=parsed.meal_type,
        items=expanded_items,
        overall_confidence=round(sum(item.confidence for item in expanded_items) / len(expanded_items), 2),
        llm_called=parsed.llm_called,
    )
    _audit(
        db,
        user_id,
        "recipe_decomposed",
        {
            "original_text": original_text,
            "before": parsed.model_dump(),
            "after": result.model_dump(),
        },
    )
    return result


def _matching_pattern(item: ParsedFoodItem, lowered_text: str) -> RecipePattern | None:
    item_name = _normalize_text(item.name)
    for pattern in _PATTERNS:
        if any(_contains_alias(item_name, term) for term in pattern.trigger_terms):
            return pattern
        if item_name in {"bowl", "plate", "teller", "schüssel"} and any(_contains_alias(lowered_text, term) for term in pattern.trigger_terms):
            return pattern
    return None


def _components_for_pattern(pattern: RecipePattern, lowered_text: str) -> list[RecipeComponent]:
    components = list(pattern.base_components)
    for component in pattern.optional_components:
        if any(_contains_alias(lowered_text, alias) for alias in component.aliases):
            components.append(component)
    return components


def _contains_alias(lowered_text: str, alias: str) -> bool:
    return bool(re.search(rf"\b{re.escape(_normalize_text(alias))}\b", lowered_text))


def _detect_size(lowered_text: str) -> str:
    if re.search(r"\b(klein|kleine|kleiner|small)\b", lowered_text):
        return "small"
    if re.search(r"\b(groß|grosse|große|gross|large)\b", lowered_text):
        return "large"
    return "medium"


def _should_decompose(pattern: RecipePattern, components: list[RecipeComponent]) -> bool:
    if not pattern.base_components:
        return bool(components)
    if len(components) > len(pattern.base_components):
        return True
    return pattern.default_components_when_plain and bool(components)


def _context_text(parsed: ParsedFoodMessage, lowered_text: str) -> str:
    values = [lowered_text]
    for item in parsed.items:
        values.extend([item.name, item.notes or "", item.parent_name or ""])
        values.extend(item.modifiers)
    return _normalize_text(" ".join(value for value in values if value))


def _normalize_text(text: str) -> str:
    normalized = text.lower()
    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _component_key(item: ParsedFoodItem) -> str:
    return _component_key_from_name(item.name)


def _component_key_from_name(name: str) -> str:
    return _normalize_text(name)


def _items_from_components(
    recipe_name: str,
    components: list[RecipeComponent],
    size: str,
    parent_confidence: float,
) -> list[ParsedFoodItem]:
    confidence = max(min(parent_confidence, 0.86), 0.78)
    return [
        ParsedFoodItem(
            name=component.name,
            quantity=component.grams_by_size[size],
            unit="g",
            role="main",
            notes=f"{recipe_name}, {size}",
            confidence=confidence,
        )
        for component in components
    ]


def _audit(
    db: Session | None,
    user_id: uuid.UUID | None,
    event_type: str,
    payload: dict,
) -> None:
    if db is None:
        return
    AuditService(db).log(event_type=event_type, user_id=user_id, payload=payload)
