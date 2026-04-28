"""meal template items

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meal_template_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", UUID(as_uuid=True), sa.ForeignKey("meal_templates.id"), nullable=False),
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
    op.create_index("ix_meal_template_items_template_id", "meal_template_items", ["template_id"])


def downgrade() -> None:
    op.drop_index("ix_meal_template_items_template_id", table_name="meal_template_items")
    op.drop_table("meal_template_items")
