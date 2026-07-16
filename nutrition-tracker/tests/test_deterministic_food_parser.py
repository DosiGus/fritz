from app.services.deterministic_food_parser import parse_deterministic_food
from app.services.hard_fact_extractor import extract_hard_facts


def _parse(text):
    return parse_deterministic_food(text, extract_hard_facts(text))


def test_amount_food_parses_without_llm():
    parsed = _parse("100g Skyr")

    assert parsed is not None
    assert parsed.llm_called is False
    assert parsed.items[0].name == "Skyr"
    assert parsed.items[0].quantity == 100
    assert parsed.items[0].unit == "g"


def test_quantity_food_defaults_to_piece():
    parsed = _parse("1 Banane")

    assert parsed is not None
    assert parsed.items[0].name == "Banane"
    assert parsed.items[0].quantity == 1
    assert parsed.items[0].unit == "piece"


def test_plural_food_is_canonicalized():
    parsed = _parse("2 Eier")

    assert parsed is not None
    assert parsed.items[0].name == "Ei"
    assert parsed.items[0].quantity == 2
    assert parsed.items[0].unit == "piece"


def test_mixed_simple_list_parses_all_items():
    parsed = _parse("250g Skyr, 1 Banane und 30g Whey")

    assert parsed is not None
    assert [(item.name, item.quantity, item.unit) for item in parsed.items] == [
        ("Skyr", 250, "g"),
        ("Banane", 1, "piece"),
        ("Whey Protein", 30, "g"),
    ]


def test_meal_type_is_preserved_from_hard_facts():
    parsed = _parse("zum Frühstück 250g Skyr")

    assert parsed is not None
    assert parsed.meal_type == "breakfast"
    assert parsed.items[0].name == "Skyr"


def test_container_unit_parses_known_food():
    parsed = _parse("eine Schüssel Haferflocken")

    assert parsed is not None
    assert parsed.items[0].name == "Haferflocken"
    assert parsed.items[0].quantity == 1
    assert parsed.items[0].unit == "bowl"


def test_counted_cappuccino_uses_cup_unit():
    parsed = _parse("2 Cappuccino")

    assert parsed is not None
    assert parsed.items[0].name == "Cappuccino"
    assert parsed.items[0].quantity == 2
    assert parsed.items[0].unit == "cup"


def test_meal_type_suffix_is_stripped_from_food_name():
    parsed = _parse("2 Cappuccino zum Frühstück")

    assert parsed is not None
    assert parsed.meal_type == "breakfast"
    assert parsed.items[0].name == "Cappuccino"
    assert parsed.items[0].quantity == 2
    assert parsed.items[0].unit == "cup"


def test_decimal_comma_volume_beer_does_not_split_into_fake_items():
    parsed = _parse("Zwei kleine Heineken Bier 0,33 ml.")

    assert parsed is not None
    assert len(parsed.items) == 1
    assert parsed.items[0].name == "Bier"
    assert parsed.items[0].quantity == 660
    assert parsed.items[0].unit == "ml"


def test_complex_composite_is_left_for_openai():
    parsed = _parse("Falafel-Sandwich mit Hummus und Halloumi")

    assert parsed is None
