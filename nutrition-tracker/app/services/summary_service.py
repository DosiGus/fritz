from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.db.repositories.food_logs import FoodLogRepository
from app.db.repositories.user_goals import UserGoalRepository


def build_daily_summary(
    user_id: uuid.UUID,
    day: date,
    db: Session,
    tz_name: str | None = None,
) -> str:
    log_repo = FoodLogRepository(db)
    logs = log_repo.get_for_user_on_date(user_id, day, tz_name=tz_name)

    if not logs:
        return "Heute noch nichts geloggt."

    total_kcal = sum(float(l.total_kcal or 0) for l in logs)
    total_protein = sum(float(l.total_protein or 0) for l in logs)
    total_carbs = sum(float(l.total_carbs or 0) for l in logs)
    total_fat = sum(float(l.total_fat or 0) for l in logs)

    goal_repo = UserGoalRepository(db)
    goal = goal_repo.get_active_for_user(user_id)

    lines = [f"Heute — {day.strftime('%d.%m.%Y')}", ""]
    lines.append(f"Kalorien: {total_kcal:.0f} kcal" + (f" / {goal.daily_calorie_goal}" if goal and goal.daily_calorie_goal else ""))
    lines.append(f"Protein:  {total_protein:.1f}g" + (f" / {float(goal.daily_protein_goal):.0f}g" if goal and goal.daily_protein_goal else ""))
    lines.append(f"Carbs:    {total_carbs:.1f}g")
    lines.append(f"Fett:     {total_fat:.1f}g")
    return "\n".join(lines)
