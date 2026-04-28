from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


JsonType = JSON().with_variant(JSONB(), "postgresql")


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(Text)
    first_name: Mapped[Optional[str]] = mapped_column(Text)
    last_name: Mapped[Optional[str]] = mapped_column(Text)
    language_code: Mapped[Optional[str]] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text, default="Europe/Berlin")
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    goals: Mapped[List["UserGoal"]] = relationship(back_populates="user")
    food_logs: Mapped[List["FoodLog"]] = relationship(back_populates="user")
    portion_memory: Mapped[List["UserPortionMemory"]] = relationship(back_populates="user")
    meal_templates: Mapped[List["MealTemplate"]] = relationship(back_populates="user")
    conversation_states: Mapped[List["ConversationState"]] = relationship(back_populates="user")


class UserGoal(Base):
    __tablename__ = "user_goals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    daily_calorie_goal: Mapped[Optional[int]] = mapped_column(Integer)
    daily_protein_goal: Mapped[Optional[float]] = mapped_column(Numeric)
    daily_carbs_goal: Mapped[Optional[float]] = mapped_column(Numeric)
    daily_fat_goal: Mapped[Optional[float]] = mapped_column(Numeric)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    user: Mapped["User"] = relationship(back_populates="goals")


class FoodLog(Base):
    __tablename__ = "food_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[Optional[str]] = mapped_column(String(50))  # text, voice, template, correction
    meal_type: Mapped[Optional[str]] = mapped_column(String(50))
    total_kcal: Mapped[Optional[float]] = mapped_column(Numeric)
    total_protein: Mapped[Optional[float]] = mapped_column(Numeric)
    total_carbs: Mapped[Optional[float]] = mapped_column(Numeric)
    total_fat: Mapped[Optional[float]] = mapped_column(Numeric)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric)
    status: Mapped[Optional[str]] = mapped_column(String(50))  # saved, pending_confirmation, corrected, deleted
    logged_at: Mapped[datetime] = mapped_column(nullable=False, default=_now)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    user: Mapped["User"] = relationship(back_populates="food_logs")
    items: Mapped[List["FoodLogItem"]] = relationship(back_populates="food_log")


class FoodLogItem(Base):
    __tablename__ = "food_log_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    food_log_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("food_logs.id"), nullable=False)
    original_name: Mapped[Optional[str]] = mapped_column(Text)
    canonical_name: Mapped[Optional[str]] = mapped_column(Text)
    quantity: Mapped[Optional[float]] = mapped_column(Numeric)
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    grams: Mapped[Optional[float]] = mapped_column(Numeric)
    kcal: Mapped[Optional[float]] = mapped_column(Numeric)
    protein: Mapped[Optional[float]] = mapped_column(Numeric)
    carbs: Mapped[Optional[float]] = mapped_column(Numeric)
    fat: Mapped[Optional[float]] = mapped_column(Numeric)
    source: Mapped[Optional[str]] = mapped_column(String(100))
    source_id: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric)
    was_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    food_log: Mapped["FoodLog"] = relationship(back_populates="items")


class NutritionItem(Base):
    __tablename__ = "nutrition_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    brand: Mapped[Optional[str]] = mapped_column(Text)
    barcode: Mapped[Optional[str]] = mapped_column(Text, index=True)
    kcal_100g: Mapped[Optional[float]] = mapped_column(Numeric)
    protein_100g: Mapped[Optional[float]] = mapped_column(Numeric)
    carbs_100g: Mapped[Optional[float]] = mapped_column(Numeric)
    fat_100g: Mapped[Optional[float]] = mapped_column(Numeric)
    source: Mapped[Optional[str]] = mapped_column(String(100))
    source_id: Mapped[Optional[str]] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)


class FoodAlias(Base):
    __tablename__ = "food_aliases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    alias: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="de")
    confidence: Mapped[float] = mapped_column(Numeric, default=0.8)
    created_at: Mapped[datetime] = mapped_column(default=_now)


class PortionRule(Base):
    __tablename__ = "portion_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    food_category: Mapped[Optional[str]] = mapped_column(Text)
    food_name: Mapped[Optional[str]] = mapped_column(Text, index=True)
    unit_text: Mapped[str] = mapped_column(Text, nullable=False)
    default_grams: Mapped[Optional[float]] = mapped_column(Numeric)
    min_grams: Mapped[Optional[float]] = mapped_column(Numeric)
    max_grams: Mapped[Optional[float]] = mapped_column(Numeric)
    default_kcal: Mapped[Optional[float]] = mapped_column(Numeric)
    country: Mapped[str] = mapped_column(String(10), default="DE")
    confidence: Mapped[float] = mapped_column(Numeric, default=0.7)
    source: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=_now)


class UserPortionMemory(Base):
    __tablename__ = "user_portion_memory"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    phrase: Mapped[str] = mapped_column(Text, nullable=False)
    food_name: Mapped[Optional[str]] = mapped_column(Text)
    grams: Mapped[Optional[float]] = mapped_column(Numeric)
    ml: Mapped[Optional[float]] = mapped_column(Numeric)
    usage_count: Mapped[int] = mapped_column(Integer, default=1)
    last_used_at: Mapped[Optional[datetime]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=_now)

    user: Mapped["User"] = relationship(back_populates="portion_memory")


class MealTemplate(Base):
    __tablename__ = "meal_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    template_name: Mapped[str] = mapped_column(Text, nullable=False)
    total_kcal: Mapped[Optional[float]] = mapped_column(Numeric)
    total_protein: Mapped[Optional[float]] = mapped_column(Numeric)
    total_carbs: Mapped[Optional[float]] = mapped_column(Numeric)
    total_fat: Mapped[Optional[float]] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    user: Mapped["User"] = relationship(back_populates="meal_templates")
    items: Mapped[List["MealTemplateItem"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
    )


class MealTemplateItem(Base):
    __tablename__ = "meal_template_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    template_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("meal_templates.id"), nullable=False)
    original_name: Mapped[Optional[str]] = mapped_column(Text)
    canonical_name: Mapped[Optional[str]] = mapped_column(Text)
    quantity: Mapped[Optional[float]] = mapped_column(Numeric)
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    grams: Mapped[Optional[float]] = mapped_column(Numeric)
    kcal: Mapped[Optional[float]] = mapped_column(Numeric)
    protein: Mapped[Optional[float]] = mapped_column(Numeric)
    carbs: Mapped[Optional[float]] = mapped_column(Numeric)
    fat: Mapped[Optional[float]] = mapped_column(Numeric)
    source: Mapped[Optional[str]] = mapped_column(String(100))
    source_id: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric)
    was_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    template: Mapped["MealTemplate"] = relationship(back_populates="items")


class ConversationState(Base):
    __tablename__ = "conversation_states"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    state_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JsonType, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    user: Mapped["User"] = relationship(back_populates="conversation_states")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    event_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    payload: Mapped[Optional[dict]] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(default=_now)


class ApiRequestLog(Base):
    __tablename__ = "api_request_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    service: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False, default="GET")
    status_code: Mapped[Optional[int]] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(Numeric)
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=_now)
