"""Convert German written numbers to floats."""

_WORD_MAP: dict[str, float] = {
    "null": 0,
    "ein": 1,
    "eine": 1,
    "einen": 1,
    "einem": 1,
    "einer": 1,
    "eins": 1,
    "zwei": 2,
    "drei": 3,
    "vier": 4,
    "fünf": 5,
    "sechs": 6,
    "sieben": 7,
    "acht": 8,
    "neun": 9,
    "zehn": 10,
    "elf": 11,
    "zwölf": 12,
    "halb": 0.5,
    "halbe": 0.5,
    "halben": 0.5,
    "halber": 0.5,
    "anderthalb": 1.5,
    "eineinhalb": 1.5,
    "zweieinhalb": 2.5,
    "dreieinhalb": 3.5,
}


def word_to_number(word: str) -> float | None:
    """Return float for a German number word, or None if not recognized."""
    return _WORD_MAP.get(word.lower())


def parse_number(token: str) -> float | None:
    """Try to parse token as float or German number word."""
    try:
        return float(token.replace(",", "."))
    except ValueError:
        return word_to_number(token)
