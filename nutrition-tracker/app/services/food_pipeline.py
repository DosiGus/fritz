from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import User
from app.db.repositories.conversation_states import ConversationStateRepository
from app.db.repositories.food_logs import FoodLogItemRepository, FoodLogRepository
from app.schemas.bot_responses import BotResponse, Decision, LoggedItemSummary
from app.schemas.nutrition import NutritionMatch
from app.schemas.parsed_food import ParsedFoodItem, ParsedFoodMessage
from app.schemas.portions import ResolvedPortion
from app.services.audit_service import AuditService
from app.services.clarification_service import build_clarification, resolve_custom_amount
from app.services.confidence_engine import decide
from app.services.food_intent_pipeline import parse_with_food_intent_v2
from app.services.input_preprocessor import normalize_text
from app.services.nutrition_calculator import calculate_for_item, sum_items
from app.services.nutrition_matcher import find_ambiguous_matches, match as match_nutrition
from app.services.portion_engine import resolve_portion
from app.services.summary_service import build_daily_summary
from app.services.user_memory_service import memory_phrase
from app.utils.time import user_today


def handle_food_message(user_id: uuid.UUID, text: str, source: str = "text", db: Session | None = None) -> BotResponse:
    if db is None:
        raise ValueError("db session is required for handle_food_message")

    normalized = normalize_text(text)
    template_name_response = _resolve_template_name_if_pending(normalized, user_id, db)
    if template_name_response:
        return template_name_response

    custom_response = resolve_custom_amount(normalized, user_id=user_id, db=db)
    if custom_response:
        return custom_response

    state = ConversationStateRepository(db).get_active_for_user(user_id)
    retry_response = _resolve_nutrition_retry_if_pending(normalized, state, user_id, source, db)
    if retry_response:
        return retry_response

    edit_payload = _consume_edit_last_state(state, user_id, db)
    if edit_payload:
        source = "correction"
        state = None
    if state and state.state_type == "clarification":
        return BotResponse(text="Bitte nutze zuerst die Auswahlbuttons oder /cancel.")

    audit = AuditService(db)
    audit.log(event_type="pipeline_started", user_id=user_id, payload={"source": source, "text": normalized})

    parsed = parse_with_food_intent_v2(normalized, db=db, user_id=user_id)
    if parsed is None:
        audit.log(event_type="parser_unavailable", user_id=user_id, payload={"text": normalized})
        return BotResponse(
            text=(
                "Ich konnte deinen Eintrag gerade nicht verarbeiten. "
                "Bitte versuche es in einem Moment nochmal."
            )
        )

    portions = [resolve_portion(item, user_id=user_id, db=db) for item in parsed.items]
    matches = [_match_for_portion(portion, db) for portion in portions]
    _attach_food_match_clarifications(portions, matches, user_id, db)
    decision = decide(portions, matches)

    audit.log(
        event_type="confidence_decision",
        user_id=user_id,
        payload={
            "decision": decision.model_dump(),
            "parsed": parsed.model_dump(),
            "portions": [portion.model_dump() for portion in portions],
            "matches": [match.model_dump() if match else None for match in matches],
        },
    )

    payload = _payload(
        raw_text=normalized,
        source=source,
        parsed=parsed,
        portions=portions,
        matches=matches,
    )
    if edit_payload:
        payload["replaces_log_id"] = edit_payload.get("food_log_id")

    if decision.action in {"ask_short_clarification", "ask_detailed_clarification"}:
        no_match_response = _response_for_unmatched_nutrition(
            portions=portions,
            matches=matches,
            user_id=user_id,
            db=db,
            decision=decision,
            raw_text=normalized,
        )
        if no_match_response:
            return no_match_response
        return build_clarification(payload, user_id=user_id, db=db)

    return finalize_log_from_payload(payload, user_id=user_id, db=db, decision=decision)


