"""Deterministic German food parser. Runs before the LLM and handles the common cases:
explicit weights ("250g Skyr"), piece counts ("2 Eier"), containers ("ein Teller Pasta"),
compound foods ("Dönerbox mit Pommes"), and "X mit Y" splits ("Kaffee mit Milch").

Pure function, no DB access — all lookups go through app.services.static_data.
"""

from __future__ import annotations

import re

from app.schemas.parsed_food import ParsedFoodItem, ParsedFoodMessage
from app.services.static_data import (
    FOOD_ALIASES,
    PARSER_STOPWORDS,
    canonicalize,
    find_compound,
    get_portion_rule,
)
from app.utils.text_numbers import parse_number
from app.utils.units import normalize_unit

# Containers that imply an ambiguous portion size, mapped to their normalized unit.
_CONTAINER_TO_UNIT: dict[str, str] = {
    "teller": "plate",
    "schüssel": "bowl",
    "bowl": "bowl",
    "glas": "glass",
    "tasse": "cup",
    "becher": "cup",
}

# Confidence baselines.
_CONF_EXPLICIT_WEIGHT = 0.95
_CONF_EXPLICIT_VOLUME = 0.95
_CONF_PIECE_KNOWN = 0.90
_CONF_SLICE = 0.85
_CONF_CONTAINER_KNOWN = 0.70
_CONF_CONTAINER_AMBIGUOUS = 0.50
_CONF_BOWL_NEEDS_VARIANT = 0.40
_CONF_PIECE_KCAL_DEFAULT = 0.70  # 1 Döner → kcal default
_CONF_COMPOUND_KCAL = 0.70
_CONF_BARE_FOOD = 0.50
_CONF_INGREDIENT_NO_QTY = 0.40

_NUMBER_WORD_RE = re.compile(
    r"\b(eine|einen|einem|einer|eins|ein|zwei|drei|vier|fünf|sechs|sieben|"
    r"acht|neun|zehn|elf|zwölf|halbe|halben|halber|halb|anderthalb|eineinhalb|"
    r"zweieinhalb|dreieinhalb)\b",
    re.IGNORECASE,
)

# "<num><unit>" or "<num> <unit>" with a weight/volume unit immediately attached.
_WEIGHT_VOLUME_RE = re.compile(
    r"(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g|ml|l)\b",
    re.IGNORECASE,
)


def parse(text: str) -> ParsedFoodMessage:
    """Run the rule parser. Returns a ParsedFoodMessage with per-item confidences."""
    text = text.strip()
    if not text:
        return ParsedFoodMessage(items=[], overall_confidence=0.0)

    segments = _split_segments(text)
    items: list[ParsedFoodItem] = []
    for seg in segments:
        items.extend(_parse_segment(seg))

    overall = (
        round(sum(i.confidence for i in items) / len(items), 2)
        if items
        else 0.0
    )
    return ParsedFoodMessage(items=items, overall_confidence=overall)


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------

def _split_segments(text: str) -> list[str]:
    """Split a message into per-item segments by comma, newlines, and 'und'.

    Decimal commas between digits ('1,5kg') are not separators.
    """
    # Match commas that are NOT between digits — those split items. Newlines and
    # 'und' always split.
    raw = re.split(r"(?<!\d),(?!\d)|\n|\bund\b", text, flags=re.IGNORECASE)
    return [s.strip() for s in raw if s and s.strip()]


# ---------------------------------------------------------------------------
# Segment parser
# ---------------------------------------------------------------------------

def _parse_segment(segment: str) -> list[ParsedFoodItem]:
    """Parse one segment into 1+ ParsedFoodItems.

    Order of attempts:
    1. Explicit weight/volume → "250g Skyr", "500ml Milch".
    2. Compound food via static map → "Dönerbox mit Pommes".
    3. Number + named food (alias) → "2 Eier", "1 Banane".
    4. Number + Scheibe + food → "eine Scheibe Brot".
    5. Number + container + food → "ein Teller Pasta", "eine Schüssel Haferflocken".
    6. Bowl + "mit X" needing meal-variant clarification → "eine Bowl mit Hähnchen".
    7. "X mit Y" split → "ein Kaffee mit Milch".
    8. Bare food → "1 Döner", "ein Kaffee".
    """
    seg = segment.strip().rstrip(".")
    if not seg:
        return []

    # 1. explicit weight/volume
    item = _try_explicit_weight_volume(seg)
    if item:
        return [item]

    tokens = _tokenize(seg)
    if not tokens:
        return []

    # 2. compound food
    compound = find_compound(tokens)
    if compound:
        canonical, start, end = compound
        # quantity = number that appears before the compound (default 1).
        qty = _extract_leading_quantity(tokens[:start])
        return [_build_compound_item(canonical, qty)]

    # 3. number + named food (single token food via alias)
    item = _try_number_plus_food(tokens)
    if item:
        return [item]

    # 4. number + Scheibe + food
    item = _try_slice_plus_food(tokens)
    if item:
        return [item]

    # 5. number + container + food
    container_item = _try_container_plus_food(tokens)
    if container_item:
        return [container_item]

    # 6. "X mit Y" split — "ein Kaffee mit Milch", "ein Teller mit Pasta", etc.
    split_items = _try_split_on_mit(tokens)
    if split_items:
        return split_items

    # 7. Bare food (article + name)
    bare = _try_bare_food(tokens)
    if bare:
        return [bare]

    # No match — return a low-confidence placeholder so downstream can decide.
    return [
        ParsedFoodItem(
            name=seg,
            quantity=None,
            unit="unknown",
            confidence=0.30,
        )
    ]


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------

