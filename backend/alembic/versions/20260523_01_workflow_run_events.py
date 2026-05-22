"""workflow run event log (W8)

Revision ID: 20260523_01
Revises: 20260522_01
Create Date: 2026-05-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260523_01"
down_revision = "20260522_01"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
  op.create_table(
    "workflow_run_events",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("instance_id", sa.Uuid(), nullable=False),
    sa.Column("event_type", sa.String(length=64), nullable=False),
    sa.Column("actor_user_id", sa.Uuid(), nullable=True),
    sa.Column("payload", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column(
      "created_at",
      sa.DateTime(timezone=True),
      nullable=False,
      server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.ForeignKeyConstraint(
      ["instance_id"],
      ["workflow_graph_instances.id"],
      name="fk_wf_run_events_instance",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["actor_user_id"],
      ["users.id"],
      name="fk_wf_run_events_actor",
      ondelete="SET NULL",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_wf_run_events"),
  )
  op.create_index(
    "idx_wf_run_events_instance_created",
    "workflow_run_events",
    ["instance_id", "created_at"],
  )
  op.create_index(
    "idx_wf_run_events_instance_type",
    "workflow_run_events",
    ["instance_id", "event_type"],
  )


def downgrade() -> None:
  op.drop_index("idx_wf_run_events_instance_type", table_name="workflow_run_events")
  op.drop_index("idx_wf_run_events_instance_created", table_name="workflow_run_events")
  op.drop_table("workflow_run_events")
