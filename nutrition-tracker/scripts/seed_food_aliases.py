"""Seed food_aliases with common German food names → canonical names."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db.session import SessionLocal
from app.db.repositories.nutrition_items import FoodAliasRepository

FOOD_ALIASES = [
    # (alias, canonical_name, language, confidence)
    ("skyr",                "Skyr",              "de", 0.95),
    ("magerquark",          "Magerquark",        "de", 0.95),
    ("quark",               "Magerquark",        "de", 0.80),
    ("ei",                  "Ei",                "de", 0.95),
    ("eier",                "Ei",                "de", 0.95),
    ("vollei",              "Ei",                "de", 0.90),
    ("banane",              "Banane",            "de", 0.95),
    ("bananen",             "Banane",            "de", 0.95),
    ("brot",                "Brot",              "de", 0.90),
    ("vollkornbrot",        "Vollkornbrot",      "de", 0.95),
    ("toast",               "Toast",             "de", 0.95),
    ("toastbrot",           "Toast",             "de", 0.90),
    ("milch",               "Milch",             "de", 0.95),
    ("kuhmilch",            "Milch",             "de", 0.90),
    ("haferflocken",        "Haferflocken",      "de", 0.95),
    ("oats",                "Haferflocken",      "en", 0.90),
    ("porridge",            "Haferflocken",      "de", 0.80),
    ("reis",                "Reis",              "de", 0.95),
    ("gekochter reis",      "Reis",              "de", 0.95),
    ("pasta",               "Pasta",             "de", 0.95),
    ("nudeln",              "Pasta",             "de", 0.95),
    ("spaghetti",           "Pasta",             "de", 0.90),
    ("penne",               "Pasta",             "de", 0.90),
    ("whey",                "Whey Protein",      "de", 0.90),
    ("whey protein",        "Whey Protein",      "en", 0.95),
    ("proteinpulver",       "Whey Protein",      "de", 0.80),
    ("döner",               "Döner",             "de", 0.95),
    ("döner kebab",         "Döner",             "de", 0.95),
    ("chicken bowl",        "Chicken Bowl Reis", "de", 0.80),
    ("hähnchen bowl",       "Chicken Bowl Reis", "de", 0.80),
    ("hähnchen",            "Hähnchen",          "de", 0.95),
    ("huhn",                "Hähnchen",          "de", 0.90),
    ("chicken",             "Hähnchen",          "en", 0.90),
    ("kaffee",              "Kaffee",            "de", 0.95),
    ("espresso",            "Espresso",          "de", 0.95),
    ("butter",              "Butter",            "de", 0.95),
    ("olivenöl",            "Olivenöl",          "de", 0.95),
    ("apfel",               "Apfel",             "de", 0.95),
    ("orange",              "Orange",            "de", 0.95),
    ("mandarine",           "Mandarine",         "de", 0.95),
]


def run() -> None:
    with SessionLocal() as db:
        repo = FoodAliasRepository(db)
        existing = {a.alias.lower() for a in repo.list_all()}
        created = 0
        for alias, canonical_name, language, confidence in FOOD_ALIASES:
            if alias.lower() in existing:
                continue
            repo.create(alias=alias, canonical_name=canonical_name, language=language, confidence=confidence)
            created += 1
        print(f"Seeded {created} food aliases ({len(existing)} already existed).")


if __name__ == "__main__":
    run()
