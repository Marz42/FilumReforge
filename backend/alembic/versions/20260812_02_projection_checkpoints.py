"""Iteration 5-B expand: independent projection stream checkpoints.

Revision ID: 20260812_02
Revises: 20260812_01
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260812_02"
down_revision = "20260812_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
    "projection_checkpoints",
    sa.Column("projection_name", sa.String(length=64), nullable=False),
    sa.Column("stream_name", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="idle"),
    sa.Column("cursor_occurred_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("cursor_source_id", sa.Uuid(), nullable=True),
    sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_error", sa.Text(), nullable=True),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint(
      "status in ('idle', 'running', 'failed')",
      name="projection_checkpoints_status_chk",
    ),
    sa.CheckConstraint(
      "(cursor_occurred_at IS NULL AND cursor_source_id IS NULL) "
      "OR (cursor_occurred_at IS NOT NULL AND cursor_source_id IS NOT NULL)",
      name="projection_checkpoints_cursor_pair_chk",
    ),
    sa.CheckConstraint(
      "processed_count >= 0 AND attempt_count >= 0",
      name="projection_checkpoints_counts_chk",
    ),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint(
      "projection_name",
      "stream_name",
      name="uq_projection_checkpoints_projection_stream",
    ),
  )
  op.create_index(
    "idx_projection_checkpoints_status",
    "projection_checkpoints",
    ["status", "updated_at"],
  )


def downgrade() -> None:
  op.drop_index("idx_projection_checkpoints_status", table_name="projection_checkpoints")
  op.drop_table("projection_checkpoints")
