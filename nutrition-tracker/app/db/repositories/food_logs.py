import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import FoodLog, FoodLogItem


class FoodLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        user_id: uuid.UUID,
        raw_text: str | None = None,
        source: str = "text",
        meal_type: str | None = None,
        total_kcal: float | None = None,
        total_protein: float | None = None,
        total_carbs: float | None = None,
        total_fat: float | None = None,
        confidence: float | None = None,
        status: str = "saved",
        logged_at: datetime | None = None,
    ) -> FoodLog:
        log = FoodLog(
            user_id=user_id,
            raw_text=raw_text,
            source=source,
            meal_type=meal_type,
            total_kcal=total_kcal,
            total_protein=total_protein,
            total_carbs=total_carbs,
            total_fat=total_fat,
            confidence=confidence,
            status=status,
            logged_at=logged_at or datetime.now(timezone.utc),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_by_id(self, log_id: uuid.UUID) -> FoodLog | None:
        return self.db.query(FoodLog).filter(FoodLog.id == log_id).first()

    def get_last_for_user(self, user_id: uuid.UUID) -> FoodLog | None:
        return (
            self.db.query(FoodLog)
            .filter(FoodLog.user_id == user_id, FoodLog.status == "saved")
            .order_by(FoodLog.logged_at.desc())
            .first()
        )

    def get_for_user_on_date(self, user_id: uuid.UUID, day: date) -> list[FoodLog]:
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        end = datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=timezone.utc)
        return (
            self.db.query(FoodLog)
            .filter(
                FoodLog.user_id == user_id,
                FoodLog.logged_at >= start,
                FoodLog.logged_at <= end,
                FoodLog.status == "saved",
            )
            .order_by(FoodLog.logged_at.asc())
            .all()
        )

    def soft_delete(self, log: FoodLog) -> FoodLog:
        log.status = "deleted"
        self.db.commit()
        self.db.refresh(log)
        return log

    def update_status(self, log: FoodLog, status: str) -> FoodLog:
        log.status = status
        self.db.commit()
        self.db.refresh(log)
        return log

    def count_today(self) -> int:
        today = datetime.now(timezone.utc).date()
        start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
        return self.db.query(FoodLog).filter(FoodLog.logged_at >= start).count()


class FoodLogItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        food_log_id: uuid.UUID,
        original_name: str | None = None,
        canonical_name: str | None = None,
        quantity: float | None = None,
        unit: str | None = None,
        grams: float | None = None,
        kcal: float | None = None,
        protein: float | None = None,
        carbs: float | None = None,
        fat: float | None = None,
        source: str | None = None,
        source_id: str | None = None,
        confidence: float | None = None,
        was_estimated: bool = False,
    ) -> FoodLogItem:
        item = FoodLogItem(
            food_log_id=food_log_id,
            original_name=original_name,
            canonical_name=canonical_name,
            quantity=quantity,
            unit=unit,
            grams=grams,
            kcal=kcal,
            protein=protein,
            carbs=carbs,
            fat=fat,
            source=source,
            source_id=source_id,
            confidence=confidence,
            was_estimated=was_estimated,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_for_log(self, food_log_id: uuid.UUID) -> list[FoodLogItem]:
        return self.db.query(FoodLogItem).filter(FoodLogItem.food_log_id == food_log_id).all()
