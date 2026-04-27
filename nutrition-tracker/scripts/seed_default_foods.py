"""Seed nutrition_items with common German default foods (kcal/protein/carbs/fat per 100g)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db.session import SessionLocal
from app.db.repositories.nutrition_items import NutritionItemRepository

DEFAULT_FOODS = [
    # (canonical_name, kcal_100g, protein_100g, carbs_100g, fat_100g)
    ("Skyr",             64,  11.0,  4.0,  0.2),
    ("Magerquark",       67,  12.0,  4.1,  0.2),
    ("Ei",              155,  13.0,  1.1, 11.0),
    ("Banane",           89,   1.1, 23.0,  0.3),
    ("Brot",            250,   8.0, 47.0,  2.0),
    ("Vollkornbrot",    220,   8.0, 41.0,  2.0),
    ("Toast",           265,   8.0, 50.0,  3.0),
    ("Milch",            64,   3.4,  4.8,  3.7),
    ("Haferflocken",    370,  13.0, 59.0,  7.0),
    ("Reis",            130,   2.7, 28.0,  0.3),
    ("Pasta",           158,   5.8, 30.0,  0.9),
    ("Whey Protein",    400,  80.0,  8.0,  5.0),
    ("Hähnchen",        165,  31.0,  0.0,  3.6),
    ("Kaffee",            2,   0.3,  0.0,  0.0),
    ("Espresso",          9,   0.6,  1.0,  0.2),
    ("Butter",          717,   0.9,  0.1, 81.0),
    ("Olivenöl",        884,   0.0,  0.0, 100.0),
    ("Apfel",            52,   0.3, 14.0,  0.2),
    ("Orange",           47,   0.9, 12.0,  0.1),
    ("Mandarine",        53,   0.8, 13.0,  0.3),
    ("Lachs",           208,  20.0,  0.0, 13.0),
    ("Thunfisch",       116,  26.0,  0.0,  1.0),
    ("Rindfleisch",     215,  26.0,  0.0, 12.0),
    ("Tomate",           18,   0.9,  3.9,  0.2),
    ("Gurke",            16,   0.7,  3.6,  0.1),
    ("Paprika",          31,   1.0,  6.0,  0.3),
    ("Spinat",           23,   2.9,  3.6,  0.4),
    ("Brokkoli",         34,   2.8,  7.0,  0.4),
    ("Kartoffel",        77,   2.0, 17.0,  0.1),
    ("Süßkartoffel",     86,   1.6, 20.0,  0.1),
    ("Avocado",         160,   2.0,  9.0, 15.0),
    ("Linsen",          353,  25.0, 60.0,  1.1),
    ("Kichererbsen",    364,  19.0, 61.0,  6.0),
    ("Joghurt",          59,   3.5,  4.7,  3.3),
    ("Griechischer Joghurt", 97, 9.0, 4.0, 5.0),
]


def run() -> None:
    with SessionLocal() as db:
        repo = NutritionItemRepository(db)
        created = 0
        for canonical_name, kcal, protein, carbs, fat in DEFAULT_FOODS:
            existing = repo.get_by_canonical_name(canonical_name)
            if existing:
                continue
            repo.create(
                canonical_name=canonical_name,
                kcal_100g=kcal,
                protein_100g=protein,
                carbs_100g=carbs,
                fat_100g=fat,
                source="default_seed",
                verified=True,
            )
            created += 1
        print(f"Seeded {created} default foods.")


if __name__ == "__main__":
    run()
