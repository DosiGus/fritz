"""Static seed-equivalent data used by stateless engines (rule parser, portion engine).

These tables mirror the DB seeds in scripts/seed_*.py. Keeping them in code lets the
parser run deterministically without a DB and lets tests assert against the same
canonical truth as the production seed scripts.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StaticPortionRule:
    food_name: str
    unit_text: str
    default_grams: float | None
    default_kcal: float | None
    confidence: float
    sized: bool = False  # plate_s/m/l companions exist


# (alias, canonical_name)
FOOD_ALIASES: dict[str, str] = {
    "skyr": "Skyr",
    "magerquark": "Magerquark",
    "quark": "Magerquark",
    "ei": "Ei",
    "eier": "Ei",
    "vollei": "Ei",
    "banane": "Banane",
    "bananen": "Banane",
    "brot": "Brot",
    "vollkornbrot": "Vollkornbrot",
    "toast": "Toast",
    "toastbrot": "Toast",
    "milch": "Milch",
    "kuhmilch": "Milch",
    "haferflocken": "Haferflocken",
    "oats": "Haferflocken",
    "porridge": "Haferflocken",
    "reis": "Reis",
    "pasta": "Pasta",
    "nudeln": "Pasta",
    "spaghetti": "Pasta",
    "penne": "Pasta",
    "whey": "Whey Protein",
    "whey protein": "Whey Protein",
    "proteinpulver": "Whey Protein",
    "döner": "Döner",
    "döner kebab": "Döner",
    "hähnchen": "Hähnchen",
    "huhn": "Hähnchen",
    "chicken": "Hähnchen",
    "kaffee": "Kaffee",
    "espresso": "Espresso",
    "butter": "Butter",
    "olivenöl": "Olivenöl",
    "apfel": "Apfel",
    "orange": "Orange",
    "mandarine": "Mandarine",
    "joghurt": "Joghurt",
    "lachs": "Lachs",
    "thunfisch": "Thunfisch",
    "rindfleisch": "Rindfleisch",
    "tomate": "Tomate",
    "gurke": "Gurke",
    "paprika": "Paprika",
    "spinat": "Spinat",
    "brokkoli": "Brokkoli",
    "kartoffel": "Kartoffel",
    "süßkartoffel": "Süßkartoffel",
    "avocado": "Avocado",
    "linsen": "Linsen",
    "kichererbsen": "Kichererbsen",
}


# Multi-word compound foods. The rule parser recognises these as a single item
# even when the input contains "mit" between the parts (e.g. "Dönerbox mit Pommes").
# Order matters: longer compounds first so they match before any prefix.
COMPOUND_FOODS: list[tuple[tuple[str, ...], str]] = [
    (("dönerbox", "pommes"), "Dönerbox Pommes"),
    (("chicken", "bowl", "reis"), "Chicken Bowl Reis"),
    (("chicken", "bowl", "salat"), "Chicken Bowl Salat"),
    (("hähnchen", "bowl", "reis"), "Chicken Bowl Reis"),
    (("hähnchen", "bowl", "salat"), "Chicken Bowl Salat"),
    (("whey", "protein"), "Whey Protein"),
]


# Static portion rules keyed by (canonical_food_name, unit_text).
PORTION_RULES: dict[tuple[str, str], StaticPortionRule] = {
    ("Banane", "piece"):       StaticPortionRule("Banane", "piece", 120, None, 0.90),
    ("Ei", "piece"):           StaticPortionRule("Ei", "piece", 60,  None, 0.90),
    ("Toast", "slice"):        StaticPortionRule("Toast", "slice", 25, None, 0.90),
    ("Brot", "slice"):         StaticPortionRule("Brot", "slice", 45, None, 0.85),
    ("Milch", "glass"):        StaticPortionRule("Milch", "glass", 250, None, 0.85),
    ("Haferflocken", "bowl"):  StaticPortionRule("Haferflocken", "bowl", 80, None, 0.70),
    ("Reis", "portion"):       StaticPortionRule("Reis", "portion", 180, None, 0.80),
    ("Pasta", "plate"):        StaticPortionRule("Pasta", "plate", 350, None, 0.50, sized=True),
    ("Pasta", "plate_s"):      StaticPortionRule("Pasta", "plate_s", 250, None, 0.85),
    ("Pasta", "plate_m"):      StaticPortionRule("Pasta", "plate_m", 350, None, 0.85),
    ("Pasta", "plate_l"):      StaticPortionRule("Pasta", "plate_l", 500, None, 0.85),
    ("Döner", "piece"):        StaticPortionRule("Döner", "piece", None, 650, 0.70),
    ("Dönerbox Pommes", "piece"):     StaticPortionRule("Dönerbox Pommes", "piece", None, 850, 0.70),
    ("Chicken Bowl Reis", "portion"): StaticPortionRule("Chicken Bowl Reis", "portion", None, 700, 0.75),
    ("Chicken Bowl Salat", "portion"):StaticPortionRule("Chicken Bowl Salat", "portion", None, 450, 0.75),
    ("Kaffee", "cup"):         StaticPortionRule("Kaffee", "cup", None, 5, 0.90),
    ("Apfel", "piece"):        StaticPortionRule("Apfel", "piece", 180, None, 0.85),
    ("Orange", "piece"):       StaticPortionRule("Orange", "piece", 200, None, 0.85),
    ("Butter", "tbsp"):        StaticPortionRule("Butter", "tbsp", 15, None, 0.80),
    ("Olivenöl", "tbsp"):      StaticPortionRule("Olivenöl", "tbsp", 14, None, 0.80),
}


# Volume → grams conversion factors for common drinks.
VOLUME_DENSITY: dict[str, float] = {
    "Milch": 1.03,
}


# Default nutrition values per 100g. Mirrors scripts/seed_default_foods.py for
# deterministic matching when no DB/cache/API result is available.
DEFAULT_NUTRITION: dict[str, dict[str, float]] = {
    "Skyr": {"kcal_100g": 64, "protein_100g": 11.0, "carbs_100g": 4.0, "fat_100g": 0.2},
    "Magerquark": {"kcal_100g": 67, "protein_100g": 12.0, "carbs_100g": 4.1, "fat_100g": 0.2},
    "Ei": {"kcal_100g": 155, "protein_100g": 13.0, "carbs_100g": 1.1, "fat_100g": 11.0},
    "Banane": {"kcal_100g": 89, "protein_100g": 1.1, "carbs_100g": 23.0, "fat_100g": 0.3},
    "Brot": {"kcal_100g": 250, "protein_100g": 8.0, "carbs_100g": 47.0, "fat_100g": 2.0},
    "Vollkornbrot": {"kcal_100g": 220, "protein_100g": 8.0, "carbs_100g": 41.0, "fat_100g": 2.0},
    "Toast": {"kcal_100g": 265, "protein_100g": 8.0, "carbs_100g": 50.0, "fat_100g": 3.0},
    "Milch": {"kcal_100g": 64, "protein_100g": 3.4, "carbs_100g": 4.8, "fat_100g": 3.7},
    "Haferflocken": {"kcal_100g": 370, "protein_100g": 13.0, "carbs_100g": 59.0, "fat_100g": 7.0},
    "Reis": {"kcal_100g": 130, "protein_100g": 2.7, "carbs_100g": 28.0, "fat_100g": 0.3},
    "Pasta": {"kcal_100g": 158, "protein_100g": 5.8, "carbs_100g": 30.0, "fat_100g": 0.9},
    "Whey Protein": {"kcal_100g": 400, "protein_100g": 80.0, "carbs_100g": 8.0, "fat_100g": 5.0},
    "Hähnchen": {"kcal_100g": 165, "protein_100g": 31.0, "carbs_100g": 0.0, "fat_100g": 3.6},
    "Kaffee": {"kcal_100g": 2, "protein_100g": 0.3, "carbs_100g": 0.0, "fat_100g": 0.0},
    "Espresso": {"kcal_100g": 9, "protein_100g": 0.6, "carbs_100g": 1.0, "fat_100g": 0.2},
    "Butter": {"kcal_100g": 717, "protein_100g": 0.9, "carbs_100g": 0.1, "fat_100g": 81.0},
    "Olivenöl": {"kcal_100g": 884, "protein_100g": 0.0, "carbs_100g": 0.0, "fat_100g": 100.0},
    "Apfel": {"kcal_100g": 52, "protein_100g": 0.3, "carbs_100g": 14.0, "fat_100g": 0.2},
    "Orange": {"kcal_100g": 47, "protein_100g": 0.9, "carbs_100g": 12.0, "fat_100g": 0.1},
    "Mandarine": {"kcal_100g": 53, "protein_100g": 0.8, "carbs_100g": 13.0, "fat_100g": 0.3},
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

# Stop words used for "unused span" detection in the LLM-trigger logic.
PARSER_STOPWORDS: set[str] = {
    "und", "mit", "ein", "eine", "einen", "einem", "einer",
    "der", "die", "das", "den", "dem", "mein", "meine",
    "ich", "hatte", "habe", "gegessen", "getrunken",
    "gefrühstückt", "gabs", "gab", "es", "war", "und",
    "ne", "nen",
}


def canonicalize(name: str) -> str:
    """Map a raw food token (case-insensitive) to its canonical name."""
    key = name.strip().lower()
    return FOOD_ALIASES.get(key, name.strip())


def find_compound(tokens: list[str]) -> tuple[str, int, int] | None:
    """Find longest compound match in tokens. Returns (canonical, start, end-exclusive)."""
    lowered = [t.lower() for t in tokens]
    best: tuple[str, int, int] | None = None
    best_len = 0
    for parts, canonical in COMPOUND_FOODS:
        # The window can be longer than `len(parts)` because we allow stopwords
        # like "mit" between the parts, so iterate every starting position.
        for i in range(0, len(lowered)):
            j = i
            ok = True
            for p in parts:
                while j < len(lowered) and lowered[j] in {"mit", "und", "&"}:
                    j += 1
                if j >= len(lowered) or lowered[j] != p:
                    ok = False
                    break
                j += 1
            if ok and (j - i) > best_len:
                best = (canonical, i, j)
                best_len = j - i
    return best


def get_portion_rule(food_name: str, unit_text: str) -> StaticPortionRule | None:
    return PORTION_RULES.get((food_name, unit_text))


def has_sized_variants(food_name: str, unit_text: str) -> bool:
    rule = PORTION_RULES.get((food_name, unit_text))
    return bool(rule and rule.sized)


def sized_variants(food_name: str, unit_text: str) -> list[StaticPortionRule]:
    """Return [small, medium, large] variants for a sized rule."""
    out = []
    for suffix in ("_s", "_m", "_l"):
        v = PORTION_RULES.get((food_name, unit_text + suffix))
        if v:
            out.append(v)
    return out
