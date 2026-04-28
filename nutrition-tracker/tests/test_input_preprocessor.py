from app.services.input_preprocessor import normalize_text


def test_voice_asr_corrections_for_cappuccino_and_milk():
    text = normalize_text("zwei Kapucine mit Hamilsch")
    assert text == "zwei Cappuccino mit Hafermilch"
