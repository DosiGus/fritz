from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.repositories.conversation_states import ConversationStateRepository
from app.schemas.bot_responses import BotResponse, Decision
from app.schemas.portions import ResolvedPortion
from app.services.audit_service import AuditService
from app.services.user_memory_service import record as record_memory


def build_clarification(pending_items: list[dict] | dict, user_id: uuid.UUID, db: Session) -> BotResponse:
    """Persist pending pipeline state and return the next one-question prompt."""
    payload = _coerce_payload(pending_items)
    target_idx = _first_pending_index(payload)
    if target_idx is None:
        from app.services.food_pipeline import finalize_log_from_payload

        return finalize_log_from_payload(payload, user_id=user_id, db=db)

    question = _question_for_payload(payload, target_idx)
    payload["target_index"] = target_idx
    payload["question"] = question

    state_repo = ConversationStateRepository(db)
    state_repo.delete_for_user(user_id)
    state_repo.create(
        user_id=user_id,
        state_type="clarification",
        payload=payload,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )

    AuditService(db).log(
        event_type="clarification_asked",
        user_id=user_id,
        payload={"target_index": target_idx, "question": question["text"]},
    )

    return BotResponse(
        text=question["text"],
        decision=Decision(
            action=question["decision_action"],
            confidence=question["confidence"],
            reason=question["type"],
        ),
        inline_keyboard=question["keyboard"],
    )


