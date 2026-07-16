"""Iteration 3-F expand: Link lineage and operational incident queue.

Revision ID: 20260716_01
Revises: 20260715_03
Create Date: 2026-07-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260716_01"
down_revision = "20260715_03"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
  op.add_column("workflow_human_task_links", sa.Column("iteration", sa.Integer(), nullable=True))
  op.add_column(
    "workflow_human_task_links",
    sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
  )
  op.add_column(
    "workflow_human_task_links",
    sa.Column("superseded_by_link_id", sa.Uuid(), nullable=True),
  )
  op.create_foreign_key(
    "fk_wf_human_task_links_superseded_by",
    "workflow_human_task_links",
    "workflow_human_task_links",
    ["superseded_by_link_id"],
    ["id"],
    ondelete="SET NULL",
  )

  bind = op.get_bind()
  if bind.dialect.name == "postgresql":
    op.execute(
      """
      UPDATE workflow_human_task_links AS link
      SET iteration = node.iteration
      FROM workflow_node_instances AS node
      WHERE node.id = link.node_instance_id AND link.iteration IS NULL
      """
    )
  else:
    op.execute(
      """
      UPDATE workflow_human_task_links
      SET iteration = (
        SELECT workflow_node_instances.iteration
        FROM workflow_node_instances
        WHERE workflow_node_instances.id = workflow_human_task_links.node_instance_id
      )
      WHERE iteration IS NULL
      """
    )

  op.create_table(
    "workflow_operational_incidents",
    sa.Column("category", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
    sa.Column("severity", sa.String(length=16), nullable=False, server_default="warning"),
    sa.Column("fingerprint", sa.String(length=64), nullable=False),
    sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("instance_id", sa.Uuid(), nullable=True),
    sa.Column("node_instance_id", sa.Uuid(), nullable=True),
    sa.Column("task_id", sa.Uuid(), nullable=True),
    sa.Column("command_receipt_id", sa.Uuid(), nullable=True),
    sa.Column("outbox_event_id", sa.Uuid(), nullable=True),
    sa.Column("engine_version", sa.String(length=32), nullable=True),
    sa.Column("details", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint(
      "category in ('link_fallback', 'link_mismatch', 'link_backfill_issue', "
      "'coordinator_failure', 'receipt_conflict', 'outbox_duplicate', 'migration_incomplete')",
      name="wf_op_inc_category_chk",
    ),
    sa.CheckConstraint(
      "status in ('open', 'resolved', 'ignored')",
      name="wf_op_inc_status_chk",
    ),
    sa.CheckConstraint(
      "severity in ('info', 'warning', 'error', 'critical')",
      name="wf_op_inc_severity_chk",
    ),
    sa.CheckConstraint("occurrence_count > 0", name="wf_op_inc_count_chk"),
    sa.ForeignKeyConstraint(
      ["instance_id"],
      ["workflow_graph_instances.id"],
      name="fk_wf_operational_incidents_instance",
      ondelete="SET NULL",
    ),
    sa.ForeignKeyConstraint(
      ["node_instance_id"],
      ["workflow_node_instances.id"],
      name="fk_wf_operational_incidents_node",
      ondelete="SET NULL",
    ),
    sa.ForeignKeyConstraint(
      ["task_id"],
      ["tasks.id"],
      name="fk_wf_operational_incidents_task",
      ondelete="SET NULL",
    ),
    sa.ForeignKeyConstraint(
      ["command_receipt_id"],
      ["workflow_command_receipts.id"],
      name="fk_wf_operational_incidents_receipt",
      ondelete="SET NULL",
    ),
    sa.ForeignKeyConstraint(
      ["outbox_event_id"],
      ["workflow_outbox_events.id"],
      name="fk_wf_operational_incidents_outbox",
      ondelete="SET NULL",
    ),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("category", "fingerprint", name="uq_wf_operational_incident_identity"),
  )
  op.create_index(
    "idx_wf_operational_incidents_status",
    "workflow_operational_incidents",
    ["status", "severity", "last_seen_at"],
  )
  op.create_index(
    "idx_wf_operational_incidents_category",
    "workflow_operational_incidents",
    ["category", "last_seen_at"],
  )
  op.create_index(
    "idx_wf_operational_incidents_instance",
    "workflow_operational_incidents",
    ["instance_id", "status"],
  )


def downgrade() -> None:
  op.drop_index("idx_wf_operational_incidents_instance", table_name="workflow_operational_incidents")
  op.drop_index("idx_wf_operational_incidents_category", table_name="workflow_operational_incidents")
  op.drop_index("idx_wf_operational_incidents_status", table_name="workflow_operational_incidents")
  op.drop_table("workflow_operational_incidents")
  op.drop_constraint(
    "fk_wf_human_task_links_superseded_by",
    "workflow_human_task_links",
    type_="foreignkey",
  )
  op.drop_column("workflow_human_task_links", "superseded_by_link_id")
  op.drop_column("workflow_human_task_links", "superseded_at")
  op.drop_column("workflow_human_task_links", "iteration")
