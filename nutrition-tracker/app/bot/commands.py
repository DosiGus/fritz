import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.db.repositories.conversation_states import ConversationStateRepository
from app.db.repositories.food_logs import FoodLogRepository
from app.db.repositories.meal_templates import MealTemplateRepository
from app.db.repositories.user_goals import UserGoalRepository
from app.db.repositories.users import UserRepository
from app.db.session import SessionLocal
from app.services.audit_service import AuditService
from app.services.edit_log_service import start_edit_last
from app.utils.time import user_today

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    with SessionLocal() as db:
        repo = UserRepository(db)
        _, created = repo.get_or_create(
            telegram_user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code,
        )

    name = user.first_name or "dort"
    greeting = "Willkommen" if created else "Willkommen zurück"
    text = (
        f"{greeting}, {name}! 👋\n\n"
        "Ich bin Fritz, dein Ernährungs-Tracker.\n\n"
        "Schreib mir einfach, was du gegessen hast – zum Beispiel:\n"
        "  250g Skyr, 1 Banane und 30g Whey\n\n"
        "Oder sende mir eine Sprachnachricht.\n\n"
        "/help für alle Befehle."
    )
    await update.message.reply_text(text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🍽 *Fritz Nutrition Tracker*\n\n"
        "Schreib mir was du gegessen hast und ich berechne Kalorien & Makros.\n\n"
        "*Befehle:*\n"
        "/today – heutiger Überblick\n"
        "/goal – Tagesziele setzen\n"
        "/delete\\_last – letzten Eintrag löschen\n"
        "/edit\\_last – letzten Eintrag bearbeiten\n"
        "/favorites – Standardmahlzeiten\n"
        "/cancel – aktuelle Aktion abbrechen\n\n"
        "*Beispiele:*\n"
        "  250g Skyr\n"
        "  2 Eier und eine Scheibe Brot\n"
        "  ein Teller Pasta\n"
        "  500ml Milch"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    with SessionLocal() as db:
        user_repo = UserRepository(db)
        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await update.message.reply_text("Starte zuerst mit /start.")
            return

        log_repo = FoodLogRepository(db)
        today = user_today(db_user.timezone)
        logs = log_repo.get_for_user_on_date(db_user.id, today, tz_name=db_user.timezone)

        if not logs:
            await update.message.reply_text("Heute noch nichts geloggt. Schreib mir was du gegessen hast!")
            return

        total_kcal = sum(float(l.total_kcal or 0) for l in logs)
        total_protein = sum(float(l.total_protein or 0) for l in logs)
        total_carbs = sum(float(l.total_carbs or 0) for l in logs)
        total_fat = sum(float(l.total_fat or 0) for l in logs)

        goal_repo = UserGoalRepository(db)
        goal = goal_repo.get_active_for_user(db_user.id)

        lines = [f"📊 *Heute, {today.strftime('%d.%m.%Y')}*\n"]
        lines.append(f"Kalorien: {total_kcal:.0f} kcal")
        if goal and goal.daily_calorie_goal:
            lines[-1] += f" / {goal.daily_calorie_goal} kcal"
        lines.append(f"Protein: {total_protein:.1f}g")
        if goal and goal.daily_protein_goal:
            lines[-1] += f" / {float(goal.daily_protein_goal):.0f}g"
        lines.append(f"Carbs: {total_carbs:.1f}g")
        lines.append(f"Fett: {total_fat:.1f}g")
        lines.append(f"\n{len(logs)} Mahlzeit(en) geloggt.")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        await update.message.reply_text(
            "Setze dein Kalorienziel:\n/goal 2400\n\nOder mit Protein:\n/goal 2400 180"
        )
        return

    user = update.effective_user
    try:
        kcal = int(args[0])
        protein = float(args[1]) if len(args) > 1 else None
    except ValueError:
        await update.message.reply_text("Ungültige Eingabe. Beispiel: /goal 2400 180")
        return

    with SessionLocal() as db:
        user_repo = UserRepository(db)
        db_user = user_repo.get_or_create(telegram_user_id=user.id)[0]

        goal_repo = UserGoalRepository(db)
        goal_repo.create(user_id=db_user.id, daily_calorie_goal=kcal, daily_protein_goal=protein)

    msg = f"✅ Ziel gesetzt: {kcal} kcal/Tag"
    if protein:
        msg += f", {protein:.0f}g Protein"
    await update.message.reply_text(msg)


async def cmd_delete_last(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    with SessionLocal() as db:
        user_repo = UserRepository(db)
        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await update.message.reply_text("Starte zuerst mit /start.")
            return

        log_repo = FoodLogRepository(db)
        last_log = log_repo.get_last_for_user(db_user.id)
        if not last_log:
            await update.message.reply_text("Kein Eintrag zum Löschen gefunden.")
            return

        log_repo.soft_delete(last_log)
        AuditService(db).log(
            event_type="food_log_deleted",
            user_id=db_user.id,
            payload={"food_log_id": str(last_log.id), "source": "delete_last"},
        )
        kcal = float(last_log.total_kcal or 0)

    await update.message.reply_text(f"🗑 Letzter Eintrag gelöscht ({kcal:.0f} kcal).")


async def cmd_edit_last(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    with SessionLocal() as db:
        user_repo = UserRepository(db)
        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await update.message.reply_text("Starte zuerst mit /start.")
            return
        response = start_edit_last(db_user.id, db)

    await update.message.reply_text(response.text)


async def cmd_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    with SessionLocal() as db:
        user_repo = UserRepository(db)
        db_user = user_repo.get_by_telegram_id(user.id)
        if not db_user:
            await update.message.reply_text("Starte zuerst mit /start.")
            return

        template_repo = MealTemplateRepository(db)
        templates = template_repo.get_for_user(db_user.id)

    if not templates:
        await update.message.reply_text(
            "Du hast noch keine Standardmahlzeiten gespeichert.\n"
            "Tippe einfach deine Mahlzeit und ich frage ob ich sie speichern soll."
        )
        return

    from app.bot.keyboards import favorites_keyboard
    kb = favorites_keyboard([{"name": t.template_name, "id": str(t.id)} for t in templates])
    await update.message.reply_text("⭐ Deine Standardmahlzeiten:", reply_markup=kb)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    with SessionLocal() as db:
        user_repo = UserRepository(db)
        db_user = user_repo.get_by_telegram_id(user.id)
        if db_user:
            state_repo = ConversationStateRepository(db)
            state = state_repo.get_active_for_user(db_user.id)
            state_repo.delete_for_user(db_user.id)
            AuditService(db).log(
                event_type="conversation_cancelled",
                user_id=db_user.id,
                payload={"state_type": state.state_type if state else None},
            )

    await update.message.reply_text("❌ Abgebrochen.")
