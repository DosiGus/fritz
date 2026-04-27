import pytest

from app.utils.text_numbers import parse_number, word_to_number


class TestWordToNumber:
    def test_ein(self):
        assert word_to_number("ein") == 1.0

    def test_eine(self):
        assert word_to_number("eine") == 1.0

    def test_einen(self):
        assert word_to_number("einen") == 1.0

    def test_zwei(self):
        assert word_to_number("zwei") == 2.0

    def test_drei(self):
        assert word_to_number("drei") == 3.0

    def test_halb(self):
        assert word_to_number("halb") == 0.5

    def test_halbe(self):
        assert word_to_number("halbe") == 0.5

    def test_anderthalb(self):
        assert word_to_number("anderthalb") == 1.5

    def test_eineinhalb(self):
        assert word_to_number("eineinhalb") == 1.5

    def test_case_insensitive(self):
        assert word_to_number("ZWEI") == 2.0
        assert word_to_number("Eine") == 1.0

    def test_unknown_word(self):
        assert word_to_number("viele") is None

    def test_null(self):
        assert word_to_number("null") == 0.0


class TestParseNumber:
    def test_integer_string(self):
        assert parse_number("250") == 250.0

    def test_float_string(self):
        assert parse_number("0.5") == 0.5

    def test_comma_decimal(self):
        assert parse_number("1,5") == 1.5

    def test_german_word(self):
        assert parse_number("zwei") == 2.0

    def test_half(self):
        assert parse_number("halb") == 0.5

    def test_unknown_returns_none(self):
        assert parse_number("viele") is None

    def test_anderthalb(self):
        assert parse_number("anderthalb") == 1.5

    @pytest.mark.parametrize("word,expected", [
        ("vier", 4.0),
        ("fünf", 5.0),
        ("sechs", 6.0),
        ("sieben", 7.0),
        ("acht", 8.0),
        ("neun", 9.0),
        ("zehn", 10.0),
        ("elf", 11.0),
        ("zwölf", 12.0),
    ])
    def test_all_basic_words(self, word, expected):
        assert parse_number(word) == expected
