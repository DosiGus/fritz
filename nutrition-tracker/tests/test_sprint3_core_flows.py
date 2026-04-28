import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from app.db.models import Base, FoodLog, FoodLogItem, MealTemplate
from app.db.repositories.conversation_states import ConversationStateRepository
from app.db.repositories.food_logs import FoodLogRepository
from app.db.repositories.nutrition_items import NutritionItemRepository
from app.db.repositories.users import UserRepository
from app.services.clarification_service import resolve_clarification
from app.services.edit_log_service import confirm_log, delete_log, start_edit_last, start_edit_log
from app.services.food_pipeline import handle_food_message
from app.services.meal_template_service import log_template, prompt_save_template_name
from app.schemas.parsed_food import ParsedFoodItem, ParsedFoodMessage


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
    return UserRepository(db).create(telegram_user_id=12345, first_name="Test")


def test_edit_last_replaces_previous_log(db, user):
    first = handle_food_message(user.id, "100g Skyr", db=db)
    assert first.decision.action == "direct_save"

    start = start_edit_last(user.id, db)
    assert "korrigierten Eintrag" in start.text

    replacement = handle_food_message(user.id, "200g Skyr", db=db)
    assert replacement.decision.action == "direct_save"

    logs = db.query(FoodLog).order_by(FoodLog.created_at.asc()).all()
    assert [log.status for log in logs] == ["corrected", "saved"]
    assert logs[1].source == "correction"
    assert float(logs[1].total_kcal) > float(logs[0].total_kcal)


def test_saved_log_response_exposes_feedback_actions(db, user):
    response = handle_food_message(user.id, "100g Skyr", db=db)
    log = FoodLogRepository(db).get_last_for_user(user.id)

    assert log is not None
    callbacks = [
        button["callback_data"]
        for row in response.inline_keyboard
        for button in row
    ]
    assert f"confirm:{log.id}" in callbacks
    assert f"edit:{log.id}" in callbacks
    assert f"template_save:{log.id}" in callbacks
    assert f"delete:{log.id}" in callbacks


def test_edit_specific_log_replaces_that_log(db, user):
    first = handle_food_message(user.id, "100g Skyr", db=db)
    assert first.decision.action == "direct_save"
    first_log = FoodLogRepository(db).get_last_for_user(user.id)
    second = handle_food_message(user.id, "1 Banane", db=db)
    assert second.decision.action in {"direct_save", "save_as_estimate"}

    start = start_edit_log(first_log.id, user.id, db)
    assert "korrigierten Eintrag" in start.text
    replacement = handle_food_message(user.id, "200g Skyr", db=db)
    assert replacement.decision.action == "direct_save"

    logs = db.query(FoodLog).order_by(FoodLog.logged_at.asc(), FoodLog.created_at.asc()).all()
    assert [log.status for log in logs] == ["corrected", "saved", "saved"]
    assert logs[-1].source == "correction"
    assert logs[-1].raw_text == "200g Skyr"


def test_delete_log_soft_deletes_and_removes_from_last_log(db, user):
    handle_food_message(user.id, "100g Skyr", db=db)
    first_log = FoodLogRepository(db).get_last_for_user(user.id)
    handle_food_message(user.id, "1 Banane", db=db)

    deleted = delete_log(first_log.id, user.id, db)

    assert "Gelöscht" in deleted.text
    assert FoodLogRepository(db).get_by_id(first_log.id).status == "deleted"
    assert FoodLogRepository(db).get_last_for_user(user.id).raw_text == "1 Banane"


def test_confirm_log_keeps_saved_status(db, user):
    handle_food_message(user.id, "100g Skyr", db=db)
    log = FoodLogRepository(db).get_last_for_user(user.id)

    response = confirm_log(log.id, user.id, db)

    assert "bleibt gespeichert" in response.text
    assert FoodLogRepository(db).get_by_id(log.id).status == "saved"


def test_ambiguous_food_match_creates_clarification_state(db, user):
    NutritionItemRepository(db).create("Proteinriegel Schoko", kcal_100g=390, protein_100g=30, carbs_100g=35, fat_100g=12)
    NutritionItemRepository(db).create("Proteinriegel Vanille", kcal_100g=370, protein_100g=31, carbs_100g=33, fat_100g=11)

    response = handle_food_message(user.id, "100g Proteinriegel", db=db)

    assert response.decision.action == "ask_short_clarification"
    assert "Welches Lebensmittel passt?" in response.text
    assert response.inline_keyboard[0][0]["callback_data"] == "clarify:0"
    state = ConversationStateRepository(db).get_active_for_user(user.id)
    assert state.state_type == "clarification"
    assert state.payload["question"]["type"] == "food_match"


def test_food_match_button_response_saves_log(db, user):
    NutritionItemRepository(db).create("Proteinriegel Schoko", kcal_100g=390, protein_100g=30, carbs_100g=35, fat_100g=12)
    NutritionItemRepository(db).create("Proteinriegel Vanille", kcal_100g=370, protein_100g=31, carbs_100g=33, fat_100g=11)
    handle_food_message(user.id, "100g Proteinriegel", db=db)

    response = resolve_clarification("clarify:0", user.id, db)

    assert response.decision.action in {"direct_save", "save_as_estimate"}
    log = FoodLogRepository(db).get_last_for_user(user.id)
    assert log is not None
    item = db.query(FoodLogItem).filter(FoodLogItem.food_log_id == log.id).one()
    assert item.canonical_name in {"Proteinriegel Schoko", "Proteinriegel Vanille"}
    assert item.source != "portion_default"


