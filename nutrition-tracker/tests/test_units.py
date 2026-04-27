import pytest

from app.utils.units import is_volume_unit, is_weight_unit, normalize_unit, to_grams, to_ml


class TestNormalizeUnit:
    @pytest.mark.parametrize("raw,expected", [
        ("g", "g"),
        ("G", "g"),
        ("gr", "g"),
        ("gramm", "g"),
        ("Gramm", "g"),
        ("kg", "kg"),
        ("kilogramm", "kg"),
        ("kilo", "kg"),
        ("ml", "ml"),
        ("ML", "ml"),
        ("milliliter", "ml"),
        ("l", "l"),
        ("liter", "l"),
        ("scheibe", "slice"),
        ("Scheibe", "slice"),
        ("scheiben", "slice"),
        ("stück", "piece"),
        ("stk", "piece"),
        ("el", "tbsp"),
        ("Esslöffel", "tbsp"),
        ("tl", "tsp"),
        ("teelöffel", "tsp"),
        ("glas", "glass"),
        ("Glas", "glass"),
        ("tasse", "cup"),
        ("Cup", "cup"),
        ("teller", "plate"),
        ("Teller", "plate"),
        ("schüssel", "bowl"),
        ("Bowl", "bowl"),
        ("portion", "portion"),
        ("Portionen", "portion"),
    ])
    def test_normalize(self, raw, expected):
        assert normalize_unit(raw) == expected

    def test_known_becher_maps_to_cup(self):
        assert normalize_unit("Becher") == "cup"

    def test_unknown_returns_lowercased(self):
        assert normalize_unit("Schüsselchen") == "schüsselchen"


class TestToGrams:
    def test_grams_passthrough(self):
        assert to_grams(250, "g") == 250.0

    def test_gramm(self):
        assert to_grams(100, "gramm") == 100.0

    def test_kg_to_grams(self):
        assert to_grams(1, "kg") == 1000.0

    def test_half_kg(self):
        assert to_grams(0.5, "kg") == 500.0

    def test_ml_returns_none(self):
        assert to_grams(500, "ml") is None

    def test_piece_returns_none(self):
        assert to_grams(2, "stück") is None

    def test_unknown_unit_returns_none(self):
        assert to_grams(1, "bowl") is None


class TestToMl:
    def test_ml_passthrough(self):
        assert to_ml(500, "ml") == 500.0

    def test_liter_to_ml(self):
        assert to_ml(1, "l") == 1000.0

    def test_half_liter(self):
        assert to_ml(0.5, "liter") == 500.0

    def test_grams_returns_none(self):
        assert to_ml(250, "g") is None

    def test_piece_returns_none(self):
        assert to_ml(1, "stück") is None


class TestIsWeightUnit:
    @pytest.mark.parametrize("unit", ["g", "gramm", "kg", "kilogramm"])
    def test_weight_units(self, unit):
        assert is_weight_unit(unit) is True

    @pytest.mark.parametrize("unit", ["ml", "l", "piece", "slice", "bowl"])
    def test_non_weight_units(self, unit):
        assert is_weight_unit(unit) is False


class TestIsVolumeUnit:
    @pytest.mark.parametrize("unit", ["ml", "milliliter", "l", "liter"])
    def test_volume_units(self, unit):
        assert is_volume_unit(unit) is True

    @pytest.mark.parametrize("unit", ["g", "kg", "piece", "slice"])
    def test_non_volume_units(self, unit):
        assert is_volume_unit(unit) is False
