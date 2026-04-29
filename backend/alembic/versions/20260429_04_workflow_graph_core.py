"""workflow graph core foundation

Revision ID: 20260429_04
Revises: 20260429_03
Create Date: 2026-04-29 18:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260429_04"
down_revision = "20260429_03"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _value_enum(name: str, values: list[str]) -> sa.Enum:
  return sa.Enum(
    *values,
    name=name,
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
  )


def upgrade() -> None:
  graph_template_status = _value_enum(
    "workflow_graph_template_status",
    ["draft", "active", "archived"],
  )
  graph_node_type = _value_enum(
    "workflow_graph_node_type",
    ["task", "approval", "notice"],
  )
  graph_instance_status = _value_enum(
    "workflow_graph_instance_status",
    ["pending", "active", "completed", "cancelled", "terminated"],
  )
  node_engine_state = _value_enum(
    "workflow_node_engine_state",
    ["pending", "activated", "acknowledged", "completed", "terminated"],
  )
  node_business_state = _value_enum(
    "workflow_node_business_state",
    [
      "draft",
      "assigned",
      "accepted",
      "rejected",
      "delegated",
      "doing",
      "pending_review",
      "done",
      "returned_for_rework",
      "cancelled",
    ],
  )
  outbox_event_status = _value_enum(
    "workflow_outbox_event_status",
    ["pending", "retrying", "dispatched", "failed"],
  )

  op.create_table(
    "workflow_graph_templates",
    sa.Column("code", sa.String(length=64), nullable=False),
    sa.Column("base_code", sa.String(length=64), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    sa.Column("name", sa.String(length=120), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("status", graph_template_status, nullable=False, server_default=sa.text("'draft'")),
    sa.Column("context_schema", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("config", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("source_template_id", sa.Uuid(), nullable=True),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_wf_graph_tpls_created_by"),
    sa.ForeignKeyConstraint(
      ["source_template_id"],
      ["workflow_graph_templates.id"],
      name="fk_wf_graph_tpls_source",
    ),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("base_code", "version", name="uq_wf_graph_tpls_base_ver"),
    sa.UniqueConstraint("code", name="uq_wf_graph_tpls_code"),
  )
  op.create_index("idx_wf_graph_tpls_base_code", "workflow_graph_templates", ["base_code"], unique=False)
  op.create_index("idx_wf_graph_tpls_status", "workflow_graph_templates", ["status"], unique=False)

  op.create_table(
    "workflow_graph_template_nodes",
    sa.Column("template_id", sa.Uuid(), nullable=False),
    sa.Column("node_key", sa.String(length=64), nullable=False),
    sa.Column("title", sa.String(length=255), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("node_type", graph_node_type, nullable=False, server_default=sa.text("'task'")),
    sa.Column("assignment_mode", sa.String(length=32), nullable=False, server_default=sa.text("'single'")),
    sa.Column("join_mode", sa.String(length=32), nullable=False, server_default=sa.text("'all'")),
    sa.Column("assignee_rule", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("config", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("assignment_mode in ('single', 'fan_out')", name="wf_graph_tpl_nodes_assign_chk"),
    sa.CheckConstraint("join_mode in ('all', 'any')", name="wf_graph_tpl_nodes_join_chk"),
    sa.ForeignKeyConstraint(
      ["template_id"],
      ["workflow_graph_templates.id"],
      name="fk_wf_graph_tpl_nodes_template",
      ondelete="CASCADE",
    ),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("template_id", "node_key", name="uq_wf_graph_tpl_nodes_key"),
  )
  op.create_index(
    "idx_wf_graph_tpl_nodes_order",
    "workflow_graph_template_nodes",
    ["template_id", "sort_order"],
    unique=False,
  )

  op.create_table(
    "workflow_graph_template_edges",
    sa.Column("template_id", sa.Uuid(), nullable=False),
    sa.Column("from_node_id", sa.Uuid(), nullable=False),
    sa.Column("to_node_id", sa.Uuid(), nullable=False),
    sa.Column("is_reject_path", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column("condition", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("from_node_id <> to_node_id", name="wf_graph_tpl_edges_not_self"),
    sa.ForeignKeyConstraint(
      ["template_id"],
      ["workflow_graph_templates.id"],
      name="fk_wf_graph_tpl_edges_template",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["from_node_id"],
      ["workflow_graph_template_nodes.id"],
      name="fk_wf_graph_tpl_edges_from",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["to_node_id"],
      ["workflow_graph_template_nodes.id"],
      name="fk_wf_graph_tpl_edges_to",
      ondelete="CASCADE",
    ),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("template_id", "from_node_id", "to_node_id", name="uq_wf_graph_tpl_edges_path"),
  )
  op.create_index(
    "idx_wf_graph_tpl_edges_from",
    "workflow_graph_template_edges",
    ["template_id", "from_node_id"],
    unique=False,
  )

  op.create_table(
    "workflow_graph_instances",
    sa.Column("template_id", sa.Uuid(), nullable=True),
    sa.Column("initiator_user_id", sa.Uuid(), nullable=False),
    sa.Column("department_id", sa.Uuid(), nullable=True),
    sa.Column("source_type", sa.String(length=64), nullable=True),
    sa.Column("source_id", sa.Uuid(), nullable=True),
    sa.Column("status", graph_instance_status, nullable=False, server_default=sa.text("'pending'")),
    sa.Column("current_node_key", sa.String(length=64), nullable=True),
    sa.Column("context", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("context_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    sa.Column("max_iterations", sa.Integer(), nullable=False, server_default=sa.text("5")),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("context_version > 0", name="wf_graph_instances_ctx_ver_chk"),
    sa.CheckConstraint("max_iterations > 0", name="wf_graph_instances_max_iter_chk"),
    sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_wf_graph_instances_department"),
    sa.ForeignKeyConstraint(["initiator_user_id"], ["users.id"], name="fk_wf_graph_instances_initiator"),
    sa.ForeignKeyConstraint(["template_id"], ["workflow_graph_templates.id"], name="fk_wf_graph_instances_template"),
    sa.PrimaryKeyConstraint("id"),
  )
  op.create_index("idx_wf_graph_instances_source", "workflow_graph_instances", ["source_type", "source_id"], unique=False)
  op.create_index("idx_wf_graph_instances_status", "workflow_graph_instances", ["status"], unique=False)
  op.create_index("idx_wf_graph_instances_template", "workflow_graph_instances", ["template_id", "status"], unique=False)

  op.create_table(
    "workflow_node_instances",
    sa.Column("instance_id", sa.Uuid(), nullable=False),
    sa.Column("template_node_id", sa.Uuid(), nullable=True),
    sa.Column("node_key", sa.String(length=64), nullable=False),
    sa.Column("title", sa.String(length=255), nullable=False),
    sa.Column("node_type", graph_node_type, nullable=False, server_default=sa.text("'task'")),
    sa.Column("engine_state", node_engine_state, nullable=False, server_default=sa.text("'pending'")),
    sa.Column("business_state", node_business_state, nullable=False, server_default=sa.text("'draft'")),
    sa.Column("assignee_user_id", sa.Uuid(), nullable=True),
    sa.Column("iteration", sa.Integer(), nullable=False, server_default=sa.text("1")),
    sa.Column("node_instance_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    sa.Column("config", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("iteration > 0", name="wf_node_instances_iter_chk"),
    sa.CheckConstraint("node_instance_version > 0", name="wf_node_instances_ver_chk"),
    sa.ForeignKeyConstraint(
      ["assignee_user_id"],
      ["users.id"],
      name="fk_wf_node_instances_assignee",
    ),
    sa.ForeignKeyConstraint(
      ["instance_id"],
      ["workflow_graph_instances.id"],
      name="fk_wf_node_instances_instance",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["template_node_id"],
      ["workflow_graph_template_nodes.id"],
      name="fk_wf_node_instances_template_node",
    ),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint(
      "instance_id",
      "node_key",
      "assignee_user_id",
      "iteration",
      name="uq_wf_node_instances_iter",
    ),
  )
  op.create_index(
    "idx_wf_node_instances_assignee",
    "workflow_node_instances",
    ["assignee_user_id", "engine_state"],
    unique=False,
  )
  op.create_index(
    "idx_wf_node_instances_inst_eng",
    "workflow_node_instances",
    ["instance_id", "engine_state"],
    unique=False,
  )

  op.create_table(
    "workflow_deliverables",
    sa.Column("node_instance_id", sa.Uuid(), nullable=False),
    sa.Column("submitted_by_user_id", sa.Uuid(), nullable=True),
    sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("summary", sa.Text(), nullable=True),
    sa.Column("payload", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("signature", sa.String(length=128), nullable=True),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(
      ["node_instance_id"],
      ["workflow_node_instances.id"],
      name="fk_wf_deliverables_node",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], name="fk_wf_deliverables_user"),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("node_instance_id", name="uq_wf_deliverables_node"),
  )

  op.create_table(
    "workflow_outbox_events",
    sa.Column("instance_id", sa.Uuid(), nullable=False),
    sa.Column("node_instance_id", sa.Uuid(), nullable=True),
    sa.Column("event_type", sa.String(length=64), nullable=False),
    sa.Column("status", outbox_event_status, nullable=False, server_default=sa.text("'pending'")),
    sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_error", sa.Text(), nullable=True),
    sa.Column("payload", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(
      ["instance_id"],
      ["workflow_graph_instances.id"],
      name="fk_wf_outbox_events_instance",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["node_instance_id"],
      ["workflow_node_instances.id"],
      name="fk_wf_outbox_events_node",
      ondelete="SET NULL",
    ),
    sa.PrimaryKeyConstraint("id"),
  )
  op.create_index(
    "idx_wf_outbox_events_inst",
    "workflow_outbox_events",
    ["instance_id", "status"],
    unique=False,
  )
  op.create_index(
    "idx_wf_outbox_events_status",
    "workflow_outbox_events",
    ["status", "available_at"],
    unique=False,
  )


def downgrade() -> None:
  op.drop_index("idx_wf_outbox_events_status", table_name="workflow_outbox_events")
  op.drop_index("idx_wf_outbox_events_inst", table_name="workflow_outbox_events")
  op.drop_table("workflow_outbox_events")

  op.drop_table("workflow_deliverables")

  op.drop_index("idx_wf_node_instances_inst_eng", table_name="workflow_node_instances")
  op.drop_index("idx_wf_node_instances_assignee", table_name="workflow_node_instances")
  op.drop_table("workflow_node_instances")

  op.drop_index("idx_wf_graph_instances_template", table_name="workflow_graph_instances")
  op.drop_index("idx_wf_graph_instances_status", table_name="workflow_graph_instances")
  op.drop_index("idx_wf_graph_instances_source", table_name="workflow_graph_instances")
  op.drop_table("workflow_graph_instances")

  op.drop_index("idx_wf_graph_tpl_edges_from", table_name="workflow_graph_template_edges")
  op.drop_table("workflow_graph_template_edges")

  op.drop_index("idx_wf_graph_tpl_nodes_order", table_name="workflow_graph_template_nodes")
  op.drop_table("workflow_graph_template_nodes")

  op.drop_index("idx_wf_graph_tpls_status", table_name="workflow_graph_templates")
  op.drop_index("idx_wf_graph_tpls_base_code", table_name="workflow_graph_templates")
  op.drop_table("workflow_graph_templates")