def _try_explicit_weight_volume(seg: str) -> ParsedFoodItem | None:
    """Match '<num><unit>' optionally followed by a food name."""
    m = _WEIGHT_VOLUME_RE.search(seg)
    if not m:
        return None
    qty = float(m.group("num").replace(",", "."))
    raw_unit = m.group("unit").lower()
    norm = normalize_unit(raw_unit)

    # Anything before/after the match becomes the name candidate.
    before = seg[: m.start()].strip()
    after = seg[m.end():].strip()
    name_raw = (after or before).strip()
    if not name_raw:
        return None
    canonical = _resolve_name(name_raw)

    # Convert kg → g, l → ml so callers can rely on g/ml.
    if norm == "kg":
        qty *= 1000.0
        norm = "g"
    elif norm == "l":
        qty *= 1000.0
        norm = "ml"

    return ParsedFoodItem(
        name=canonical,
        quantity=qty,
        unit=norm,
        confidence=_CONF_EXPLICIT_WEIGHT if norm == "g" else _CONF_EXPLICIT_VOLUME,
    )


def _try_number_plus_food(tokens: list[str]) -> ParsedFoodItem | None:
    """Match: optional article-or-number + food name (single alias token)."""
    qty, rest_idx = _consume_quantity(tokens, 0)
    if rest_idx >= len(tokens):
        return None
    name_token = tokens[rest_idx]
    canonical = FOOD_ALIASES.get(name_token.lower())
    if not canonical:
        return None

    # Reject if the alias is also a container (handled separately).
    if name_token.lower() in _CONTAINER_TO_UNIT:
        return None

    # Trailing tokens after the name? If they're filler, accept; otherwise let
    # other strategies try.
    trailing = tokens[rest_idx + 1:]
    if any(t.lower() not in PARSER_STOPWORDS for t in trailing):
        return None

    rule = get_portion_rule(canonical, "piece")
    rule_cup = get_portion_rule(canonical, "cup")
    if rule and rule.default_grams:
        return ParsedFoodItem(
            name=canonical,
            quantity=qty or 1.0,
            unit="piece",
            confidence=_CONF_PIECE_KNOWN,
        )
    if rule and rule.default_kcal:
        return ParsedFoodItem(
            name=canonical,
            quantity=qty or 1.0,
            unit="piece",
            confidence=_CONF_PIECE_KCAL_DEFAULT,
        )
    if rule_cup and rule_cup.default_kcal:
        return ParsedFoodItem(
            name=canonical,
            quantity=qty or 1.0,
            unit="cup",
            confidence=_CONF_PIECE_KNOWN,
        )
    # No piece rule. Fall back to bare food with quantity.
    return ParsedFoodItem(
        name=canonical,
        quantity=qty or 1.0,
        unit="piece" if qty else "unknown",
        confidence=_CONF_BARE_FOOD,
    )


def _try_slice_plus_food(tokens: list[str]) -> ParsedFoodItem | None:
    """Match: <number> Scheibe(n) <food>."""
    qty, idx = _consume_quantity(tokens, 0)
    if idx >= len(tokens):
        return None
    if tokens[idx].lower() not in {"scheibe", "scheiben", "slice", "slices"}:
        return None
    if idx + 1 >= len(tokens):
        return None
    name_raw = " ".join(tokens[idx + 1:])
    canonical = _resolve_name(name_raw)
    return ParsedFoodItem(
        name=canonical,
        quantity=qty or 1.0,
        unit="slice",
        confidence=_CONF_SLICE,
    )


