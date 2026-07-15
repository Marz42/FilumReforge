"""Iteration 3-D/E: event envelope and notification outbox deduplication.

Revision ID: 20260715_03
Revises: 20260715_02
Create Date: 2026-07-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260715_03"
down_revision = "20260715_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column(
    "workflow_run_events",
    sa.Column("event_version", sa.Integer(), nullable=False, server_default="1"),
  )
  op.add_column("workflow_run_events", sa.Column("aggregate_version", sa.Integer(), nullable=True))
  op.add_column("workflow_run_events", sa.Column("command_id", sa.String(length=128), nullable=True))
  op.add_column("workflow_run_events", sa.Column("causation_id", sa.Uuid(), nullable=True))
  op.add_column("workflow_run_events", sa.Column("correlation_id", sa.Uuid(), nullable=True))
  op.add_column(
    "workflow_run_events",
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
  )
  op.execute("UPDATE workflow_run_events SET occurred_at = created_at WHERE occurred_at IS NULL")
  op.alter_column("workflow_run_events", "occurred_at", nullable=False)
  op.create_check_constraint(
    "wf_run_events_event_ver_chk",
    "workflow_run_events",
    "event_version > 0",
  )
  op.create_check_constraint(
    "wf_run_events_aggregate_ver_chk",
    "workflow_run_events",
    "aggregate_version IS NULL OR aggregate_version > 0",
  )
  op.create_index(
    "idx_wf_run_events_command",
    "workflow_run_events",
    ["command_id"],
  )
  op.create_index(
    "idx_wf_run_events_correlation",
    "workflow_run_events",
    ["correlation_id", "occurred_at"],
  )

  op.add_column(
    "notification_messages",
    sa.Column("deduplication_key", sa.String(length=160), nullable=True),
  )
  op.create_unique_constraint(
    "uq_notification_messages_dedup_key",
    "notification_messages",
    ["deduplication_key"],
  )


def downgrade() -> None:
  op.drop_constraint(
    "uq_notification_messages_dedup_key",
    "notification_messages",
    type_="unique",
  )
  op.drop_column("notification_messages", "deduplication_key")

  op.drop_index("idx_wf_run_events_correlation", table_name="workflow_run_events")
  op.drop_index("idx_wf_run_events_command", table_name="workflow_run_events")
  op.drop_constraint("wf_run_events_aggregate_ver_chk", "workflow_run_events", type_="check")
  op.drop_constraint("wf_run_events_event_ver_chk", "workflow_run_events", type_="check")
  op.drop_column("workflow_run_events", "occurred_at")
  op.drop_column("workflow_run_events", "correlation_id")
  op.drop_column("workflow_run_events", "causation_id")
  op.drop_column("workflow_run_events", "command_id")
  op.drop_column("workflow_run_events", "aggregate_version")
  op.drop_column("workflow_run_events", "event_version")