def resolve_clarification(callback_data: str, user_id: uuid.UUID, db: Session) -> BotResponse:
    state_repo = ConversationStateRepository(db)
    state = state_repo.get_active_for_user(user_id)
    if not state:
        return BotResponse(text="Diese Rückfrage ist abgelaufen. Sende den Eintrag bitte nochmal.")

    if callback_data.startswith("save_memory:") and state.state_type == "save_to_memory":
        return _resolve_save_to_memory(callback_data, state, user_id, db)

    payload = dict(state.payload)
    if callback_data == "cancel":
        state_repo.delete_for_user(user_id)
        return BotResponse(text="Abgebrochen.")

    option = _option_from_callback(callback_data, payload)
    if option is None:
        return BotResponse(text="Diese Auswahl konnte ich nicht zuordnen.")

    target_idx = int(payload.get("target_index", 0))
    if option.get("type") == "custom":
        payload["awaiting_custom_amount"] = True
        state_repo.delete_for_user(user_id)
        state_repo.create(
            user_id=user_id,
            state_type="custom_amount",
            payload=payload,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        return BotResponse(text="Sende mir die Menge als Gramm oder ml, z. B. 80g oder 125ml.")

    _apply_option(payload, target_idx, option)
    AuditService(db).log(
        event_type="clarification_resolved",
        user_id=user_id,
        payload={"target_index": target_idx, "option": option},
    )

    state_repo.delete_for_user(user_id)
    if _first_pending_index(payload) is not None:
        return build_clarification(payload, user_id=user_id, db=db)

    from app.services.food_pipeline import finalize_log_from_payload

    return finalize_log_from_payload(payload, user_id=user_id, db=db)


def _resolve_save_to_memory(
    callback_data: str,
    state,
    user_id: uuid.UUID,
    db: Session,
) -> BotResponse:
    state_repo = ConversationStateRepository(db)
    answer = callback_data.split(":", 1)[1]
    payload = dict(state.payload)
    candidates = payload.get("candidates") or []

    if answer == "yes":
        recorded = 0
        for candidate in candidates:
            phrase = candidate.get("phrase")
            food_name = candidate.get("food_name")
            if not phrase or not food_name:
                continue
            record_memory(
                phrase=phrase,
                food_name=food_name,
                grams=candidate.get("grams"),
                ml=candidate.get("ml"),
                user_id=user_id,
                db=db,
            )
            recorded += 1

        AuditService(db).log(
            event_type="save_to_memory_confirmed",
            user_id=user_id,
            payload={
                "food_log_id": payload.get("food_log_id"),
                "recorded": recorded,
                "candidates": candidates,
            },
        )
        state_repo.delete_for_user(user_id)
        return BotResponse(text="Gemerkt. Beim nächsten Mal nutze ich diese Menge automatisch.")

    AuditService(db).log(
        event_type="save_to_memory_declined",
        user_id=user_id,
        payload={"food_log_id": payload.get("food_log_id")},
    )
    state_repo.delete_for_user(user_id)
    return BotResponse(text="OK, merke ich mir nicht.")


def resolve_custom_amount(text: str, user_id: uuid.UUID, db: Session) -> BotResponse | None:
    state_repo = ConversationStateRepository(db)
    state = state_repo.get_active_for_user(user_id)
    if not state or state.state_type != "custom_amount":
        return None

    amount = _parse_amount(text)
    if not amount:
        return BotResponse(text="Ich brauche eine Menge wie 80g oder 125ml.")

    payload = dict(state.payload)
    target_idx = int(payload.get("target_index", 0))
    _apply_option(payload, target_idx, amount)
    _record_memory_from_custom_amount(payload, target_idx, user_id, db)
    state_repo.delete_for_user(user_id)

    if _first_pending_index(payload) is not None:
        return build_clarification(payload, user_id=user_id, db=db)

    from app.services.food_pipeline import finalize_log_from_payload

    return finalize_log_from_payload(payload, user_id=user_id, db=db)


def _record_memory_from_custom_amount(
    payload: dict,
    target_idx: int,
    user_id: uuid.UUID,
    db: Session,
) -> None:
    """User typed an explicit gram/ml value — strongest learning signal we get."""
    parsed_items = payload.get("parsed_items") or []
    portions = payload.get("portions") or payload.get("items") or []
    if target_idx >= len(parsed_items) or target_idx >= len(portions):
        return

    from app.services.user_memory_service import memory_phrase

    parsed = parsed_items[target_idx]
    portion = portions[target_idx]
    food_name = portion.get("item_name") or parsed.get("name")
    grams = portion.get("grams")
    ml = portion.get("ml")
    if (grams is None and ml is None) or not food_name:
        return

    phrase = memory_phrase(parsed)
    if not phrase:
        return

    record_memory(
        phrase=phrase,
        food_name=food_name,
        grams=grams,
        ml=ml,
        user_id=user_id,
        db=db,
    )
    AuditService(db).log(
        event_type="memory_recorded",
        user_id=user_id,
        payload={
            "phrase": phrase,
            "food_name": food_name,
            "grams": grams,
            "ml": ml,
            "source": "custom_amount",
        },
    )


def _coerce_payload(pending_items: list[dict] | dict) -> dict:
    if isinstance(pending_items, dict):
        return pending_items
    if len(pending_items) == 1 and "payload" in pending_items[0]:
        return pending_items[0]["payload"]
    return {"items": pending_items}


def _first_pending_index(payload: dict) -> int | None:
    portions = payload.get("portions") or payload.get("items") or []
    for idx, portion in enumerate(portions):
        if portion.get("needs_clarification"):
            return idx
    return None


def _question_for_payload(payload: dict, target_idx: int) -> dict:
    portions = payload.get("portions") or payload.get("items") or []
    portion = portions[target_idx]
    options = portion.get("options") or [{"label": "Eigene Menge", "type": "custom"}]
    question_type = _question_type(options)
    text = {
        "meal_variant": "Welche Variante passt am ehesten?",
        "custom_amount": "Welche Menge passt?",
        "portion_size": "Welche Portion passt am besten?",
    }[question_type]

    return {
        "type": question_type,
        "text": text,
        "confidence": float(portion.get("confidence") or 0.5),
        "decision_action": (
            "ask_detailed_clarification" if question_type == "meal_variant" else "ask_short_clarification"
        ),
        "keyboard": _keyboard_for_options(options),
    }


def _question_type(options: list[dict]) -> str:
    labels = {str(option.get("label", "")).lower() for option in options}
    if {"reis + hähnchen", "salat + hähnchen"} & labels:
        return "meal_variant"
    if any("ml" in option for option in options):
        return "custom_amount"
    return "portion_size"


def _keyboard_for_options(options: list[dict]) -> list[list[dict]]:
    rows = []
    row = []
    for idx, option in enumerate(options):
        row.append({"text": str(option.get("label", "Auswahl")), "callback_data": f"clarify:{idx}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"text": "Abbrechen", "callback_data": "cancel"}])
    return rows


def _option_from_callback(callback_data: str, payload: dict) -> dict | None:
    if callback_data.startswith("clarify:"):
        idx = int(callback_data.split(":", 1)[1])
        target_idx = int(payload.get("target_index", 0))
        portions = payload.get("portions") or payload.get("items") or []
        options = portions[target_idx].get("options") or []
        return options[idx] if 0 <= idx < len(options) else None

    if callback_data.startswith("milk:"):
        value = callback_data.split(":", 1)[1]
        return {"type": "custom"} if value == "custom" else {"label": f"{value}ml", "ml": float(value)}

    if callback_data.startswith("portion:"):
        _, _, size = callback_data.split(":", 2)
        size_map = {"small": 250, "medium": 350, "large": 500}
        return {"type": "custom"} if size == "custom" else {"label": size, "grams": size_map[size]}

    return None


def _apply_option(payload: dict, target_idx: int, option: dict) -> None:
    portions = payload.get("portions") or payload.get("items") or []
    portion = dict(portions[target_idx])

    if "grams" in option:
        portion["grams"] = float(option["grams"])
        portion["confidence"] = max(float(portion.get("confidence") or 0.0), 0.85)
    if "ml" in option:
        portion["ml"] = float(option["ml"])
        portion["grams"] = float(option["ml"])
        portion["confidence"] = max(float(portion.get("confidence") or 0.0), 0.80)
    if "default_kcal" in option:
        portion["default_kcal"] = float(option["default_kcal"])
        portion["confidence"] = max(float(portion.get("confidence") or 0.0), 0.75)
        new_name = _meal_variant_name(option)
        if new_name:
            portion["item_name"] = new_name
            if payload.get("parsed_items"):
                payload["parsed_items"][target_idx]["name"] = new_name

    portion["needs_clarification"] = False
    portion["was_estimated"] = True
    portion["options"] = []
    portions[target_idx] = ResolvedPortion.model_validate(portion).model_dump()
    payload["portions"] = portions


def _meal_variant_name(option: dict) -> str | None:
    label = option.get("label")
    name_map = {
        "Reis + Hähnchen": "Chicken Bowl Reis",
        "Salat + Hähnchen": "Chicken Bowl Salat",
        "Poke / Fisch": "Poke Bowl",
    }
    return name_map.get(label)


def _parse_amount(text: str) -> dict | None:
    match = re.search(r"(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>g|gramm|ml|l)\b", text, re.IGNORECASE)
    if not match:
        return None
    value = float(match.group("num").replace(",", "."))
    unit = match.group("unit").lower()
    if unit == "l":
        return {"label": f"{value:g}l", "ml": value * 1000}
    if unit == "ml":
        return {"label": f"{value:g}ml", "ml": value}
    return {"label": f"{value:g}g", "grams": value}
