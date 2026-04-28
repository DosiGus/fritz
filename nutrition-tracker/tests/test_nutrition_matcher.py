from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.services.nutrition_matcher import _from_usda_food, match


@pytest.fixture()
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


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


def test_match_rejects_meal_context_words_before_external_lookup(db):
    with patch("app.services.nutrition_matcher.OpenFoodFactsClient") as off_client:
        assert match("Frühstück", db=db) is None

    off_client.assert_not_called()
