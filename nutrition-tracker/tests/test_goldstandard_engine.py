import json
from pathlib import Path

import pytest

from app.services.confidence_engine import decide
from app.services.nutrition_matcher import match
from app.services.parser_merge import should_call_llm
from app.services.portion_engine import resolve_portion
from app.services.rule_parser import parse


FIXTURES = json.loads(Path("tests/fixtures/goldstandard.json").read_text())


@pytest.mark.parametrize("fixture", FIXTURES, ids=[case["input"] for case in FIXTURES])
def test_goldstandard_decisions_and_portions(fixture):
    parsed = parse(fixture["input"])
    llm_called = should_call_llm(fixture["input"], parsed)
    portions = [resolve_portion(item) for item in parsed.items]
    matches = [None if portion.default_kcal is not None else match(portion.item_name) for portion in portions]
    decision = decide(portions, matches)

    assert llm_called is fixture["llm_called"]
    assert decision.action == fixture["decision"]
    assert len(portions) == len(fixture["items"])

    for idx, expected in enumerate(fixture["items"]):
        parsed_item = parsed.items[idx]
        portion = portions[idx]

        assert portion.item_name == expected["name"]
        assert parsed_item.unit == expected["unit"]
        assert portion.was_estimated is expected.get("was_estimated", portion.was_estimated)
        assert portion.needs_clarification is expected.get("needs_clarification", False)
        assert portion.confidence == pytest.approx(expected["confidence"], abs=0.10)

        if "grams" in expected and expected["grams"] is not None:
            assert portion.grams == pytest.approx(expected["grams"], rel=0.10)
        if "ml" in expected and expected["ml"] is not None:
            assert portion.ml == pytest.approx(expected["ml"], rel=0.10)
        if "default_kcal" in expected:
            assert portion.default_kcal == pytest.approx(expected["default_kcal"], rel=0.10)
        if expected.get("options"):
            assert [option["label"] for option in portion.options] == [
                option["label"] for option in expected["options"]
            ]


def test_goldstandard_llm_skip_cost_contract():
    must_skip = {0, 1, 2, 4, 5, 6, 7, 8}
    for idx in must_skip:
        fixture = FIXTURES[idx]
        assert should_call_llm(fixture["input"], parse(fixture["input"])) is False
