"""Seed portion_rules with standard German food portions."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db.session import SessionLocal
from app.db.repositories.portions import PortionRuleRepository

PORTION_RULES = [
    # (food_name, unit_text, default_grams, min_grams, max_grams, default_kcal, confidence)
    ("Banane",          "piece",    120,  80,  180, None, 0.90),
    ("Ei",              "piece",     60,  50,   80, None, 0.90),
    ("Toast",           "slice",     25,  20,   35, None, 0.90),
    ("Brot",            "slice",     45,  30,   60, None, 0.85),
    ("Milch",           "glass",    250, 200,  300, None, 0.85),
    ("Haferflocken",    "bowl",      80,  50,  120, None, 0.80),
    ("Reis",            "portion",  180, 120,  250, None, 0.80),
    ("Pasta",           "plate",    350, 250,  500, None, 0.50),
    ("Pasta",           "plate_s",  250, 200,  300, None, 0.85),
    ("Pasta",           "plate_m",  350, 300,  420, None, 0.85),
    ("Pasta",           "plate_l",  500, 420,  650, None, 0.85),
    ("Döner",           "piece",   None,  None, None, 650, 0.70),
    ("Dönerbox Pommes", "piece",   None,  None, None, 850, 0.70),
    ("Chicken Bowl Reis",   "portion", None, None, None, 700, 0.75),
    ("Chicken Bowl Salat",  "portion", None, None, None, 450, 0.75),
    ("Kaffee",          "cup",     None,   None, None, 5,  0.90),
    ("Apfel",           "piece",    180,   120,  250, None, 0.85),
    ("Orange",          "piece",    200,   150,  280, None, 0.85),
    ("Butter",          "tbsp",      15,    10,   20, None, 0.80),
    ("Olivenöl",        "tbsp",      14,    10,   18, None, 0.80),
]


def run() -> None:
    with SessionLocal() as db:
        repo = PortionRuleRepository(db)
        existing = {(r.food_name, r.unit_text) for r in repo.list_all()}
        created = 0
        for food_name, unit_text, default_grams, min_grams, max_grams, default_kcal, confidence in PORTION_RULES:
            if (food_name, unit_text) in existing:
                continue
            repo.create(
                food_name=food_name,
                unit_text=unit_text,
                default_grams=default_grams,
                min_grams=min_grams,
                max_grams=max_grams,
                default_kcal=default_kcal,
                confidence=confidence,
                source="seed",
            )
            created += 1
        print(f"Seeded {created} portion rules ({len(existing)} already existed).")


if __name__ == "__main__":
    run()
