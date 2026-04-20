"""task center memo support

Revision ID: 20260420_02
Revises: 20260420_01
Create Date: 2026-04-20 14:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260420_02"
down_revision = "20260420_01"
branch_labels = None
depends_on = None


def _created_at_column() -> sa.Column:
  return sa.Column(
    "created_at",
    sa.DateTime(timezone=True),
    nullable=False,
    server_default=sa.text("CURRENT_TIMESTAMP"),
  )


def _updated_at_column() -> sa.Column:
  return sa.Column(
    "updated_at",
    sa.DateTime(timezone=True),
    nullable=False,
    server_default=sa.text("CURRENT_TIMESTAMP"),
  )


def upgrade() -> None:
  op.create_table(
    "task_memos",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("owner_user_id", sa.Uuid(), nullable=False),
    sa.Column("related_task_id", sa.Uuid(), nullable=True),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    _created_at_column(),
    _updated_at_column(),
    sa.CheckConstraint("length(trim(content)) > 0", name="task_memos_non_empty_content"),
    sa.ForeignKeyConstraint(
      ["owner_user_id"],
      ["users.id"],
      name="fk_task_memos_owner",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["related_task_id"],
      ["tasks.id"],
      name="fk_task_memos_related_task",
      ondelete="SET NULL",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_task_memos"),
  )
  op.create_index(
    "idx_task_memos_owner_pinned_updated",
    "task_memos",
    ["owner_user_id", "is_pinned", "updated_at"],
    unique=False,
  )
  op.create_index(
    "idx_task_memos_related_task",
    "task_memos",
    ["related_task_id"],
    unique=False,
  )


def downgrade() -> None:
  op.drop_index("idx_task_memos_related_task", table_name="task_memos")
  op.drop_index("idx_task_memos_owner_pinned_updated", table_name="task_memos")
  op.drop_table("task_memos")
