from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.repositories.conversation_states import ConversationStateRepository
from app.db.repositories.food_logs import FoodLogItemRepository, FoodLogRepository
from app.schemas.bot_responses import BotResponse, Decision, LoggedItemSummary
from app.schemas.nutrition import NutritionMatch
from app.schemas.parsed_food import ParsedFoodItem, ParsedFoodMessage
from app.schemas.portions import ResolvedPortion
from app.services import rule_parser
from app.services.audit_service import AuditService
from app.services.clarification_service import build_clarification, resolve_custom_amount
from app.services.confidence_engine import decide
from app.services.input_preprocessor import normalize_text
from app.services.llm_parser import parse as llm_parse
from app.services.nutrition_calculator import calculate_for_item, sum_items
from app.services.nutrition_matcher import match as match_nutrition
from app.services.parser_merge import mark_llm_skipped, merge, should_call_llm
from app.services.portion_engine import resolve_portion
from app.services.summary_service import build_daily_summary
from app.services.user_memory_service import memory_phrase


def handle_food_message(user_id: uuid.UUID, text: str, source: str = "text", db: Session | None = None) -> BotResponse:
    if db is None:
        raise ValueError("db session is required for handle_food_message")

    normalized = normalize_text(text)
    custom_response = resolve_custom_amount(normalized, user_id=user_id, db=db)
    if custom_response:
        return custom_response

    state = ConversationStateRepository(db).get_active_for_user(user_id)
    if state and state.state_type == "clarification":
        return BotResponse(text="Bitte nutze zuerst die Auswahlbuttons oder /cancel.")

    audit = AuditService(db)
    audit.log(event_type="pipeline_started", user_id=user_id, payload={"source": source, "text": normalized})

    rule_result = rule_parser.parse(normalized)
    if should_call_llm(normalized, rule_result):
        llm_result = llm_parse(normalized)
        parsed = merge(rule_result, llm_result, original_text=normalized, db=db, user_id=user_id)
    else:
        parsed = mark_llm_skipped(rule_result, db=db, user_id=user_id)

    portions = [resolve_portion(item, user_id=user_id, db=db) for item in parsed.items]
    matches = [_match_for_portion(portion, db) for portion in portions]
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

    if decision.action in {"ask_short_clarification", "ask_detailed_clarification"}:
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

    response_text = _format_saved_response(logged_items, summary, user_id, db)
    inline_keyboard: list[list[dict]] | None = None

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


def _match_for_portion(portion: ResolvedPortion, db: Session) -> NutritionMatch | None:
    if portion.default_kcal is not None:
        return None
    return match_nutrition(portion.item_name, db=db)


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

    lines.extend([
        "",
        "Gesamt:",
        f"{summary.total_kcal:.0f} kcal",
        f"{summary.total_protein:.1f}g Protein",
        f"{summary.total_carbs:.1f}g Carbs",
        f"{summary.total_fat:.1f}g Fett",
        "",
        build_daily_summary(user_id, date.today(), db),
    ])
    return "\n".join(lines)


def _format_amount(item: LoggedItemSummary) -> str:
    if item.grams is not None:
        return f"{item.grams:g}g "
    if item.ml is not None:
        return f"{item.ml:g}ml "
    return ""
