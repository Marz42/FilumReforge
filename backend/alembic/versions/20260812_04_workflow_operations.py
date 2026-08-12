"""Iteration 5-D expand: workflow operations audit and trace identifiers.

Revision ID: 20260812_04
Revises: 20260812_03
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260812_04"
down_revision = "20260812_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
  dialect = op.get_bind().dialect.name
  # Migration tests build the legacy tables from current metadata and then stamp
  # the pre-projection revision. Treat an already expanded table as satisfied;
  # real 20260812_03 databases do not have this column.
  try:
    existing_outbox_columns = {
      item["name"] for item in sa.inspect(op.get_bind()).get_columns("workflow_outbox_events")
    }
  except sa.exc.NoInspectionAvailable:
    existing_outbox_columns = set()
  if "manual_replay_count" in existing_outbox_columns:
    return

  op.add_column(
    "workflow_outbox_events",
    sa.Column("manual_replay_count", sa.Integer(), nullable=False, server_default="0"),
  )
  op.add_column(
    "workflow_outbox_events",
    sa.Column("last_replayed_at", sa.DateTime(timezone=True), nullable=True),
  )
  op.add_column(
    "workflow_outbox_events",
    sa.Column("last_replayed_by_user_id", sa.Uuid(), nullable=True),
  )
  op.add_column(
    "workflow_outbox_events",
    sa.Column("last_replay_reason", sa.Text(), nullable=True),
  )
  if dialect != "sqlite":
    op.create_foreign_key(
      "fk_wf_outbox_events_replayer",
      "workflow_outbox_events",
      "users",
      ["last_replayed_by_user_id"],
      ["id"],
      ondelete="SET NULL",
    )

  op.add_column(
    "workflow_operational_incidents",
    sa.Column("resolved_by_user_id", sa.Uuid(), nullable=True),
  )
  op.add_column(
    "workflow_operational_incidents",
    sa.Column("resolution_note", sa.Text(), nullable=True),
  )
  if dialect != "sqlite":
    op.create_foreign_key(
      "fk_wf_operational_incidents_resolver",
      "workflow_operational_incidents",
      "users",
      ["resolved_by_user_id"],
      ["id"],
      ondelete="SET NULL",
    )

  op.add_column("workflow_run_events", sa.Column("request_id", sa.String(length=64), nullable=True))
  op.add_column("workflow_run_events", sa.Column("node_instance_id", sa.Uuid(), nullable=True))
  op.add_column("workflow_run_events", sa.Column("task_id", sa.Uuid(), nullable=True))
  if dialect != "sqlite":
    op.create_foreign_key(
      "fk_wf_run_events_node",
      "workflow_run_events",
      "workflow_node_instances",
      ["node_instance_id"],
      ["id"],
      ondelete="SET NULL",
    )
  op.create_index("idx_wf_run_events_request", "workflow_run_events", ["request_id", "occurred_at"])
  op.create_index("idx_wf_run_events_node", "workflow_run_events", ["node_instance_id", "occurred_at"])
  op.create_index("idx_wf_run_events_task", "workflow_run_events", ["task_id", "occurred_at"])


def downgrade() -> None:
  op.drop_index("idx_wf_run_events_task", table_name="workflow_run_events")
  op.drop_index("idx_wf_run_events_node", table_name="workflow_run_events")
  op.drop_index("idx_wf_run_events_request", table_name="workflow_run_events")
  if op.get_bind().dialect.name == "sqlite":
    with op.batch_alter_table("workflow_run_events", recreate="always") as batch_op:
      batch_op.drop_column("task_id")
      batch_op.drop_column("node_instance_id")
      batch_op.drop_column("request_id")
    with op.batch_alter_table("workflow_operational_incidents", recreate="always") as batch_op:
      batch_op.drop_column("resolution_note")
      batch_op.drop_column("resolved_by_user_id")
    with op.batch_alter_table("workflow_outbox_events", recreate="always") as batch_op:
      batch_op.drop_column("last_replay_reason")
      batch_op.drop_column("last_replayed_by_user_id")
      batch_op.drop_column("last_replayed_at")
      batch_op.drop_column("manual_replay_count")
    return

  if op.get_bind().dialect.name != "sqlite":
    op.drop_constraint("fk_wf_run_events_node", "workflow_run_events", type_="foreignkey")
  op.drop_column("workflow_run_events", "task_id")
  op.drop_column("workflow_run_events", "node_instance_id")
  op.drop_column("workflow_run_events", "request_id")

  if op.get_bind().dialect.name != "sqlite":
    op.drop_constraint(
      "fk_wf_operational_incidents_resolver",
      "workflow_operational_incidents",
      type_="foreignkey",
    )
  op.drop_column("workflow_operational_incidents", "resolution_note")
  op.drop_column("workflow_operational_incidents", "resolved_by_user_id")

  if op.get_bind().dialect.name != "sqlite":
    op.drop_constraint(
      "fk_wf_outbox_events_replayer",
      "workflow_outbox_events",
      type_="foreignkey",
    )
  op.drop_column("workflow_outbox_events", "last_replay_reason")
  op.drop_column("workflow_outbox_events", "last_replayed_by_user_id")
  op.drop_column("workflow_outbox_events", "last_replayed_at")
  op.drop_column("workflow_outbox_events", "manual_replay_count")
