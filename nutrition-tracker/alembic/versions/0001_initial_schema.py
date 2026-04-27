"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("username", sa.Text()),
        sa.Column("first_name", sa.Text()),
        sa.Column("last_name", sa.Text()),
        sa.Column("language_code", sa.Text()),
        sa.Column("timezone", sa.Text(), nullable=False, server_default="Europe/Berlin"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "user_goals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("daily_calorie_goal", sa.Integer()),
        sa.Column("daily_protein_goal", sa.Numeric()),
        sa.Column("daily_carbs_goal", sa.Numeric()),
        sa.Column("daily_fat_goal", sa.Numeric()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "food_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("raw_text", sa.Text()),
        sa.Column("source", sa.String(50)),
        sa.Column("meal_type", sa.String(50)),
        sa.Column("total_kcal", sa.Numeric()),
        sa.Column("total_protein", sa.Numeric()),
        sa.Column("total_carbs", sa.Numeric()),
        sa.Column("total_fat", sa.Numeric()),
        sa.Column("confidence", sa.Numeric()),
        sa.Column("status", sa.String(50)),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_food_logs_user_id_logged_at", "food_logs", ["user_id", "logged_at"])

    op.create_table(
        "food_log_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("food_log_id", UUID(as_uuid=True), sa.ForeignKey("food_logs.id"), nullable=False),
        sa.Column("original_name", sa.Text()),
        sa.Column("canonical_name", sa.Text()),
        sa.Column("quantity", sa.Numeric()),
        sa.Column("unit", sa.String(50)),
        sa.Column("grams", sa.Numeric()),
        sa.Column("kcal", sa.Numeric()),
        sa.Column("protein", sa.Numeric()),
        sa.Column("carbs", sa.Numeric()),
        sa.Column("fat", sa.Numeric()),
        sa.Column("source", sa.String(100)),
        sa.Column("source_id", sa.Text()),
        sa.Column("confidence", sa.Numeric()),
        sa.Column("was_estimated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "nutrition_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("brand", sa.Text()),
        sa.Column("barcode", sa.Text()),
        sa.Column("kcal_100g", sa.Numeric()),
        sa.Column("protein_100g", sa.Numeric()),
        sa.Column("carbs_100g", sa.Numeric()),
        sa.Column("fat_100g", sa.Numeric()),
        sa.Column("source", sa.String(100)),
        sa.Column("source_id", sa.Text()),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_nutrition_items_canonical_name", "nutrition_items", ["canonical_name"])
    op.create_index("ix_nutrition_items_barcode", "nutrition_items", ["barcode"])

    op.create_table(
        "food_aliases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default="de"),
        sa.Column("confidence", sa.Numeric(), nullable=False, server_default="0.8"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_food_aliases_alias", "food_aliases", ["alias"])

    op.create_table(
        "portion_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("food_category", sa.Text()),
        sa.Column("food_name", sa.Text()),
        sa.Column("unit_text", sa.Text(), nullable=False),
        sa.Column("default_grams", sa.Numeric()),
        sa.Column("min_grams", sa.Numeric()),
        sa.Column("max_grams", sa.Numeric()),
        sa.Column("default_kcal", sa.Numeric()),
        sa.Column("country", sa.String(10), nullable=False, server_default="DE"),
        sa.Column("confidence", sa.Numeric(), nullable=False, server_default="0.7"),
        sa.Column("source", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_portion_rules_food_name", "portion_rules", ["food_name"])

    op.create_table(
        "user_portion_memory",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("phrase", sa.Text(), nullable=False),
        sa.Column("food_name", sa.Text()),
        sa.Column("grams", sa.Numeric()),
        sa.Column("ml", sa.Numeric()),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_portion_memory_user_phrase", "user_portion_memory", ["user_id", "phrase"])

    op.create_table(
        "meal_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("template_name", sa.Text(), nullable=False),
        sa.Column("total_kcal", sa.Numeric()),
        sa.Column("total_protein", sa.Numeric()),
        sa.Column("total_carbs", sa.Numeric()),
        sa.Column("total_fat", sa.Numeric()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "conversation_states",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("state_type", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversation_states_user_id", "conversation_states", ["user_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True)),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("conversation_states")
    op.drop_table("meal_templates")
    op.drop_table("user_portion_memory")
    op.drop_table("portion_rules")
    op.drop_table("food_aliases")
    op.drop_table("nutrition_items")
    op.drop_table("food_log_items")
    op.drop_table("food_logs")
    op.drop_table("user_goals")
    op.drop_table("users")