def finalize_log_from_payload(
    payload: dict,
    user_id: uuid.UUID,
    db: Session,
    decision: Decision | None = None,
) -> BotResponse:
    parsed_items = [ParsedFoodItem.model_validate(item) for item in payload.get("parsed_items", [])]
    portions = [ResolvedPortion.model_validate(portion) for portion in payload.get("portions", [])]
    matches = [
        NutritionMatch.model_validate(match) if match is not None else None
        for match in payload.get("matches", [])
    ]
    if len(matches) < len(portions):
        matches.extend([None] * (len(portions) - len(matches)))

    decision = decision or decide(portions, matches)
    calculated_items = [
        _calculate_item(parsed_items[idx] if idx < len(parsed_items) else None, portion, matches[idx])
        for idx, portion in enumerate(portions)
    ]
    summary = sum_items(calculated_items)

    log = FoodLogRepository(db).create(
        user_id=user_id,
        raw_text=payload.get("raw_text"),
        source=payload.get("source", "text"),
        meal_type=payload.get("meal_type", "unknown"),
        total_kcal=summary.total_kcal,
        total_protein=summary.total_protein,
        total_carbs=summary.total_carbs,
        total_fat=summary.total_fat,
        confidence=decision.confidence,
        status="saved",
    )

    item_repo = FoodLogItemRepository(db)
    logged_items = []
    for idx, calculated in enumerate(calculated_items):
        parsed_item = parsed_items[idx] if idx < len(parsed_items) else None
        portion = portions[idx]
        match = matches[idx]
        item_repo.create(
            food_log_id=log.id,
            original_name=parsed_item.name if parsed_item else portion.item_name,
            canonical_name=portion.item_name,
            quantity=parsed_item.quantity if parsed_item else None,
            unit=parsed_item.unit if parsed_item else None,
            grams=portion.grams,
            kcal=calculated["kcal"],
            protein=calculated["protein"],
            carbs=calculated["carbs"],
            fat=calculated["fat"],
            source=match.source if match else "portion_default",
            source_id=match.source_id if match else None,
            confidence=portion.confidence,
            was_estimated=portion.was_estimated,
        )
        logged_items.append(
            LoggedItemSummary(
                name=portion.item_name,
                grams=portion.grams,
                ml=portion.ml,
                kcal=calculated["kcal"],
                was_estimated=portion.was_estimated,
            )
        )

    AuditService(db).log(
        event_type="food_log_saved",
        user_id=user_id,
        payload={"food_log_id": str(log.id), "decision": decision.model_dump()},
    )

    replaced_log_id = payload.get("replaces_log_id")
    if replaced_log_id:
        old_log = FoodLogRepository(db).get_by_id(uuid.UUID(replaced_log_id))
        if old_log and old_log.user_id == user_id and old_log.status == "saved":
            FoodLogRepository(db).update_status(old_log, "corrected")
            AuditService(db).log(
                event_type="food_log_corrected",
                user_id=user_id,
                payload={"old_food_log_id": str(old_log.id), "new_food_log_id": str(log.id)},
            )

    response_text = _format_saved_response(logged_items, summary, user_id, db)
    inline_keyboard: list[list[dict]] | None = _saved_log_keyboard(log.id)

    if decision.post_save_action == "ask_save_to_memory":
        memory_candidates = _build_memory_candidates(parsed_items, portions)
        if memory_candidates:
            ConversationStateRepository(db).delete_for_user(user_id)
            ConversationStateRepository(db).create(
                user_id=user_id,
                state_type="save_to_memory",
                payload={
                    "food_log_id": str(log.id),
                    "candidates": memory_candidates,
                },
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            )
            response_text = response_text + "\n\nSoll ich mir das für dich merken?"
            inline_keyboard = [
                [
                    {"text": "Ja, merken", "callback_data": "save_memory:yes"},
                    {"text": "Nein danke", "callback_data": "save_memory:no"},
                ]
            ]
            AuditService(db).log(
                event_type="save_to_memory_prompted",
                user_id=user_id,
                payload={"food_log_id": str(log.id), "candidates": memory_candidates},
            )

    return BotResponse(
        text=response_text,
        decision=decision,
        logged_items=logged_items,
        inline_keyboard=inline_keyboard,
    )


