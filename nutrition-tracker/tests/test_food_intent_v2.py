import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, FoodLogItem
from app.db.repositories.food_logs import FoodLogRepository
from app.db.repositories.users import UserRepository
from app.schemas.food_intent import FoodIntent, FoodIntentComponent, FoodIntentEntry
from app.services.food_intent_adapter import food_intent_to_parsed
from app.services.food_pipeline import handle_food_message
from app.services.hard_fact_extractor import extract_hard_facts
from app.services.openai_food_intent_parser import parse_food_intent


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


@pytest.fixture()
def user(db):
    return UserRepository(db).create(telegram_user_id=54321, first_name="Intent")


def test_hard_facts_extract_quantity_size_and_meal():
    facts = extract_hard_facts("Ich hatte zum Frühstück zwei kleine Cappuccino")

    assert any(f.type == "meal_type" and f.value == "breakfast" for f in facts)
    assert any(f.type == "quantity" and f.value == 2 for f in facts)
    assert any(f.type == "portion_size" and f.value == "small" for f in facts)


def test_food_intent_adapter_preserves_single_entry_quantity_fact():
    intent = FoodIntent(
        meal_type="breakfast",
        entries=[FoodIntentEntry(type="single", name="Cappuccino", quantity=None, unit="cup", confidence=0.8)],
        confidence=0.8,
    )
    facts = extract_hard_facts("zwei Cappuccino mit H-Milch")

    parsed = food_intent_to_parsed(intent, facts)

    assert parsed.items[0].name == "Cappuccino"
    assert parsed.items[0].quantity == 2


def test_openai_food_intent_parser_uses_structured_outputs():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"meal_type":"snack","entries":[{"type":"single","name":"Skyr",'
                        '"quantity":250,"unit":"g","portion_size":"unknown","components":[],'
                        '"modifiers":[],"confidence":0.95}],"uncertainties":[],"confidence":0.95}'
                    )
                }
            }
        ]
    }

    with (
        patch("app.services.openai_food_intent_parser.settings.openai_api_key", "test-key"),
        patch("httpx.post", return_value=mock_response) as mock_post,
    ):
        intent = parse_food_intent("250g Skyr", extract_hard_facts("250g Skyr"))

    assert intent is not None
    assert intent.entries[0].name == "Skyr"
    payload = mock_post.call_args.kwargs["json"]
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["name"] == "food_intent"


def test_food_intent_v2_cappuccino_flow(db, user):
    intent = FoodIntent(
        meal_type="breakfast",
        entries=[
            FoodIntentEntry(
                type="single",
                name="Cappuccino",
                quantity=2,
                unit="cup",
                modifiers=["mit H-Milch 3,5%"],
                confidence=0.86,
            )
        ],
        confidence=0.86,
    )

    with patch("app.services.food_intent_pipeline.parse_food_intent", return_value=intent):
        response = handle_food_message(user.id, "Ich hatte zum Frühstück zwei Cappuccino mit H-Milch", db=db)

    log = FoodLogRepository(db).get_last_for_user(user.id)
    assert log is not None
    assert float(log.total_kcal) == pytest.approx(162, abs=1)
    item = db.query(FoodLogItem).filter(FoodLogItem.food_log_id == log.id).one()
    assert item.canonical_name == "Cappuccino"
    assert float(item.quantity) == 2
    assert response.logged_items[0].name == "Cappuccino"


def test_food_intent_v2_drops_meal_context_item_from_correction(db, user):
    intent = FoodIntent(
        meal_type="breakfast",
        entries=[
            FoodIntentEntry(type="single", name="Cappuccino", quantity=2, unit="piece", confidence=1.0),
            FoodIntentEntry(type="single", name="Frühstück", quantity=None, unit="unknown", confidence=0.9),
        ],
        confidence=0.95,
    )

    with patch("app.services.food_intent_pipeline.parse_food_intent", return_value=intent):
        response = handle_food_message(user.id, "2 cappuccino zum frühstück", db=db)

    log = FoodLogRepository(db).get_last_for_user(user.id)
    items = db.query(FoodLogItem).filter(FoodLogItem.food_log_id == log.id).all()
    assert response.decision.action in {"direct_save", "save_as_estimate"}
    assert [item.canonical_name for item in items] == ["Cappuccino"]
    assert float(items[0].grams) == pytest.approx(360)
    assert float(log.total_kcal) == pytest.approx(162, abs=1)