def _try_container_plus_food(tokens: list[str]) -> ParsedFoodItem | None:
    """Match: <number> <container> <food>.

    Container = teller / schüssel / glas / tasse / bowl / becher.
    If the food after the container has a known portion rule for that unit, use it.
    Otherwise mark as ambiguous (Pasta plate without size).
    """
    qty, idx = _consume_quantity(tokens, 0)
    if idx >= len(tokens):
        return None
    container = tokens[idx].lower()
    unit = _CONTAINER_TO_UNIT.get(container)
    if not unit:
        return None
    if idx + 1 >= len(tokens):
        # "ein Teller" alone — treat as bare bowl-ish food.
        return ParsedFoodItem(
            name=container.capitalize(),
            quantity=qty or 1.0,
            unit=unit,
            confidence=_CONF_CONTAINER_AMBIGUOUS,
        )

    rest_tokens = tokens[idx + 1:]

    # Bowl + "mit X" → meal_variant clarification candidate
    if container == "bowl":
        mit_idx = _find_token(rest_tokens, "mit")
        if mit_idx is not None:
            ingredient_tokens = rest_tokens[mit_idx + 1:]
            ingredient = " ".join(ingredient_tokens).strip()
            return ParsedFoodItem(
                name="Bowl",
                quantity=qty or 1.0,
                unit="bowl",
                notes=f"mit {ingredient}" if ingredient else None,
                confidence=_CONF_BOWL_NEEDS_VARIANT,
                needs_clarification=True,
                options=[],  # filled by portion engine
            )

    name_raw = " ".join(rest_tokens)
    canonical = _resolve_name(name_raw)
    rule = get_portion_rule(canonical, unit)
    if rule and rule.default_grams is not None:
        # Ambiguous (low-confidence) rule (e.g. Pasta plate) keeps confidence low.
        confidence = (
            _CONF_CONTAINER_AMBIGUOUS
            if rule.confidence < 0.6
            else _CONF_CONTAINER_KNOWN
        )
        return ParsedFoodItem(
            name=canonical,
            quantity=qty or 1.0,
            unit=unit,
            confidence=confidence,
        )
    if rule and rule.default_kcal is not None:
        return ParsedFoodItem(
            name=canonical,
            quantity=qty or 1.0,
            unit=unit,
            confidence=_CONF_CONTAINER_KNOWN,
        )

    # No rule for this food/container — still mark with the unit so portion engine
    # can decide what to do.
    return ParsedFoodItem(
        name=canonical or container.capitalize(),
        quantity=qty or 1.0,
        unit=unit,
        confidence=_CONF_CONTAINER_AMBIGUOUS,
    )


def _try_split_on_mit(tokens: list[str]) -> list[ParsedFoodItem] | None:
    """Match: <food1> mit <food2> where the two foods aren't a known compound.

    The first food typically resolves cleanly (e.g. Kaffee). The second is treated
    as an ingredient with no quantity → low-confidence ParsedFoodItem the portion
    engine will surface as a custom-amount clarification.
    """
    mit_idx = _find_token(tokens, "mit")
    if mit_idx is None:
        return None
    left = tokens[:mit_idx]
    right = tokens[mit_idx + 1:]
    if not left or not right:
        return None

    # Parse left side as a single food.
    left_item = _try_number_plus_food(left) or _try_bare_food(left)
    if not left_item:
        return None

    # Parse right side as ingredient with no quantity.
    right_name_raw = " ".join(right)
    right_canonical = _resolve_name(right_name_raw)

    # If the right side has its own quantity (e.g. "mit 30g Whey"), treat it as a
    # full second item.
    explicit_right = _try_explicit_weight_volume(right_name_raw)
    if explicit_right:
        return [left_item, explicit_right]

    note = f"in {left_item.name}"
    right_item = ParsedFoodItem(
        name=right_canonical,
        quantity=None,
        unit="unknown",
        notes=note,
        confidence=_CONF_INGREDIENT_NO_QTY,
        needs_clarification=True,
        options=[],
    )
    return [left_item, right_item]