def _build_memory_candidates(
    parsed_items: list[ParsedFoodItem],
    portions: list[ResolvedPortion],
) -> list[dict]:
    """Pair parsed items with their resolved estimate so we can record both later."""
    candidates: list[dict] = []
    for idx, portion in enumerate(portions):
        if not portion.was_estimated:
            continue
        if portion.default_kcal is not None:
            continue
        if portion.grams is None and portion.ml is None:
            continue
        parsed = parsed_items[idx] if idx < len(parsed_items) else None
        if parsed is None:
            continue
        candidates.append(
            {
                "phrase": memory_phrase(parsed),
                "food_name": portion.item_name,
                "grams": portion.grams,
                "ml": portion.ml,
            }
        )
    return candidates


def _saved_log_keyboard(log_id: uuid.UUID) -> list[list[dict]]:
    return [
        [
            {"text": "Passt", "callback_data": f"confirm:{log_id}"},
            {"text": "Korrigieren", "callback_data": f"edit:{log_id}"},
        ],
        [
            {"text": "Als Favorit speichern", "callback_data": f"template_save:{log_id}"},
            {"text": "Löschen", "callback_data": f"delete:{log_id}"},
        ],
    ]


def _match_for_portion(portion: ResolvedPortion, db: Session) -> NutritionMatch | None:
    if portion.default_kcal is not None:
        return None
    return match_nutrition(portion.item_name, db=db)


def _attach_food_match_clarifications(
    portions: list[ResolvedPortion],
    matches: list[NutritionMatch | None],
    user_id: uuid.UUID,
    db: Session,
) -> None:
    for idx, portion in enumerate(portions):
        if portion.needs_clarification or portion.default_kcal is not None:
            continue
        candidates = find_ambiguous_matches(portion.item_name, db=db)
        if len(candidates) < 2:
            continue

        current = matches[idx] if idx < len(matches) else None
        top = candidates[0]
        if current and current.confidence >= 0.90 and current.canonical_name == top.canonical_name:
            continue

        portion.needs_clarification = True
        portion.confidence = min(float(portion.confidence), float(top.confidence), 0.69)
        portion.options = [
            {"label": candidate.canonical_name, "nutrition_match": candidate.model_dump()}
            for candidate in candidates[:4]
        ]
        if idx < len(matches):
            matches[idx] = None
        AuditService(db).log(
            event_type="food_match_clarification_needed",
            user_id=user_id,
            payload={"item_name": portion.item_name, "candidates": [c.model_dump() for c in candidates[:4]]},
        )


