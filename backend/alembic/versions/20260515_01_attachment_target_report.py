"""expand attachment_target_type for report attachments

Revision ID: 20260515_01
Revises: 20260429_04
Create Date: 2026-05-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260515_01"
down_revision = "20260429_04"
branch_labels = None
depends_on = None

_VALUES = (
  "task_comment",
  "task",
  "profile",
  "document",
  "notification_message",
  "report",
)


def upgrade() -> None:
  new_enum = sa.Enum(*_VALUES, name="attachment_target_type", native_enum=False)
  old_enum = sa.Enum(
    "task_comment",
    "task",
    "profile",
    "document",
    "notification_message",
    name="attachment_target_type",
    native_enum=False,
  )
  with op.batch_alter_table("attachment_links") as batch:
    batch.alter_column(
      "target_type",
      existing_type=old_enum,
      type_=new_enum,
      existing_nullable=False,
    )


def downgrade() -> None:
  op.execute(sa.text("DELETE FROM attachment_links WHERE target_type = 'report'"))
  narrowed = sa.Enum(
    "task_comment",
    "task",
    "profile",
    "document",
    "notification_message",
    name="attachment_target_type",
    native_enum=False,
  )
  wide = sa.Enum(*_VALUES, name="attachment_target_type", native_enum=False)
  with op.batch_alter_table("attachment_links") as batch:
    batch.alter_column(
      "target_type",
      existing_type=wide,
      type_=narrowed,
      existing_nullable=False,
    )
