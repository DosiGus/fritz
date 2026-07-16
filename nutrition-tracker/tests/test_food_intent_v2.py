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


def test_food_intent_adapter_keeps_components_attached_to_parent():
    """Composite entries with components are returned as parent + role=component children."""
    intent = FoodIntent(
        meal_type="lunch",
        entries=[
            FoodIntentEntry(
                type="composite",
                name="Falafel Sandwich",
                quantity=1,
                unit="piece",
                components=[
                    FoodIntentComponent(name="Hummus", role="component", confidence=0.8),
                    FoodIntentComponent(name="Halloumi", role="component", confidence=0.8),
                ],
                confidence=0.9,
            )
        ],
        confidence=0.9,
    )

    parsed = food_intent_to_parsed(intent, [])

    assert [item.name for item in parsed.items] == ["Falafel Sandwich", "Hummus", "Halloumi"]
    assert parsed.items[0].role == "main"
    assert parsed.items[1].role == "component"
    assert parsed.items[1].parent_name == "Falafel Sandwich"


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


def test_cappuccino_milk_component_with_fat_percent_does_not_double_count(db, user):
    intent = FoodIntent(
        meal_type="breakfast",
        entries=[
            FoodIntentEntry(
                type="single",
                name="Cappuccino",
                quantity=2,
                unit="cup",
                components=[
                    FoodIntentComponent(
                        name="H-Milch",
                        amount_value=3.5,
                        amount_unit="unknown",
                        portion_hint="in Cappuccino",
                        confidence=0.8,
                    )
                ],
                confidence=0.88,
            )
        ],
        confidence=0.88,
    )

    with patch("app.services.food_intent_pipeline.parse_food_intent", return_value=intent):
        response = handle_food_message(user.id, "zwei Cappuccino mit H-Milch 3,5%", source="voice", db=db)

    log = FoodLogRepository(db).get_last_for_user(user.id)
    assert log is not None
    items = db.query(FoodLogItem).filter(FoodLogItem.food_log_id == log.id).all()
    assert [item.canonical_name for item in items] == ["Cappuccino"]
    assert [item.name for item in response.logged_items] == ["Cappuccino"]


def test_falafel_sandwich_components_dont_double_count(db, user):
    """Components inside a composite parent must not be saved as separate food items.

    This prevents the "Falafel Sandwich + Hummus + Halloumi + Auberginencreme" double-counting bug.
    """
    intent = FoodIntent(
        meal_type="lunch",
        entries=[
            FoodIntentEntry(
                type="composite",
                name="Falafel Sandwich",
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
                confidence=0.85,
            ),
            FoodIntentEntry(
                type="single",
                name="Mayo",
                quantity=15,
                unit="g",
                modifiers=["etwas"],
                confidence=0.7,
            ),
        ],
        confidence=0.85,
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
    assert [item.name for item in response.logged_items] == ["Falafel Sandwich", "Süßkartoffelpommes", "Mayo"]


def test_simple_food_pipeline_does_not_call_openai_when_key_missing(db, user):
    with patch("app.services.food_intent_pipeline.parse_food_intent") as mock_openai:
        response = handle_food_message(user.id, "250g Skyr", db=db)

    mock_openai.assert_not_called()
    assert response.decision.action == "direct_save"
    assert FoodLogRepository(db).get_last_for_user(user.id) is not None


def test_food_pipeline_falls_back_to_deterministic_parse_when_openai_fails(db, user):
    with patch("app.services.food_intent_pipeline.parse_food_intent", return_value=None):
        response = handle_food_message(user.id, "250g Skyr", db=db)

    assert response.decision.action == "direct_save"
    assert FoodLogRepository(db).get_last_for_user(user.id) is not None


def test_food_pipeline_returns_friendly_error_when_no_parser_can_handle_input(db, user):
    with patch("app.services.food_intent_pipeline.parse_food_intent", return_value=None):
        response = handle_food_message(user.id, "Falafel-Sandwich mit Hummus", db=db)

    assert "nicht verarbeiten" in response.text
    assert FoodLogRepository(db).get_last_for_user(user.id) is None