def _response_for_unmatched_nutrition(
    portions: list[ResolvedPortion],
    matches: list[NutritionMatch | None],
    user_id: uuid.UUID,
    db: Session,
    decision: Decision,
    raw_text: str,
) -> BotResponse | None:
    unmatched = []
    for idx, portion in enumerate(portions):
        match = matches[idx] if idx < len(matches) else None
        if portion.default_kcal is None and match is None and not portion.needs_clarification:
            unmatched.append(portion.item_name)

    if not unmatched:
        return None

    AuditService(db).log(
        event_type="nutrition_review_needed",
        user_id=user_id,
        payload={
            "raw_text": raw_text,
            "items": unmatched,
            "parsed_items": [portion.item_name for portion in portions],
            "decision": decision.model_dump(),
        },
    )
    ConversationStateRepository(db).delete_for_user(user_id)
    ConversationStateRepository(db).create(
        user_id=user_id,
        state_type="nutrition_retry",
        payload={
            "raw_text": raw_text,
            "unmatched": unmatched,
            "portions": [portion.model_dump() for portion in portions],
        },
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    item_list = "\n".join(f"- {name}" for name in unmatched)
    return BotResponse(
        text=(
            "Ich konnte dafür noch keine Nährwerte sicher finden:\n"
            f"{item_list}\n\n"
            "Du kannst mir einen anderen Namen senden, z. B. eine Marke oder ein bekannteres Lebensmittel."
        ),
        decision=decision,
        inline_keyboard=[
            [{"text": "Anderen Namen senden", "callback_data": "nutrition_retry:rename"}],
            [{"text": "Abbrechen", "callback_data": "cancel"}],
        ],
    )


def _resolve_nutrition_retry_if_pending(
    text: str,
    state,
    user_id: uuid.UUID,
    source: str,
    db: Session,
) -> BotResponse | None:
    if not state or state.state_type != "nutrition_retry":
        return None
    payload = dict(state.payload)
    retry_text = _retry_text_from_payload(text, payload)
    ConversationStateRepository(db).delete_for_user(user_id)
    AuditService(db).log(
        event_type="nutrition_retry_submitted",
        user_id=user_id,
        payload={
            "original_text": payload.get("raw_text"),
            "retry_text": retry_text,
            "replacement_name": text,
        },
    )
    return handle_food_message(user_id, retry_text, source=source, db=db)


def _retry_text_from_payload(replacement_name: str, payload: dict) -> str:
    portions = payload.get("portions") or []
    if not portions:
        return replacement_name

    portion = portions[0]
    grams = portion.get("grams")
    ml = portion.get("ml")
    if grams is not None:
        return f"{float(grams):g}g {replacement_name}"
    if ml is not None:
        return f"{float(ml):g}ml {replacement_name}"
    return replacement_name


def _consume_edit_last_state(state, user_id: uuid.UUID, db: Session) -> dict | None:
    if not state or state.state_type != "edit_last":
        return None
    payload = dict(state.payload)
    ConversationStateRepository(db).delete_for_user(user_id)
    AuditService(db).log(
        event_type="edit_last_replacement_received",
        user_id=user_id,
        payload={"old_food_log_id": payload.get("food_log_id")},
    )
    return payload


def _resolve_template_name_if_pending(text: str, user_id: uuid.UUID, db: Session) -> BotResponse | None:
    from app.services.meal_template_service import resolve_template_name

    return resolve_template_name(text, user_id, db)


def _payload(
    raw_text: str,
    source: str,
    parsed: ParsedFoodMessage,
    portions: list[ResolvedPortion],
    matches: list[NutritionMatch | None],
) -> dict:
    return {
        "raw_text": raw_text,
        "source": source,
        "meal_type": parsed.meal_type,
        "llm_called": parsed.llm_called,
        "parsed_items": [item.model_dump() for item in parsed.items],
        "portions": [portion.model_dump() for portion in portions],
        "matches": [match.model_dump() if match else None for match in matches],
    }


def _calculate_item(
    parsed_item: ParsedFoodItem | None,
    portion: ResolvedPortion,
    match: NutritionMatch | None,
) -> dict:
    if portion.default_kcal is not None:
        return {"kcal": round(portion.default_kcal, 1), "protein": 0.0, "carbs": 0.0, "fat": 0.0}

    grams = portion.grams
    if grams is None and portion.ml is not None:
        grams = portion.ml
    if grams is None or match is None:
        return {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}

    return calculate_for_item(match, grams)


def _format_saved_response(logged_items: list[LoggedItemSummary], summary, user_id: uuid.UUID, db: Session) -> str:
    lines = ["Gespeichert", "", "Items:"]
    for item in logged_items:
        amount = _format_amount(item)
        estimate = ", geschätzt" if item.was_estimated else ""
        kcal = f" ({item.kcal:.0f} kcal)" if item.kcal is not None else ""
        lines.append(f"- {amount}{item.name}{estimate}{kcal}")

    user = db.get(User, user_id)
    tz_name = user.timezone if user else None
    lines.extend([
        "",
        "Gesamt:",
        f"{summary.total_kcal:.0f} kcal",
        f"{summary.total_protein:.1f}g Protein",
        f"{summary.total_carbs:.1f}g Carbs",
        f"{summary.total_fat:.1f}g Fett",
        "",
        build_daily_summary(user_id, user_today(tz_name), db, tz_name=tz_name),
    ])
    return "\n".join(lines)


def _format_amount(item: LoggedItemSummary) -> str:
    if item.grams is not None:
        return f"{item.grams:g}g "
    if item.ml is not None:
        return f"{item.ml:g}ml "
    return ""