def _try_bare_food(tokens: list[str]) -> ParsedFoodItem | None:
    """Match: optional <number> + named food (alias) without container or unit."""
    qty, idx = _consume_quantity(tokens, 0)
    if idx >= len(tokens):
        return None
    name_raw = " ".join(tokens[idx:])
    canonical = _resolve_name(name_raw)
    if canonical == name_raw and name_raw.lower() not in FOOD_ALIASES:
        # Try just the first token (e.g. "Döner" + trailing words handled elsewhere).
        canonical = FOOD_ALIASES.get(tokens[idx].lower())
        if not canonical:
            return None

    rule_piece = get_portion_rule(canonical, "piece")
    rule_cup = get_portion_rule(canonical, "cup")
    if rule_piece and rule_piece.default_kcal:
        return ParsedFoodItem(
            name=canonical,
            quantity=qty or 1.0,
            unit="piece",
            confidence=_CONF_PIECE_KCAL_DEFAULT,
        )
    if rule_cup and rule_cup.default_kcal:
        return ParsedFoodItem(
            name=canonical,
            quantity=qty or 1.0,
            unit="cup",
            confidence=_CONF_PIECE_KNOWN,
        )
    if rule_piece and rule_piece.default_grams:
        return ParsedFoodItem(
            name=canonical,
            quantity=qty or 1.0,
            unit="piece",
            confidence=_CONF_PIECE_KNOWN,
        )
    return ParsedFoodItem(
        name=canonical,
        quantity=qty or 1.0,
        unit="piece" if qty else "unknown",
        confidence=_CONF_BARE_FOOD,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_compound_item(canonical: str, qty: float | None) -> ParsedFoodItem:
    rule_piece = get_portion_rule(canonical, "piece")
    rule_portion = get_portion_rule(canonical, "portion")
    if rule_portion and rule_portion.default_kcal is not None:
        return ParsedFoodItem(
            name=canonical,
            quantity=qty or 1.0,
            unit="portion",
            confidence=0.75,
        )
    if rule_piece and rule_piece.default_kcal is not None:
        return ParsedFoodItem(
            name=canonical,
            quantity=qty or 1.0,
            unit="piece",
            confidence=_CONF_COMPOUND_KCAL,
        )
    if rule_piece and rule_piece.default_grams is not None:
        return ParsedFoodItem(
            name=canonical,
            quantity=qty or 1.0,
            unit="piece",
            confidence=_CONF_PIECE_KNOWN,
        )
    return ParsedFoodItem(
        name=canonical,
        quantity=qty or 1.0,
        unit="portion",
        confidence=_CONF_BARE_FOOD,
    )


def _tokenize(text: str) -> list[str]:
    """Word-level tokenizer that keeps Umlauts and digits, drops punctuation."""
    return re.findall(r"[A-Za-zÄÖÜäöüß]+|\d+(?:[.,]\d+)?", text)


def _consume_quantity(tokens: list[str], start: int) -> tuple[float | None, int]:
    """Try to consume a leading article/number/word-number. Returns (qty, next_index).

    Articles like "ein"/"eine" yield qty=1.0 without consuming a real number.
    """
    if start >= len(tokens):
        return None, start
    tok = tokens[start].lower()
    qty = parse_number(tok)
    if qty is not None:
        return qty, start + 1
    return None, start


def _extract_leading_quantity(tokens: list[str]) -> float | None:
    qty, _ = _consume_quantity(tokens, 0)
    return qty


def _find_token(tokens: list[str], target: str) -> int | None:
    target_lower = target.lower()
    for i, t in enumerate(tokens):
        if t.lower() == target_lower:
            return i
    return None


def _resolve_name(raw: str) -> str:
    """Map a raw food phrase to its canonical name via the alias table."""
    raw = raw.strip()
    if not raw:
        return raw
    direct = FOOD_ALIASES.get(raw.lower())
    if direct:
        return direct
    # Try the last token (e.g. "der Banane" → "Banane").
    parts = raw.split()
    if parts:
        last = FOOD_ALIASES.get(parts[-1].lower())
        if last:
            return last
    return canonicalize(raw)


def has_meal_verb(text: str) -> bool:
    """Detect meal-context verbs that lower the LLM-skip threshold."""
    return bool(re.search(
        r"\b(hatte|gegessen|gefrühstückt|gabs|gab\s+es|getrunken)\b",
        text,
        re.IGNORECASE,
    ))


def unused_span_chars(text: str, items: list[ParsedFoodItem]) -> int:
    """Approximate unused-text length for the LLM trigger.

    We can't track precise spans without rewriting the parser, so we approximate:
    take every alphanumeric token in the input, subtract every token that appears
    in any item's name (case-insensitive). What's left, joined by spaces, is the
    unused span.
    """
    tokens = _tokenize(text)
    consumed: set[str] = set()
    for item in items:
        for t in _tokenize(item.name):
            consumed.add(t.lower())
        if item.notes:
            for t in _tokenize(item.notes):
                consumed.add(t.lower())
    ignored_units = {
        "g", "kg", "ml", "l", "gramm", "kilo", "liter",
        "stück", "stk", "scheibe", "scheiben", "teller", "schüssel",
        "bowl", "glas", "tasse", "becher", "portion", "portionen",
    }
    leftover = []
    for token in tokens:
        lowered = token.lower()
        if lowered in consumed or lowered in PARSER_STOPWORDS or lowered in ignored_units:
            continue
        if parse_number(lowered) is not None:
            continue
        if re.match(r"^\d+(?:[.,]\d+)?$", token):
            continue
        leftover.append(token)
    return len(" ".join(leftover))
