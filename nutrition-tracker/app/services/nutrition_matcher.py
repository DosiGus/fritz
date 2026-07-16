from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import NutritionItem
from app.db.repositories.nutrition_items import FoodAliasRepository, NutritionItemRepository
from app.integrations.open_food_facts import OpenFoodFactsClient
from app.integrations.usda_fdc import UsdaFdcClient
from app.schemas.nutrition import NutritionMatch
from app.services.audit_service import AuditService
from app.services.static_data import DEFAULT_NUTRITION, canonicalize
from app.utils.fuzzy_matching import best_match, score

logger = logging.getLogger(__name__)

_PREPARATION_WORDS = {
    "gekocht",
    "gekochter",
    "gekochte",
    "cooked",
    "roh",
    "roher",
    "rohe",
    "raw",
    "gebraten",
    "fried",
    "grilled",
    "gegrillt",
}


def match(canonical_name: str, db: Session | None = None) -> NutritionMatch | None:
    """Find the best nutrition values for a canonical food name.

    Ranking:
    1. exact cache hit
    2. alias → cache hit
    3. fuzzy cache hit
    4. deterministic default foods
    5. Open Food Facts
    6. USDA FoodData Central
    """
    query = _normalize_food_query(canonical_name)
    canonical = canonicalize(query)

    if db is not None:
        cached = _match_cache(canonical, db)
        if cached:
            _audit(db, "nutrition_matched", canonical_name, cached, "cache_exact")
            return cached

        alias_hit = _match_alias_cache(query, db)
        if alias_hit:
            _audit(db, "nutrition_matched", canonical_name, alias_hit, "cache_alias")
            return alias_hit

        fuzzy_hit = _match_fuzzy_cache(canonical, db)
        if fuzzy_hit:
            _audit(db, "nutrition_matched", canonical_name, fuzzy_hit, "cache_fuzzy")
            return fuzzy_hit

    default = _match_default(canonical)
    if default:
        _audit(db, "nutrition_matched", canonical_name, default, "default_food")
        return default

    if db is not None:
        ambiguous = find_ambiguous_matches(canonical_name, db=db)
        if ambiguous:
            AuditService(db).log(
                event_type="nutrition_match_ambiguous",
                payload={"canonical_name": canonical_name, "candidates": [m.model_dump() for m in ambiguous]},
            )
            return None

        off = _match_open_food_facts(canonical, db)
        if off:
            _audit(db, "nutrition_matched", canonical_name, off, "open_food_facts")
            return off

        usda = _match_usda(canonical, db)
        if usda:
            _audit(db, "nutrition_matched", canonical_name, usda, "usda")
            return usda

        AuditService(db).log(
            event_type="nutrition_match_failed",
            payload={"canonical_name": canonical_name, "normalized": canonical},
        )

    return None


def find_ambiguous_matches(canonical_name: str, db: Session, limit: int = 4) -> list[NutritionMatch]:
    """Return close nutrition candidates that should be confirmed by the user.

    Exact verified/cache/default hits are intentionally left alone by the caller.
    This helper looks for medium-confidence cache/default alternatives with close
    scores, e.g. several yogurts or branded variants for the same query.
    """
    query = _normalize_food_query(canonical_name)
    canonical = canonicalize(query)
    candidates: list[tuple[float, NutritionMatch]] = []

    for item in db.query(NutritionItem).limit(500).all():
        candidate_score = max(
            score(canonical.lower(), str(item.canonical_name).lower()),
            score(query.lower(), str(item.canonical_name).lower()),
        )
        if candidate_score < 74:
            continue
        match_obj = _from_db_item(item, confidence=round(min(candidate_score / 100, 0.86), 2))
        if match_obj:
            candidates.append((candidate_score, match_obj))

    for default_name in DEFAULT_NUTRITION:
        candidate_score = max(score(canonical.lower(), default_name.lower()), score(query.lower(), default_name.lower()))
        if candidate_score < 78:
            continue
        default_match = _match_default(default_name)
        if default_match:
            default_match.confidence = round(min(candidate_score / 100, 0.86), 2)
            candidates.append((candidate_score, default_match))

    deduped: dict[str, tuple[float, NutritionMatch]] = {}
    for candidate_score, match_obj in candidates:
        existing = deduped.get(match_obj.canonical_name)
        if existing is None or candidate_score > existing[0]:
            deduped[match_obj.canonical_name] = (candidate_score, match_obj)

    ranked = sorted(deduped.values(), key=lambda pair: pair[0], reverse=True)
    if len(ranked) < 2:
        return []
    if ranked[0][0] - ranked[1][0] > 12 and ranked[0][0] >= 90:
        return []
    return [match_obj for _, match_obj in ranked[:limit]]


