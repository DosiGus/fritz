"""Last-resort fallback data for the nutrition pipeline.

Everything in here is a safety net for when the LLM, the DB and the external
nutrition APIs all fail to produce a value. Do not add new entries here lightly —
prefer adding seeds to the DB (`scripts/seed_default_foods.py`) so they can be
edited without a code release.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StaticPortionRule:
    food_name: str
    unit_text: str
    default_grams: float | None
    default_kcal: float | None
    confidence: float


# Static portion fallbacks. Only kept for foods that are likely to appear in test
# inputs without a DB seed available. Production data lives in the portion_rules
# table (`scripts/seed_portion_rules.py`).
PORTION_RULES: dict[tuple[str, str], StaticPortionRule] = {
    ("Banane", "piece"):       StaticPortionRule("Banane", "piece", 120, None, 0.90),
    ("Ei", "piece"):           StaticPortionRule("Ei", "piece", 60, None, 0.90),
    ("Toast", "slice"):        StaticPortionRule("Toast", "slice", 25, None, 0.90),
    ("Brot", "slice"):         StaticPortionRule("Brot", "slice", 45, None, 0.85),
    ("Apfel", "piece"):        StaticPortionRule("Apfel", "piece", 180, None, 0.85),
    ("Orange", "piece"):       StaticPortionRule("Orange", "piece", 200, None, 0.85),
    ("Cappuccino", "cup"):     StaticPortionRule("Cappuccino", "cup", 180, None, 0.85),
    ("Kaffee", "cup"):         StaticPortionRule("Kaffee", "cup", None, 5, 0.90),
    ("Mayo", "tbsp"):          StaticPortionRule("Mayo", "tbsp", 15, None, 0.85),
    ("Butter", "tbsp"):        StaticPortionRule("Butter", "tbsp", 15, None, 0.80),
    ("Olivenöl", "tbsp"):      StaticPortionRule("Olivenöl", "tbsp", 14, None, 0.80),
    ("Milch", "glass"):        StaticPortionRule("Milch", "glass", 250, None, 0.85),
    ("Reis", "portion"):       StaticPortionRule("Reis", "portion", 180, None, 0.80),
    ("Pasta", "plate"):        StaticPortionRule("Pasta", "plate", 350, None, 0.70),
    ("Süßkartoffelpommes", "portion"): StaticPortionRule("Süßkartoffelpommes", "portion", 180, None, 0.70),
    ("Falafel Sandwich", "piece"): StaticPortionRule("Falafel Sandwich", "piece", 300, None, 0.82),
    ("Falafel Wrap", "piece"): StaticPortionRule("Falafel Wrap", "piece", 280, None, 0.82),
    ("Döner", "piece"):        StaticPortionRule("Döner", "piece", None, 650, 0.70),
    ("Hähnchen", "portion"):   StaticPortionRule("Hähnchen", "portion", 150, None, 0.75),
    ("Haferflocken", "bowl"):  StaticPortionRule("Haferflocken", "bowl", 80, None, 0.70),
}


# Volume → grams density factors for drinks where 1ml ≠ 1g.
VOLUME_DENSITY: dict[str, float] = {
    "Milch": 1.03,
}


# Last-resort nutrition values per 100g, used when DB cache, OFF and USDA all
# fail to return a match. Mirrors `scripts/seed_default_foods.py`.
DEFAULT_NUTRITION: dict[str, dict[str, float]] = {
    "Skyr": {"kcal_100g": 64, "protein_100g": 11.0, "carbs_100g": 4.0, "fat_100g": 0.2},
    "Magerquark": {"kcal_100g": 67, "protein_100g": 12.0, "carbs_100g": 4.1, "fat_100g": 0.2},
    "Ei": {"kcal_100g": 155, "protein_100g": 13.0, "carbs_100g": 1.1, "fat_100g": 11.0},
    "Banane": {"kcal_100g": 89, "protein_100g": 1.1, "carbs_100g": 23.0, "fat_100g": 0.3},
    "Brot": {"kcal_100g": 250, "protein_100g": 8.0, "carbs_100g": 47.0, "fat_100g": 2.0},
    "Vollkornbrot": {"kcal_100g": 220, "protein_100g": 8.0, "carbs_100g": 41.0, "fat_100g": 2.0},
    "Toast": {"kcal_100g": 265, "protein_100g": 8.0, "carbs_100g": 50.0, "fat_100g": 3.0},
    "Milch": {"kcal_100g": 64, "protein_100g": 3.4, "carbs_100g": 4.8, "fat_100g": 3.7},
    "Hafermilch": {"kcal_100g": 45, "protein_100g": 1.0, "carbs_100g": 6.5, "fat_100g": 1.5},
    "Haferflocken": {"kcal_100g": 370, "protein_100g": 13.0, "carbs_100g": 59.0, "fat_100g": 7.0},
    "Reis": {"kcal_100g": 130, "protein_100g": 2.7, "carbs_100g": 28.0, "fat_100g": 0.3},
    "Pasta": {"kcal_100g": 158, "protein_100g": 5.8, "carbs_100g": 30.0, "fat_100g": 0.9},
    "Whey Protein": {"kcal_100g": 400, "protein_100g": 80.0, "carbs_100g": 8.0, "fat_100g": 5.0},
    "Hähnchen": {"kcal_100g": 165, "protein_100g": 31.0, "carbs_100g": 0.0, "fat_100g": 3.6},
    "Kaffee": {"kcal_100g": 2, "protein_100g": 0.3, "carbs_100g": 0.0, "fat_100g": 0.0},
    "Espresso": {"kcal_100g": 9, "protein_100g": 0.6, "carbs_100g": 1.0, "fat_100g": 0.2},
    "Cappuccino": {"kcal_100g": 45, "protein_100g": 2.4, "carbs_100g": 4.8, "fat_100g": 1.8},
    "Butter": {"kcal_100g": 717, "protein_100g": 0.9, "carbs_100g": 0.1, "fat_100g": 81.0},
    "Olivenöl": {"kcal_100g": 884, "protein_100g": 0.0, "carbs_100g": 0.0, "fat_100g": 100.0},
    "Apfel": {"kcal_100g": 52, "protein_100g": 0.3, "carbs_100g": 14.0, "fat_100g": 0.2},
    "Orange": {"kcal_100g": 47, "protein_100g": 0.9, "carbs_100g": 12.0, "fat_100g": 0.1},
    "Mandarine": {"kcal_100g": 53, "protein_100g": 0.8, "carbs_100g": 13.0, "fat_100g": 0.3},
    "Mango": {"kcal_100g": 60, "protein_100g": 0.8, "carbs_100g": 15.0, "fat_100g": 0.4},
    "Erdbeere": {"kcal_100g": 32, "protein_100g": 0.7, "carbs_100g": 7.7, "fat_100g": 0.3},
    "Beeren": {"kcal_100g": 45, "protein_100g": 0.8, "carbs_100g": 10.0, "fat_100g": 0.4},
    "Bier": {"kcal_100g": 43, "protein_100g": 0.5, "carbs_100g": 3.6, "fat_100g": 0.0},
    "Honig": {"kcal_100g": 304, "protein_100g": 0.3, "carbs_100g": 82.0, "fat_100g": 0.0},
    "Hummus": {"kcal_100g": 250, "protein_100g": 7.9, "carbs_100g": 14.3, "fat_100g": 17.8},
    "Halloumi": {"kcal_100g": 321, "protein_100g": 21.0, "carbs_100g": 2.2, "fat_100g": 25.0},
    "Auberginencreme": {"kcal_100g": 180, "protein_100g": 2.0, "carbs_100g": 8.0, "fat_100g": 15.0},
    "Mayo": {"kcal_100g": 700, "protein_100g": 1.0, "carbs_100g": 1.0, "fat_100g": 75.0},
    "Falafel Sandwich": {"kcal_100g": 265, "protein_100g": 6.2, "carbs_100g": 27.0, "fat_100g": 14.8},
    "Falafel Wrap": {"kcal_100g": 260, "protein_100g": 6.5, "carbs_100g": 28.0, "fat_100g": 13.5},
    "Süßkartoffelpommes": {"kcal_100g": 180, "protein_100g": 2.0, "carbs_100g": 30.0, "fat_100g": 6.0},
    "Erdnussbutter": {"kcal_100g": 588, "protein_100g": 25.0, "carbs_100g": 20.0, "fat_100g": 50.0},
    "Lachs": {"kcal_100g": 208, "protein_100g": 20.0, "carbs_100g": 0.0, "fat_100g": 13.0},
    "Thunfisch": {"kcal_100g": 116, "protein_100g": 26.0, "carbs_100g": 0.0, "fat_100g": 1.0},
    "Rindfleisch": {"kcal_100g": 215, "protein_100g": 26.0, "carbs_100g": 0.0, "fat_100g": 12.0},
    "Tomate": {"kcal_100g": 18, "protein_100g": 0.9, "carbs_100g": 3.9, "fat_100g": 0.2},
    "Gurke": {"kcal_100g": 16, "protein_100g": 0.7, "carbs_100g": 3.6, "fat_100g": 0.1},
    "Paprika": {"kcal_100g": 31, "protein_100g": 1.0, "carbs_100g": 6.0, "fat_100g": 0.3},
    "Spinat": {"kcal_100g": 23, "protein_100g": 2.9, "carbs_100g": 3.6, "fat_100g": 0.4},
    "Brokkoli": {"kcal_100g": 34, "protein_100g": 2.8, "carbs_100g": 7.0, "fat_100g": 0.4},
    "Kartoffel": {"kcal_100g": 77, "protein_100g": 2.0, "carbs_100g": 17.0, "fat_100g": 0.1},
    "Süßkartoffel": {"kcal_100g": 86, "protein_100g": 1.6, "carbs_100g": 20.0, "fat_100g": 0.1},
    "Avocado": {"kcal_100g": 160, "protein_100g": 2.0, "carbs_100g": 9.0, "fat_100g": 15.0},
    "Linsen": {"kcal_100g": 353, "protein_100g": 25.0, "carbs_100g": 60.0, "fat_100g": 1.1},
    "Kichererbsen": {"kcal_100g": 364, "protein_100g": 19.0, "carbs_100g": 61.0, "fat_100g": 6.0},
    "Joghurt": {"kcal_100g": 59, "protein_100g": 3.5, "carbs_100g": 4.7, "fat_100g": 3.3},
    "Griechischer Joghurt": {"kcal_100g": 97, "protein_100g": 9.0, "carbs_100g": 4.0, "fat_100g": 5.0},
}


def canonicalize(name: str) -> str:
    """Return the food name unchanged (the LLM already produces canonical names)."""
    return name.strip()


def get_portion_rule(food_name: str, unit_text: str) -> StaticPortionRule | None:
    return PORTION_RULES.get((food_name, unit_text))
