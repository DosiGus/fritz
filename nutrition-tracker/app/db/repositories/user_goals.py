import uuid

from sqlalchemy.orm import Session

from app.db.models import UserGoal


class UserGoalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active_for_user(self, user_id: uuid.UUID) -> UserGoal | None:
        return (
            self.db.query(UserGoal)
            .filter(UserGoal.user_id == user_id, UserGoal.active == True)  # noqa: E712
            .order_by(UserGoal.created_at.desc())
            .first()
        )

    def create(
        self,
        user_id: uuid.UUID,
        daily_calorie_goal: int | None = None,
        daily_protein_goal: float | None = None,
        daily_carbs_goal: float | None = None,
        daily_fat_goal: float | None = None,
    ) -> UserGoal:
        # Deactivate existing goals first
        self.db.query(UserGoal).filter(UserGoal.user_id == user_id).update({"active": False})

        goal = UserGoal(
            user_id=user_id,
            daily_calorie_goal=daily_calorie_goal,
            daily_protein_goal=daily_protein_goal,
            daily_carbs_goal=daily_carbs_goal,
            daily_fat_goal=daily_fat_goal,
            active=True,
        )
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        return goal