def test_template_save_and_log_recreates_items(db, user):
    saved = handle_food_message(user.id, "250g Skyr, 1 Banane", db=db)
    assert saved.logged_items
    log = FoodLogRepository(db).get_last_for_user(user.id)

    prompt = prompt_save_template_name(log.id, user.id, db)
    assert "Wie soll" in prompt.text
    named = handle_food_message(user.id, "Standardfrühstück", db=db)
    assert "Standardmahlzeit" in named.text

    template_id = db.query(MealTemplate).one().id
    template_response = log_template(template_id, user.id, db)

    assert template_response.decision.action == "direct_save"
    template_log = FoodLogRepository(db).get_last_for_user(user.id)
    assert template_log.source == "template"
    assert db.query(FoodLogItem).filter(FoodLogItem.food_log_id == template_log.id).count() == 2


def test_user_memory_flow_still_upgrades_second_log(db, user):
    first = handle_food_message(user.id, "eine Schüssel Haferflocken", db=db)
    assert first.decision.action == "save_as_estimate"
    assert first.decision.post_save_action == "ask_save_to_memory"

    memory = resolve_clarification("save_memory:yes", user.id, db)
    assert "Gemerkt" in memory.text

    second = handle_food_message(user.id, "eine Schüssel Haferflocken", db=db)
    assert second.decision.action == "direct_save"


def test_unknown_food_with_explicit_amount_is_not_saved_as_zero_kcal(db, user):
    response = handle_food_message(user.id, "100g Fantasienudel", db=db)

    assert response.decision.action == "ask_short_clarification"
    assert "keine Nährwerte" in response.text
    assert response.inline_keyboard
    assert FoodLogRepository(db).get_last_for_user(user.id) is None
    state = ConversationStateRepository(db).get_active_for_user(user.id)
    assert state.state_type == "nutrition_retry"


def test_unknown_food_retry_uses_alternate_name_and_saves(db, user):
    NutritionItemRepository(db).create(
        "Skyr",
        kcal_100g=60,
        protein_100g=11,
        carbs_100g=4,
        fat_100g=0.2,
        verified=True,
    )
    first = handle_food_message(user.id, "100g Fantasienudel", db=db)
    assert "keine Nährwerte" in first.text

    retry = handle_food_message(user.id, "Skyr", db=db)

    assert retry.decision.action == "direct_save"
    log = FoodLogRepository(db).get_last_for_user(user.id)
    assert log is not None
    item = db.query(FoodLogItem).filter(FoodLogItem.food_log_id == log.id).one()
    assert item.canonical_name == "Skyr"
    assert float(item.grams) == 100


def test_voice_like_component_text_does_not_double_count_milk(db, user):
    llm_result = ParsedFoodMessage(
        meal_type="breakfast",
        items=[
            ParsedFoodItem(name="Cappuccino", quantity=None, unit="unknown", notes="normale Größe", confidence=0.8),
            ParsedFoodItem(
                name="H Milch Die H Milch hat 3,6 Fett Die Cappuccinos hatten normale Größe",
                quantity=None,
                unit="unknown",
                notes="in Cappuccino",
                confidence=0.4,
                needs_clarification=True,
            ),
            ParsedFoodItem(name="Milch", quantity=None, unit="unknown", notes="3,6% Fett", confidence=0.5),
        ],
        overall_confidence=0.53,
        llm_called=True,
    )

    text = "Frühstück: 2 Cappuccino mit H-Milch. Die H-Milch hat 3,6% Fett. Die Cappuccinos hatten normale Größe."
    with patch("app.services.food_pipeline.llm_parse", return_value=llm_result):
        response = handle_food_message(user.id, text, source="voice", db=db)

    assert response.decision.action in {"direct_save", "save_as_estimate"}
    log = FoodLogRepository(db).get_last_for_user(user.id)
    assert log is not None
    assert float(log.total_kcal) == pytest.approx(162, abs=1)
    items = db.query(FoodLogItem).filter(FoodLogItem.food_log_id == log.id).all()
    assert len(items) == 1
    assert items[0].canonical_name == "Cappuccino"
    assert float(items[0].quantity) == 2
    assert float(items[0].grams) == pytest.approx(360)


def test_skyr_bowl_with_toppings_is_decomposed_into_calculable_components(db, user):
    llm_result = ParsedFoodMessage(
        meal_type="snack",
        items=[
            ParsedFoodItem(name="skyr bowl", quantity=None, unit="bowl", confidence=0.8),
            ParsedFoodItem(name="tk mangos", role="component", parent_name="skyr bowl", confidence=0.8),
            ParsedFoodItem(name="honig", role="component", parent_name="skyr bowl", confidence=0.8),
        ],
        overall_confidence=0.8,
        llm_called=True,
    )

    text = "dazu noch eine kleine skyr bowl mit tk mangos und honig"
    with patch("app.services.food_pipeline.llm_parse", return_value=llm_result):
        response = handle_food_message(user.id, text, source="text", db=db)

    assert response.decision.action in {"direct_save", "save_as_estimate"}
    log = FoodLogRepository(db).get_last_for_user(user.id)
    assert log is not None
    items = db.query(FoodLogItem).filter(FoodLogItem.food_log_id == log.id).order_by(FoodLogItem.created_at.asc()).all()
    assert [item.canonical_name for item in items] == ["Skyr", "Mango", "Honig"]
    assert [float(item.grams) for item in items] == pytest.approx([150, 60, 10])
    assert float(log.total_kcal) == pytest.approx(96 + 36 + 30.4, abs=1)
    assert [item.name for item in response.logged_items] == ["Skyr", "Mango", "Honig"]
