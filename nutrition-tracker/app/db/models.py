import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    language_code: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text, default="Europe/Berlin")
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    goals: Mapped[list["UserGoal"]] = relationship(back_populates="user")
    food_logs: Mapped[list["FoodLog"]] = relationship(back_populates="user")
    portion_memory: Mapped[list["UserPortionMemory"]] = relationship(back_populates="user")
    meal_templates: Mapped[list["MealTemplate"]] = relationship(back_populates="user")
    conversation_states: Mapped[list["ConversationState"]] = relationship(back_populates="user")


class UserGoal(Base):
    __tablename__ = "user_goals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    daily_calorie_goal: Mapped[int | None] = mapped_column(Integer)
    daily_protein_goal: Mapped[float | None] = mapped_column(Numeric)
    daily_carbs_goal: Mapped[float | None] = mapped_column(Numeric)
    daily_fat_goal: Mapped[float | None] = mapped_column(Numeric)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    user: Mapped["User"] = relationship(back_populates="goals")


class FoodLog(Base):
    __tablename__ = "food_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(50))  # text, voice, template, correction
    meal_type: Mapped[str | None] = mapped_column(String(50))
    total_kcal: Mapped[float | None] = mapped_column(Numeric)
    total_protein: Mapped[float | None] = mapped_column(Numeric)
    total_carbs: Mapped[float | None] = mapped_column(Numeric)
    total_fat: Mapped[float | None] = mapped_column(Numeric)
    confidence: Mapped[float | None] = mapped_column(Numeric)
    status: Mapped[str | None] = mapped_column(String(50))  # saved, pending_confirmation, corrected, deleted
    logged_at: Mapped[datetime] = mapped_column(nullable=False, default=_now)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    user: Mapped["User"] = relationship(back_populates="food_logs")
    items: Mapped[list["FoodLogItem"]] = relationship(back_populates="food_log")


class FoodLogItem(Base):
    __tablename__ = "food_log_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    food_log_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("food_logs.id"), nullable=False)
    original_name: Mapped[str | None] = mapped_column(Text)
    canonical_name: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[float | None] = mapped_column(Numeric)
    unit: Mapped[str | None] = mapped_column(String(50))
    grams: Mapped[float | None] = mapped_column(Numeric)
    kcal: Mapped[float | None] = mapped_column(Numeric)
    protein: Mapped[float | None] = mapped_column(Numeric)
    carbs: Mapped[float | None] = mapped_column(Numeric)
    fat: Mapped[float | None] = mapped_column(Numeric)
    source: Mapped[str | None] = mapped_column(String(100))
    source_id: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Numeric)
    was_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    food_log: Mapped["FoodLog"] = relationship(back_populates="items")


class NutritionItem(Base):
    __tablename__ = "nutrition_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    brand: Mapped[str | None] = mapped_column(Text)
    barcode: Mapped[str | None] = mapped_column(Text, index=True)
    kcal_100g: Mapped[float | None] = mapped_column(Numeric)
    protein_100g: Mapped[float | None] = mapped_column(Numeric)
    carbs_100g: Mapped[float | None] = mapped_column(Numeric)
    fat_100g: Mapped[float | None] = mapped_column(Numeric)
    source: Mapped[str | None] = mapped_column(String(100))
    source_id: Mapped[str | None] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)


class FoodAlias(Base):
    __tablename__ = "food_aliases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    alias: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="de")
    confidence: Mapped[float] = mapped_column(Numeric, default=0.8)
    created_at: Mapped[datetime] = mapped_column(default=_now)


class PortionRule(Base):
    __tablename__ = "portion_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    food_category: Mapped[str | None] = mapped_column(Text)
    food_name: Mapped[str | None] = mapped_column(Text, index=True)
    unit_text: Mapped[str] = mapped_column(Text, nullable=False)
    default_grams: Mapped[float | None] = mapped_column(Numeric)
    min_grams: Mapped[float | None] = mapped_column(Numeric)
    max_grams: Mapped[float | None] = mapped_column(Numeric)
    default_kcal: Mapped[float | None] = mapped_column(Numeric)
    country: Mapped[str] = mapped_column(String(10), default="DE")
    confidence: Mapped[float] = mapped_column(Numeric, default=0.7)
    source: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=_now)


class UserPortionMemory(Base):
    __tablename__ = "user_portion_memory"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    phrase: Mapped[str] = mapped_column(Text, nullable=False)
    food_name: Mapped[str | None] = mapped_column(Text)
    grams: Mapped[float | None] = mapped_column(Numeric)
    ml: Mapped[float | None] = mapped_column(Numeric)
    usage_count: Mapped[int] = mapped_column(Integer, default=1)
    last_used_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=_now)

    user: Mapped["User"] = relationship(back_populates="portion_memory")


class MealTemplate(Base):
    __tablename__ = "meal_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    template_name: Mapped[str] = mapped_column(Text, nullable=False)
    total_kcal: Mapped[float | None] = mapped_column(Numeric)
    total_protein: Mapped[float | None] = mapped_column(Numeric)
    total_carbs: Mapped[float | None] = mapped_column(Numeric)
    total_fat: Mapped[float | None] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    user: Mapped["User"] = relationship(back_populates="meal_templates")


class ConversationState(Base):
    __tablename__ = "conversation_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    state_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    user: Mapped["User"] = relationship(back_populates="conversation_states")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(default=_now)
