"""Iteration 3-A: human-task links and workflow command receipts.

Revision ID: 20260715_02
Revises: 20260715_01
Create Date: 2026-07-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260715_02"
down_revision = "20260715_01"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
  op.create_table(
    "workflow_human_task_links",
    sa.Column("instance_id", sa.Uuid(), nullable=False),
    sa.Column("node_instance_id", sa.Uuid(), nullable=False),
    sa.Column("task_id", sa.Uuid(), nullable=False),
    sa.Column("link_role", sa.String(length=16), nullable=False, server_default="primary"),
    sa.Column("lifecycle", sa.String(length=16), nullable=False, server_default="active"),
    sa.Column("source", sa.String(length=16), nullable=False, server_default="runtime"),
    sa.Column("link_metadata", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint(
      "link_role in ('primary', 'supporting', 'observer')",
      name="wf_human_task_links_role_chk",
    ),
    sa.CheckConstraint(
      "lifecycle in ('active', 'completed', 'cancelled', 'invalidated')",
      name="wf_human_task_links_lifecycle_chk",
    ),
    sa.CheckConstraint(
      "source in ('runtime', 'manual_compat', 'backfill')",
      name="wf_human_task_links_source_chk",
    ),
    sa.ForeignKeyConstraint(
      ["instance_id"],
      ["workflow_graph_instances.id"],
      name="fk_wf_human_task_links_instance",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["node_instance_id"],
      ["workflow_node_instances.id"],
      name="fk_wf_human_task_links_node",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["task_id"],
      ["tasks.id"],
      name="fk_wf_human_task_links_task",
      ondelete="CASCADE",
    ),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("task_id", name="uq_wf_human_task_links_task"),
    sa.UniqueConstraint(
      "node_instance_id",
      "task_id",
      name="uq_wf_human_task_links_node_task",
    ),
  )
  op.create_index(
    "idx_wf_human_task_links_node_lifecycle",
    "workflow_human_task_links",
    ["node_instance_id", "lifecycle"],
  )
  op.create_index(
    "idx_wf_human_task_links_instance_lifecycle",
    "workflow_human_task_links",
    ["instance_id", "lifecycle"],
  )
  op.create_index(
    "uq_wf_human_task_links_active_primary",
    "workflow_human_task_links",
    ["node_instance_id"],
    unique=True,
    postgresql_where=sa.text("link_role = 'primary' AND lifecycle = 'active'"),
    sqlite_where=sa.text("link_role = 'primary' AND lifecycle = 'active'"),
  )

  op.create_table(
    "workflow_command_receipts",
    sa.Column("command_id", sa.String(length=128), nullable=False),
    sa.Column("command_type", sa.String(length=64), nullable=False),
    sa.Column("actor_key", sa.String(length=64), nullable=False),
    sa.Column("actor_user_id", sa.Uuid(), nullable=True),
    sa.Column("payload_hash", sa.String(length=64), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="processing"),
    sa.Column("aggregate_type", sa.String(length=32), nullable=True),
    sa.Column("aggregate_id", sa.Uuid(), nullable=True),
    sa.Column("result", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("error", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint(
      "status in ('processing', 'succeeded', 'failed')",
      name="wf_command_receipts_status_chk",
    ),
    sa.CheckConstraint(
      "length(trim(actor_key)) > 0",
      name="wf_command_receipts_actor_key_chk",
    ),
    sa.CheckConstraint(
      "length(payload_hash) = 64",
      name="wf_command_receipts_payload_hash_chk",
    ),
    sa.ForeignKeyConstraint(
      ["actor_user_id"],
      ["users.id"],
      name="fk_wf_command_receipts_actor",
      ondelete="SET NULL",
    ),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint(
      "actor_key",
      "command_type",
      "command_id",
      name="uq_wf_command_receipts_identity",
    ),
  )
  op.create_index(
    "idx_wf_command_receipts_aggregate",
    "workflow_command_receipts",
    ["aggregate_type", "aggregate_id"],
  )
  op.create_index(
    "idx_wf_command_receipts_status",
    "workflow_command_receipts",
    ["status", "created_at"],
  )


def downgrade() -> None:
  op.drop_index("idx_wf_command_receipts_status", table_name="workflow_command_receipts")
  op.drop_index("idx_wf_command_receipts_aggregate", table_name="workflow_command_receipts")
  op.drop_table("workflow_command_receipts")

  op.drop_index("uq_wf_human_task_links_active_primary", table_name="workflow_human_task_links")
  op.drop_index("idx_wf_human_task_links_instance_lifecycle", table_name="workflow_human_task_links")
  op.drop_index("idx_wf_human_task_links_node_lifecycle", table_name="workflow_human_task_links")
  op.drop_table("workflow_human_task_links")
