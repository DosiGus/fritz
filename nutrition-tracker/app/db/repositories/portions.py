import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import PortionRule, UserPortionMemory


class PortionRuleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_food_and_unit(self, food_name: str, unit_text: str) -> PortionRule | None:
        return (
            self.db.query(PortionRule)
            .filter(
                PortionRule.food_name.ilike(food_name),
                PortionRule.unit_text.ilike(unit_text),
            )
            .first()
        )

    def get_by_food_name(self, food_name: str) -> list[PortionRule]:
        return (
            self.db.query(PortionRule)
            .filter(PortionRule.food_name.ilike(food_name))
            .all()
        )

    def create(
        self,
        unit_text: str,
        food_name: str | None = None,
        food_category: str | None = None,
        default_grams: float | None = None,
        min_grams: float | None = None,
        max_grams: float | None = None,
        default_kcal: float | None = None,
        country: str = "DE",
        confidence: float = 0.7,
        source: str | None = None,
    ) -> PortionRule:
        rule = PortionRule(
            unit_text=unit_text,
            food_name=food_name,
            food_category=food_category,
            default_grams=default_grams,
            min_grams=min_grams,
            max_grams=max_grams,
            default_kcal=default_kcal,
            country=country,
            confidence=confidence,
            source=source,
        )
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def list_all(self) -> list[PortionRule]:
        return self.db.query(PortionRule).all()


class UserPortionMemoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_phrase(self, user_id: uuid.UUID, phrase: str) -> UserPortionMemory | None:
        return (
            self.db.query(UserPortionMemory)
            .filter(UserPortionMemory.user_id == user_id, UserPortionMemory.phrase.ilike(phrase))
            .first()
        )

    def create(
        self,
        user_id: uuid.UUID,
        phrase: str,
        food_name: str | None = None,
        grams: float | None = None,
        ml: float | None = None,
    ) -> UserPortionMemory:
        mem = UserPortionMemory(
            user_id=user_id,
            phrase=phrase,
            food_name=food_name,
            grams=grams,
            ml=ml,
            last_used_at=datetime.now(timezone.utc),
        )
        self.db.add(mem)
        self.db.commit()
        self.db.refresh(mem)
        return mem

    def increment_usage(self, memory: UserPortionMemory) -> UserPortionMemory:
        memory.usage_count += 1
        memory.last_used_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def get_for_user(self, user_id: uuid.UUID) -> list[UserPortionMemory]:
        return (
            self.db.query(UserPortionMemory)
            .filter(UserPortionMemory.user_id == user_id)
            .order_by(UserPortionMemory.usage_count.desc())
            .all()
        )
