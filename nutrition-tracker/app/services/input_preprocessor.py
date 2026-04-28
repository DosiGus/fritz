import re
import unicodedata

_ASR_REPLACEMENTS = [
    (re.compile(r"\bkapucine\b", re.IGNORECASE), "Cappuccino"),
    (re.compile(r"\bkapuzine\b", re.IGNORECASE), "Cappuccino"),
    (re.compile(r"\bkappucino\b", re.IGNORECASE), "Cappuccino"),
    (re.compile(r"\bkapuccino\b", re.IGNORECASE), "Cappuccino"),
    (re.compile(r"\bhamilsch\b", re.IGNORECASE), "Hafermilch"),
    (re.compile(r"\bhamilch\b", re.IGNORECASE), "Hafermilch"),
    (re.compile(r"\bhafer milch\b", re.IGNORECASE), "Hafermilch"),
    (re.compile(r"\bh milch\b", re.IGNORECASE), "H-Milch"),
]


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    for pattern, replacement in _ASR_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text