def test_food_intent_v2_decomposes_skyr_bowl_components(db, user):
    intent = FoodIntent(
        meal_type="snack",
        entries=[
            FoodIntentEntry(
                type="composite",
                name="Skyr Bowl",
                unit="bowl",
                portion_size="small",
                components=[
                    FoodIntentComponent(name="Skyr", role="base", confidence=0.9),
                    FoodIntentComponent(name="TK Mango", role="topping", confidence=0.8),
                    FoodIntentComponent(name="Honig", role="topping", confidence=0.8),
                ],
                confidence=0.85,
            )
        ],
        confidence=0.85,
    )

    with patch("app.services.food_intent_pipeline.parse_food_intent", return_value=intent):
        response = handle_food_message(user.id, "kleine skyr bowl mit tk mango und honig", db=db)

    log = FoodLogRepository(db).get_last_for_user(user.id)
    assert log is not None
    items = db.query(FoodLogItem).filter(FoodLogItem.food_log_id == log.id).order_by(FoodLogItem.created_at.asc()).all()
    assert [item.canonical_name for item in items] == ["Skyr", "Mango", "Honig"]
    assert [float(item.grams) for item in items] == pytest.approx([150, 60, 10])
    assert [item.name for item in response.logged_items] == ["Skyr", "Mango", "Honig"]


def test_food_intent_v2_decomposes_oatmeal_bowl(db, user):
    intent = FoodIntent(
        meal_type="breakfast",
        entries=[
            FoodIntentEntry(
                type="composite",
                name="Oatmeal Bowl",
                unit="bowl",
                portion_size="small",
                components=[
                    FoodIntentComponent(name="Haferflocken", role="base", confidence=0.9),
                    FoodIntentComponent(name="Banane", role="topping", confidence=0.8),
                    FoodIntentComponent(name="Honig", role="topping", confidence=0.8),
                ],
                confidence=0.85,
            )
        ],
        confidence=0.85,
    )

    with patch("app.services.food_intent_pipeline.parse_food_intent", return_value=intent):
        response = handle_food_message(user.id, "kleine porridge bowl mit banane und honig", db=db)

    log = FoodLogRepository(db).get_last_for_user(user.id)
    items = db.query(FoodLogItem).filter(FoodLogItem.food_log_id == log.id).order_by(FoodLogItem.created_at.asc()).all()
    assert [item.canonical_name for item in items] == ["Haferflocken", "Banane", "Honig"]
    assert [float(item.grams) for item in items] == pytest.approx([40, 60, 5])
    assert [item.name for item in response.logged_items] == ["Haferflocken", "Banane", "Honig"]


def test_food_intent_v2_decomposes_smoothie(db, user):
    intent = FoodIntent(
        meal_type="snack",
        entries=[
            FoodIntentEntry(
                type="composite",
                name="Smoothie",
                unit="glass",
                portion_size="medium",
                components=[
                    FoodIntentComponent(name="Banane", role="component", confidence=0.85),
                    FoodIntentComponent(name="Milch", role="component", confidence=0.85),
                    FoodIntentComponent(name="Whey Protein", role="component", confidence=0.85),
                ],
                confidence=0.85,
            )
        ],
        confidence=0.85,
    )

    with patch("app.services.food_intent_pipeline.parse_food_intent", return_value=intent):
        response = handle_food_message(user.id, "smoothie mit banane milch und whey", db=db)

    log = FoodLogRepository(db).get_last_for_user(user.id)
    items = db.query(FoodLogItem).filter(FoodLogItem.food_log_id == log.id).order_by(FoodLogItem.created_at.asc()).all()
    assert [item.canonical_name for item in items] == ["Banane", "Milch", "Whey Protein"]
    assert [float(item.grams) for item in items] == pytest.approx([120, 250, 25])
    assert [item.name for item in response.logged_items] == ["Banane", "Milch", "Whey Protein"]


def test_food_intent_v2_decomposes_rice_bowl(db, user):
    intent = FoodIntent(
        meal_type="lunch",
        entries=[
            FoodIntentEntry(
                type="composite",
                name="Rice Bowl",
                unit="bowl",
                portion_size="medium",
                components=[
                    FoodIntentComponent(name="Reis", role="base", confidence=0.9),
                    FoodIntentComponent(name="Hähnchen", role="component", confidence=0.85),
                    FoodIntentComponent(name="Avocado", role="component", confidence=0.85),
                ],
                confidence=0.85,
            )
        ],
        confidence=0.85,
    )

    with patch("app.services.food_intent_pipeline.parse_food_intent", return_value=intent):
        response = handle_food_message(user.id, "reis bowl mit hähnchen und avocado", db=db)

    log = FoodLogRepository(db).get_last_for_user(user.id)
    items = db.query(FoodLogItem).filter(FoodLogItem.food_log_id == log.id).order_by(FoodLogItem.created_at.asc()).all()
    assert [item.canonical_name for item in items] == ["Reis", "Hähnchen", "Avocado"]
    assert [float(item.grams) for item in items] == pytest.approx([180, 150, 80])
    assert [item.name for item in response.logged_items] == ["Reis", "Hähnchen", "Avocado"]


