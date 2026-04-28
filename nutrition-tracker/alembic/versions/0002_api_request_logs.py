"""add api_request_logs table

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_request_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("service", sa.String(50), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("method", sa.String(10), nullable=False, server_default="GET"),
        sa.Column("status_code", sa.Integer()),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("duration_ms", sa.Numeric()),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_api_request_logs_service", "api_request_logs", ["service"])
    op.create_index("ix_api_request_logs_created_at", "api_request_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("api_request_logs")
