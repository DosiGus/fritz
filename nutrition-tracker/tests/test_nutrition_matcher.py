from app.services.nutrition_matcher import _from_usda_food


def test_usda_rejects_implausible_milk_match():
    food = {
        "fdcId": 2048491,
        "description": "MILK CHOCOLATE CANDY",
        "foodNutrients": [
            {"nutrientName": "Energy", "value": 550},
            {"nutrientName": "Protein", "value": 17.5},
            {"nutrientName": "Carbohydrate, by difference", "value": 35},
            {"nutrientName": "Total lipid (fat)", "value": 42.5},
        ],
    }

    assert _from_usda_food("Hafermilch", food) is None
