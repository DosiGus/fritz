from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def portion_size_keyboard(food_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Klein", callback_data=f"portion:{food_name}:small"),
            InlineKeyboardButton("Normal", callback_data=f"portion:{food_name}:medium"),
            InlineKeyboardButton("Groß", callback_data=f"portion:{food_name}:large"),
        ],
        [InlineKeyboardButton("Eigene Menge", callback_data=f"portion:{food_name}:custom")],
        [InlineKeyboardButton("Abbrechen", callback_data="cancel")],
    ])


def meal_variant_keyboard(variants: list[dict]) -> InlineKeyboardMarkup:
    """variants: list of {"label": str, "callback": str}"""
    rows = []
    for variant in variants:
        rows.append([InlineKeyboardButton(variant["label"], callback_data=variant["callback"])])
    rows.append([InlineKeyboardButton("Abbrechen", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


def confirm_estimate_keyboard(log_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Ok", callback_data=f"confirm:{log_id}"),
            InlineKeyboardButton("✏️ Korrigieren", callback_data=f"edit:{log_id}"),
        ],
        [InlineKeyboardButton("🗑 Löschen", callback_data=f"delete:{log_id}")],
    ])


def yes_no_keyboard(yes_callback: str, no_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Ja", callback_data=yes_callback),
            InlineKeyboardButton("Nein", callback_data=no_callback),
        ]
    ])


def favorites_keyboard(templates: list[dict]) -> InlineKeyboardMarkup:
    """templates: list of {"name": str, "id": str}"""
    rows = []
    for t in templates:
        rows.append([InlineKeyboardButton(t["name"], callback_data=f"template:{t['id']}")])
    return InlineKeyboardMarkup(rows)


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Abbrechen", callback_data="cancel")]])


def milk_amount_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Schuss (10ml)", callback_data="milk:10"),
            InlineKeyboardButton("Etwas (30ml)", callback_data="milk:30"),
        ],
        [
            InlineKeyboardButton("Halbes Glas (125ml)", callback_data="milk:125"),
            InlineKeyboardButton("Eigene Menge", callback_data="milk:custom"),
        ],
        [InlineKeyboardButton("Abbrechen", callback_data="cancel")],
    ])