def test_food_intent_v2_decomposes_pasta_plate(db, user):
    intent = FoodIntent(
        meal_type="dinner",
        entries=[
            FoodIntentEntry(
                type="composite",
                name="Pasta",
                unit="plate",
                portion_size="large",
                components=[
                    FoodIntentComponent(name="Pasta", role="base", confidence=0.9),
                    FoodIntentComponent(name="Hähnchen", role="component", confidence=0.85),
                    FoodIntentComponent(name="Tomate", role="component", confidence=0.85),
                    FoodIntentComponent(name="Olivenöl", role="component", confidence=0.85),
                ],
                confidence=0.85,
            )
        ],
        confidence=0.85,
    )

    with patch("app.services.food_intent_pipeline.parse_food_intent", return_value=intent):
        response = handle_food_message(user.id, "großer teller pasta mit hähnchen tomaten und öl", db=db)

    log = FoodLogRepository(db).get_last_for_user(user.id)
    items = db.query(FoodLogItem).filter(FoodLogItem.food_log_id == log.id).order_by(FoodLogItem.created_at.asc()).all()
    assert [item.canonical_name for item in items] == ["Pasta", "Hähnchen", "Tomate", "Olivenöl"]
    assert [float(item.grams) for item in items] == pytest.approx([500, 180, 180, 15])
    assert [item.name for item in response.logged_items] == ["Pasta", "Hähnchen", "Tomate", "Olivenöl"]


def test_food_intent_v2_keeps_sandwich_components_inside_parent_and_scopes_sides(db, user):
    intent = FoodIntent(
        meal_type="lunch",
        entries=[
            FoodIntentEntry(
                type="composite",
                name="Falafel-Sandwich",
                quantity=1,
                unit="piece",
                components=[
                    FoodIntentComponent(name="Hummus", role="component", confidence=0.8),
                    FoodIntentComponent(name="Halloumi", role="component", confidence=0.8),
                    FoodIntentComponent(name="Auberginencreme", role="component", confidence=0.8),
                ],
                confidence=0.9,
            ),
            FoodIntentEntry(
                type="single",
                name="Süßkartoffelpommes",
                quantity=1,
                unit="portion",
                portion_size="small",
                confidence=0.9,
            ),
            FoodIntentEntry(
                type="single",
                name="Mayo",
                quantity=None,
                unit="unknown",
                modifiers=["etwas"],
                confidence=0.7,
            ),
            FoodIntentEntry(type="single", name="dazu", quantity=None, unit="unknown", confidence=0.5),
        ],
        confidence=0.9,
    )

    text = (
        "Mittagessen hatte ich ein Falafel-Sandwich mit Hummus, Halloumi und "
        "Auberginencreme und dazu noch eine kleine Portion Süßkartoffelpommes mit etwas Mayo."
    )
    with patch("app.services.food_intent_pipeline.parse_food_intent", return_value=intent):
        response = handle_food_message(user.id, text, source="voice", db=db)

    log = FoodLogRepository(db).get_last_for_user(user.id)
    items = db.query(FoodLogItem).filter(FoodLogItem.food_log_id == log.id).order_by(FoodLogItem.created_at.asc()).all()
    assert [item.canonical_name for item in items] == ["Falafel Sandwich", "Süßkartoffelpommes", "Mayo"]
    assert [float(item.grams) for item in items] == pytest.approx([300, 120, 15])
    assert float(log.total_kcal) == pytest.approx(1116, abs=2)
    assert float(log.total_kcal) < 1300
    assert [item.name for item in response.logged_items] == ["Falafel Sandwich", "Süßkartoffelpommes", "Mayo"]


def test_food_intent_v2_falls_back_to_legacy_pipeline(db, user):
    with (
        patch("app.services.food_intent_pipeline.settings.food_intent_v2_enabled", True),
        patch("app.services.food_intent_pipeline.parse_food_intent", return_value=None),
    ):
        response = handle_food_message(user.id, "250g Skyr", db=db)

    assert response.decision.action == "direct_save"
    log = FoodLogRepository(db).get_last_for_user(user.id)
    assert log is not None
    assert float(log.total_kcal) == pytest.approx(160, abs=1)
