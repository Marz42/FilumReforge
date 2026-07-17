"""Add durable blocked diagnostics for template review safety.

Revision ID: 20260717_02
Revises: 20260717_01
Create Date: 2026-07-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260717_02"
down_revision = "20260717_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column(
    "tasks",
    sa.Column("blocked_reason", sa.String(length=64), nullable=True),
  )


def downgrade() -> None:
  op.drop_column("tasks", "blocked_reason")