def _match_cache(canonical_name: str, db: Session) -> NutritionMatch | None:
    repo = NutritionItemRepository(db)
    item = repo.get_by_canonical_name(canonical_name)
    return _from_db_item(item, confidence=0.95 if item and item.verified else 0.85)


def _match_alias_cache(query: str, db: Session) -> NutritionMatch | None:
    alias = FoodAliasRepository(db).get_by_alias(query)
    if not alias:
        return None
    item = NutritionItemRepository(db).get_by_canonical_name(alias.canonical_name)
    if not item:
        return None
    return _from_db_item(item, confidence=min(float(alias.confidence), 0.92))


def _match_fuzzy_cache(canonical_name: str, db: Session) -> NutritionMatch | None:
    items = db.query(NutritionItem).limit(500).all()
    names = [item.canonical_name for item in items]
    matched = best_match(canonical_name, names, threshold=82)
    if not matched:
        return None
    matched_name, fuzzy_score = matched
    item = next((i for i in items if i.canonical_name == matched_name), None)
    if not item:
        return None
    confidence = min(0.85, round(fuzzy_score / 100, 2))
    return _from_db_item(item, confidence=confidence)


def _match_default(canonical_name: str) -> NutritionMatch | None:
    values = DEFAULT_NUTRITION.get(canonical_name)
    if not values:
        return None
    return NutritionMatch(
        canonical_name=canonical_name,
        kcal_100g=values["kcal_100g"],
        protein_100g=values["protein_100g"],
        carbs_100g=values["carbs_100g"],
        fat_100g=values["fat_100g"],
        source="default_static",
        confidence=0.92,
    )


def _match_open_food_facts(canonical_name: str, db: Session) -> NutritionMatch | None:
    client = OpenFoodFactsClient(db=db)
    try:
        products = client.search_by_name(canonical_name, page_size=3)
    finally:
        client.close()

    for product in products:
        match_obj = _from_off_product(canonical_name, product)
        if match_obj:
            _cache_match(db, match_obj)
            return match_obj
    return None


def _match_usda(canonical_name: str, db: Session) -> NutritionMatch | None:
    if not settings.usda_api_key:
        return None

    client = UsdaFdcClient(db=db)
    try:
        foods = client.search(canonical_name, page_size=3)
    finally:
        client.close()

    for food in foods:
        match_obj = _from_usda_food(canonical_name, food)
        if match_obj:
            _cache_match(db, match_obj)
            return match_obj
    return None


def _from_db_item(item: NutritionItem | None, confidence: float) -> NutritionMatch | None:
    if not item:
        return None
    return NutritionMatch(
        canonical_name=item.canonical_name,
        kcal_100g=float(item.kcal_100g) if item.kcal_100g is not None else None,
        protein_100g=float(item.protein_100g) if item.protein_100g is not None else None,
        carbs_100g=float(item.carbs_100g) if item.carbs_100g is not None else None,
        fat_100g=float(item.fat_100g) if item.fat_100g is not None else None,
        source=item.source or "cache",
        source_id=item.source_id,
        confidence=confidence,
    )


