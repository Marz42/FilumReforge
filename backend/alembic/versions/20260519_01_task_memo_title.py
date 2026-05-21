"""add optional title to task_memos

Revision ID: 20260519_01
Revises: 20260515_01
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260519_01"
down_revision = "20260515_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("task_memos", sa.Column("title", sa.String(length=200), nullable=True))


def downgrade() -> None:
  op.drop_column("task_memos", "title")
