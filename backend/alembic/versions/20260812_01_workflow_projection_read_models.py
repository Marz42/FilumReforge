"""Iteration 5-A expand: rebuildable workflow projection read models.

Revision ID: 20260812_01
Revises: 20260730_01
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260812_01"
down_revision = "20260730_01"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _projection_metadata_columns() -> list[sa.Column]:
  return [
    sa.Column("projection_schema_version", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("source_revision", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("last_event_id", sa.Uuid(), nullable=True),
    sa.Column("projected_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
  ]


def upgrade() -> None:
  op.create_table(
    "task_center_items",
    sa.Column("subject_type", sa.String(length=32), nullable=False),
    sa.Column("item_kind", sa.String(length=32), nullable=False),
    sa.Column("subject_id", sa.Uuid(), nullable=False),
    sa.Column("task_id", sa.Uuid(), nullable=True),
    sa.Column("process_run_id", sa.Uuid(), nullable=True),
    sa.Column("node_instance_id", sa.Uuid(), nullable=True),
    sa.Column("title", sa.String(length=255), nullable=False),
    sa.Column("priority", sa.String(length=16), nullable=False, server_default="medium"),
    sa.Column("raw_status", sa.String(length=32), nullable=False),
    sa.Column("engine_state", sa.String(length=32), nullable=True),
    sa.Column("business_state", sa.String(length=32), nullable=True),
    sa.Column("user_facing_state", sa.String(length=64), nullable=True),
    sa.Column("current_stage_label", sa.String(length=255), nullable=True),
    sa.Column("current_handler_label", sa.String(length=255), nullable=True),
    sa.Column("run_label", sa.String(length=255), nullable=True),
    sa.Column("creator_user_id", sa.Uuid(), nullable=True),
    sa.Column("assignee_user_id", sa.Uuid(), nullable=True),
    sa.Column("current_action_owner_user_id", sa.Uuid(), nullable=True),
    sa.Column("department_id", sa.Uuid(), nullable=True),
    sa.Column("execution_mode", sa.String(length=32), nullable=True),
    sa.Column("assignment_mode", sa.String(length=32), nullable=True),
    sa.Column("requires_action", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("action_type", sa.String(length=64), nullable=True),
    sa.Column("latest_deliverable_submitted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("rework_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("review_quality_score", sa.Integer(), nullable=True),
    sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("hidden_for_non_management", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("audience_user_ids", _json_type(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("audience_department_ids", _json_type(), nullable=False, server_default=sa.text("'[]'")),
    *_projection_metadata_columns(),
    sa.CheckConstraint(
      "subject_type in ('work_item', 'process_run', 'system_alert')",
      name="task_center_items_subject_type_chk",
    ),
    sa.CheckConstraint(
      "item_kind in ('standalone', 'human_task', 'approval', 'process_run', 'system_alert')",
      name="task_center_items_kind_chk",
    ),
    sa.CheckConstraint(
      "(subject_type = 'work_item' AND task_id IS NOT NULL) "
      "OR (subject_type = 'process_run' AND process_run_id IS NOT NULL) "
      "OR subject_type = 'system_alert'",
      name="task_center_items_subject_target_chk",
    ),
    sa.CheckConstraint(
      "(subject_type = 'work_item' AND item_kind in ('standalone', 'human_task', 'approval')) "
      "OR (subject_type = 'process_run' AND item_kind = 'process_run') "
      "OR (subject_type = 'system_alert' AND item_kind = 'system_alert')",
      name="task_center_items_subject_kind_chk",
    ),
    sa.CheckConstraint("rework_count >= 0", name="task_center_items_rework_chk"),
    sa.CheckConstraint(
      "review_quality_score IS NULL OR review_quality_score between 1 and 5",
      name="task_center_items_quality_chk",
    ),
    sa.CheckConstraint(
      "projection_schema_version > 0",
      name="task_center_items_schema_ver_chk",
    ),
    sa.CheckConstraint("source_revision >= 0", name="task_center_items_source_rev_chk"),
    sa.ForeignKeyConstraint(
      ["task_id"], ["tasks.id"], name="fk_task_center_items_task", ondelete="CASCADE"
    ),
    sa.ForeignKeyConstraint(
      ["process_run_id"],
      ["workflow_graph_instances.id"],
      name="fk_task_center_items_process_run",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["node_instance_id"],
      ["workflow_node_instances.id"],
      name="fk_task_center_items_node",
      ondelete="SET NULL",
    ),
    sa.ForeignKeyConstraint(
      ["creator_user_id"], ["users.id"], name="fk_task_center_items_creator", ondelete="SET NULL"
    ),
    sa.ForeignKeyConstraint(
      ["assignee_user_id"], ["users.id"], name="fk_task_center_items_assignee", ondelete="SET NULL"
    ),
    sa.ForeignKeyConstraint(
      ["current_action_owner_user_id"],
      ["users.id"],
      name="fk_task_center_items_action_owner",
      ondelete="SET NULL",
    ),
    sa.ForeignKeyConstraint(
      ["department_id"],
      ["departments.id"],
      name="fk_task_center_items_department",
      ondelete="SET NULL",
    ),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("subject_type", "subject_id", name="uq_task_center_items_subject"),
    sa.UniqueConstraint("task_id", name="uq_task_center_items_task"),
  )
  op.create_index(
    "idx_task_center_items_action_due",
    "task_center_items",
    ["current_action_owner_user_id", "raw_status", "due_at"],
  )
  op.create_index(
    "idx_task_center_items_department_due",
    "task_center_items",
    ["department_id", "raw_status", "due_at"],
  )
  op.create_index(
    "idx_task_center_items_history",
    "task_center_items",
    ["completed_at", "subject_id"],
  )
  op.create_index(
    "idx_task_center_items_process_run",
    "task_center_items",
    ["process_run_id", "raw_status"],
  )

  op.create_table(
    "process_run_summaries",
    sa.Column("process_run_id", sa.Uuid(), nullable=False),
    sa.Column("template_id", sa.Uuid(), nullable=True),
    sa.Column("parent_process_run_id", sa.Uuid(), nullable=True),
    sa.Column("source_type", sa.String(length=64), nullable=True),
    sa.Column("source_id", sa.Uuid(), nullable=True),
    sa.Column("department_id", sa.Uuid(), nullable=True),
    sa.Column("initiator_user_id", sa.Uuid(), nullable=True),
    sa.Column("run_label", sa.String(length=255), nullable=True),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("result", sa.String(length=32), nullable=True),
    sa.Column("current_node_key", sa.String(length=64), nullable=True),
    sa.Column("current_stage_label", sa.String(length=255), nullable=True),
    sa.Column("total_node_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("completed_node_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("active_node_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("pending_node_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("blocked_node_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("latest_event_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("audience_user_ids", _json_type(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("audience_department_ids", _json_type(), nullable=False, server_default=sa.text("'[]'")),
    *_projection_metadata_columns(),
    sa.CheckConstraint(
      "total_node_count >= 0 AND completed_node_count >= 0 "
      "AND active_node_count >= 0 AND pending_node_count >= 0 AND blocked_node_count >= 0 "
      "AND completed_node_count <= total_node_count AND active_node_count <= total_node_count "
      "AND pending_node_count <= total_node_count AND blocked_node_count <= total_node_count",
      name="process_run_summaries_counts_chk",
    ),
    sa.CheckConstraint(
      "progress_percent between 0 and 100",
      name="process_run_summaries_progress_chk",
    ),
    sa.CheckConstraint(
      "projection_schema_version > 0",
      name="process_run_summaries_schema_ver_chk",
    ),
    sa.CheckConstraint("source_revision >= 0", name="process_run_summaries_source_rev_chk"),
    sa.ForeignKeyConstraint(
      ["process_run_id"],
      ["workflow_graph_instances.id"],
      name="fk_process_run_summaries_process_run",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["template_id"],
      ["workflow_graph_templates.id"],
      name="fk_process_run_summaries_template",
      ondelete="SET NULL",
    ),
    sa.ForeignKeyConstraint(
      ["parent_process_run_id"],
      ["workflow_graph_instances.id"],
      name="fk_process_run_summaries_parent",
      ondelete="SET NULL",
    ),
    sa.ForeignKeyConstraint(
      ["department_id"],
      ["departments.id"],
      name="fk_process_run_summaries_department",
      ondelete="SET NULL",
    ),
    sa.ForeignKeyConstraint(
      ["initiator_user_id"],
      ["users.id"],
      name="fk_process_run_summaries_initiator",
      ondelete="SET NULL",
    ),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("process_run_id", name="uq_process_run_summaries_run"),
  )
  op.create_index(
    "idx_process_run_summaries_status_updated",
    "process_run_summaries",
    ["status", "source_updated_at"],
  )
  op.create_index(
    "idx_process_run_summaries_department",
    "process_run_summaries",
    ["department_id", "status"],
  )
  op.create_index(
    "idx_process_run_summaries_parent",
    "process_run_summaries",
    ["parent_process_run_id"],
  )

  op.create_table(
    "node_timeline_entries",
    sa.Column("process_run_id", sa.Uuid(), nullable=True),
    sa.Column("node_instance_id", sa.Uuid(), nullable=True),
    sa.Column("task_id", sa.Uuid(), nullable=True),
    sa.Column("source_type", sa.String(length=32), nullable=False),
    sa.Column("source_id", sa.Uuid(), nullable=False),
    sa.Column("entry_type", sa.String(length=32), nullable=False),
    sa.Column("event_type", sa.String(length=64), nullable=False),
    sa.Column("actor_user_id", sa.Uuid(), nullable=True),
    sa.Column("visibility", sa.String(length=16), nullable=False, server_default="public"),
    sa.Column("title", sa.String(length=255), nullable=False),
    sa.Column("summary", sa.Text(), nullable=True),
    sa.Column("payload", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    *_projection_metadata_columns(),
    sa.CheckConstraint(
      "entry_type in ('node_event', 'work_item_activity', 'comment', 'deliverable', "
      "'approval', 'rework', 'takeover', 'system')",
      name="node_timeline_entries_type_chk",
    ),
    sa.CheckConstraint(
      "visibility in ('public', 'internal', 'management')",
      name="node_timeline_entries_visibility_chk",
    ),
    sa.CheckConstraint(
      "process_run_id IS NOT NULL OR task_id IS NOT NULL",
      name="node_timeline_entries_parent_chk",
    ),
    sa.CheckConstraint(
      "projection_schema_version > 0",
      name="node_timeline_entries_schema_ver_chk",
    ),
    sa.CheckConstraint("source_revision >= 0", name="node_timeline_entries_source_rev_chk"),
    sa.ForeignKeyConstraint(
      ["process_run_id"],
      ["workflow_graph_instances.id"],
      name="fk_node_timeline_entries_process_run",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["node_instance_id"],
      ["workflow_node_instances.id"],
      name="fk_node_timeline_entries_node",
      ondelete="SET NULL",
    ),
    sa.ForeignKeyConstraint(
      ["task_id"], ["tasks.id"], name="fk_node_timeline_entries_task", ondelete="CASCADE"
    ),
    sa.ForeignKeyConstraint(
      ["actor_user_id"],
      ["users.id"],
      name="fk_node_timeline_entries_actor",
      ondelete="SET NULL",
    ),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("source_type", "source_id", name="uq_node_timeline_entries_source"),
  )
  op.create_index(
    "idx_node_timeline_entries_run_time",
    "node_timeline_entries",
    ["process_run_id", "occurred_at", "id"],
  )
  op.create_index(
    "idx_node_timeline_entries_task_time",
    "node_timeline_entries",
    ["task_id", "occurred_at", "id"],
  )
  op.create_index(
    "idx_node_timeline_entries_node_time",
    "node_timeline_entries",
    ["node_instance_id", "occurred_at", "id"],
  )


def downgrade() -> None:
  op.drop_index("idx_node_timeline_entries_node_time", table_name="node_timeline_entries")
  op.drop_index("idx_node_timeline_entries_task_time", table_name="node_timeline_entries")
  op.drop_index("idx_node_timeline_entries_run_time", table_name="node_timeline_entries")
  op.drop_table("node_timeline_entries")

  op.drop_index("idx_process_run_summaries_parent", table_name="process_run_summaries")
  op.drop_index("idx_process_run_summaries_department", table_name="process_run_summaries")
  op.drop_index("idx_process_run_summaries_status_updated", table_name="process_run_summaries")
  op.drop_table("process_run_summaries")

  op.drop_index("idx_task_center_items_process_run", table_name="task_center_items")
  op.drop_index("idx_task_center_items_history", table_name="task_center_items")
  op.drop_index("idx_task_center_items_department_due", table_name="task_center_items")
  op.drop_index("idx_task_center_items_action_due", table_name="task_center_items")
  op.drop_table("task_center_items")
