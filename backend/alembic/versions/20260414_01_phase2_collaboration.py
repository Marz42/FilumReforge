"""phase2 collaboration schema

Revision ID: 20260414_01
Revises: 20260413_01
Create Date: 2026-04-14 02:55:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260414_01"
down_revision = "20260413_01"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


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
  task_status = sa.Enum("todo", "doing", "review", "done", name="task_status", native_enum=False)
  task_action_type = sa.Enum(
    "created",
    "assigned",
    "status_changed",
    "commented",
    "attachment_added",
    "due_date_changed",
    "closed",
    name="task_action_type",
    native_enum=False,
  )
  comment_format = sa.Enum(
    "plain_text",
    "markdown",
    name="comment_format",
    native_enum=False,
  )

  op.create_table(
    "task_logs",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("task_id", sa.Uuid(), nullable=False),
    sa.Column("operator_id", sa.Uuid(), nullable=False),
    sa.Column("action_type", task_action_type, nullable=False),
    sa.Column("from_status", task_status, nullable=True),
    sa.Column("to_status", task_status, nullable=True),
    sa.Column("detail", _json_type(), nullable=False),
    _created_at_column(),
    sa.ForeignKeyConstraint(["operator_id"], ["users.id"], name="fk_task_logs_operator_id_users"),
    sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name="fk_task_logs_task_id_tasks", ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name="pk_task_logs"),
  )
  op.create_index("idx_task_logs_task_id_created_at", "task_logs", ["task_id", "created_at"], unique=False)
  op.create_index("idx_task_logs_operator_id", "task_logs", ["operator_id"], unique=False)

  op.create_table(
    "task_comments",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("task_id", sa.Uuid(), nullable=False),
    sa.Column("user_id", sa.Uuid(), nullable=False),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("content_format", comment_format, nullable=False, server_default=sa.text("'markdown'")),
    sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    _created_at_column(),
    _updated_at_column(),
    sa.CheckConstraint("length(trim(content)) > 0", name="task_comments_non_empty_content"),
    sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name="fk_task_comments_task_id_tasks", ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_task_comments_user_id_users"),
    sa.PrimaryKeyConstraint("id", name="pk_task_comments"),
  )
  op.create_index(
    "idx_task_comments_task_id_created_at",
    "task_comments",
    ["task_id", "created_at"],
    unique=False,
  )
  op.create_index("idx_task_comments_user_id", "task_comments", ["user_id"], unique=False)


def downgrade() -> None:
  op.drop_index("idx_task_comments_user_id", table_name="task_comments")
  op.drop_index("idx_task_comments_task_id_created_at", table_name="task_comments")
  op.drop_table("task_comments")

  op.drop_index("idx_task_logs_operator_id", table_name="task_logs")
  op.drop_index("idx_task_logs_task_id_created_at", table_name="task_logs")
  op.drop_table("task_logs")