def _from_off_product(canonical_name: str, product: dict) -> NutritionMatch | None:
    nutriments = product.get("nutriments") or {}
    kcal = _num(nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal"))
    protein = _num(nutriments.get("proteins_100g"))
    carbs = _num(nutriments.get("carbohydrates_100g"))
    fat = _num(nutriments.get("fat_100g"))
    if kcal is None and protein is None and carbs is None and fat is None:
        return None
    if not _nutrition_values_are_plausible(canonical_name, kcal, protein, carbs, fat):
        return None

    return NutritionMatch(
        canonical_name=canonical_name,
        kcal_100g=kcal,
        protein_100g=protein,
        carbs_100g=carbs,
        fat_100g=fat,
        source="open_food_facts",
        source_id=str(product.get("code") or product.get("_id") or ""),
        confidence=0.78,
    )


def _from_usda_food(canonical_name: str, food: dict) -> NutritionMatch | None:
    nutrients = food.get("foodNutrients") or []
    values = {"kcal": None, "protein": None, "carbs": None, "fat": None}
    for nutrient in nutrients:
        name = str(nutrient.get("nutrientName") or nutrient.get("name") or "").lower()
        value = _num(nutrient.get("value"))
        if value is None:
            continue
        if "energy" in name or "calorie" in name:
            values["kcal"] = value
        elif "protein" in name:
            values["protein"] = value
        elif "carbohydrate" in name:
            values["carbs"] = value
        elif name in {"total lipid (fat)", "fat"} or "total lipid" in name:
            values["fat"] = value

    if all(value is None for value in values.values()):
        return None
    description = str(food.get("description") or food.get("lowercaseDescription") or "")
    if score(canonical_name.lower(), description.lower()) < 45:
        return None
    if not _nutrition_values_are_plausible(
        canonical_name,
        values["kcal"],
        values["protein"],
        values["carbs"],
        values["fat"],
    ):
        return None

    return NutritionMatch(
        canonical_name=canonical_name,
        kcal_100g=values["kcal"],
        protein_100g=values["protein"],
        carbs_100g=values["carbs"],
        fat_100g=values["fat"],
        source="usda_fdc",
        source_id=str(food.get("fdcId") or ""),
        confidence=0.80,
    )


def _cache_match(db: Session, match_obj: NutritionMatch) -> None:
    if not match_obj.source_id:
        return
    repo = NutritionItemRepository(db)
    repo.upsert_from_api(
        canonical_name=match_obj.canonical_name,
        source=match_obj.source,
        source_id=match_obj.source_id,
        kcal_100g=match_obj.kcal_100g,
        protein_100g=match_obj.protein_100g,
        carbs_100g=match_obj.carbs_100g,
        fat_100g=match_obj.fat_100g,
        verified=False,
    )


def _normalize_food_query(name: str) -> str:
    tokens = re.findall(r"[A-Za-zÄÖÜäöüß]+", name)
    filtered = [token for token in tokens if token.lower() not in _PREPARATION_WORDS]
    return " ".join(filtered).strip() or name.strip()


def _num(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nutrition_values_are_plausible(
    canonical_name: str,
    kcal: float | None,
    protein: float | None,
    carbs: float | None,
    fat: float | None,
) -> bool:
    if kcal is not None and (kcal < 0 or kcal > 950):
        return False
    if protein is not None and (protein < 0 or protein > 100):
        return False
    if carbs is not None and (carbs < 0 or carbs > 100):
        return False
    if fat is not None and (fat < 0 or fat > 100):
        return False

    lowered = canonical_name.lower()
    if any(word in lowered for word in ("milch", "kaffee", "cappuccino", "espresso")):
        if kcal is not None and kcal > 130:
            return False
        if fat is not None and fat > 10:
            return False
        if protein is not None and protein > 12:
            return False
        if carbs is not None and carbs > 20:
            return False
    return True


def _audit(
    db: Session | None,
    event_type: str,
    query: str,
    match_obj: NutritionMatch,
    reason: str,
) -> None:
    if db is None:
        return
    AuditService(db).log(
        event_type=event_type,
        payload={
            "query": query,
            "match": match_obj.model_dump(),
            "reason": reason,
        },
    )
