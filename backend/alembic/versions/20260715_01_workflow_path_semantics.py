"""Iteration 2: durable workflow path and activation semantics.

Revision ID: 20260715_01
Revises: 20260713_01
Create Date: 2026-07-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260715_01"
down_revision = "20260713_01"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
  op.add_column(
    "workflow_graph_template_nodes",
    sa.Column("routing_mode", sa.String(length=16), nullable=False, server_default="inclusive"),
  )
  op.create_check_constraint(
    "wf_graph_tpl_nodes_route_chk",
    "workflow_graph_template_nodes",
    "routing_mode in ('exclusive', 'inclusive', 'parallel', 'first_match')",
  )

  op.drop_constraint(
    "workflow_graph_instance_status",
    "workflow_graph_instances",
    type_="check",
  )
  op.create_check_constraint(
    "workflow_graph_instance_status",
    "workflow_graph_instances",
    "status in ('pending', 'active', 'completed', 'cancelled', 'terminated', 'failed')",
  )
  op.add_column("workflow_graph_instances", sa.Column("result", sa.String(length=32), nullable=True))
  op.add_column(
    "workflow_graph_instances",
    sa.Column("diagnostics", _json_type(), nullable=False, server_default=sa.text("'{}'")),
  )
  op.create_check_constraint(
    "wf_graph_instances_result_chk",
    "workflow_graph_instances",
    "result IS NULL OR result in ('success', 'approved', 'rejected', 'cancelled', 'terminated', 'failed')",
  )

  op.drop_constraint(
    "workflow_node_engine_state",
    "workflow_node_instances",
    type_="check",
  )
  op.create_check_constraint(
    "workflow_node_engine_state",
    "workflow_node_instances",
    "engine_state in ('pending', 'activated', 'acknowledged', 'completed', 'terminated', 'skipped', 'failed', 'suspended')",
  )

  op.create_table(
    "workflow_edge_traversals",
    sa.Column("instance_id", sa.Uuid(), nullable=False),
    sa.Column("source_node_instance_id", sa.Uuid(), nullable=False),
    sa.Column("iteration", sa.Integer(), nullable=False),
    sa.Column("from_node_key", sa.String(length=64), nullable=False),
    sa.Column("to_node_key", sa.String(length=64), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("condition", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("evidence", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("context_version", sa.Integer(), nullable=False),
    sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status in ('taken', 'not_taken', 'invalidated')", name="wf_edge_traversals_status_chk"),
    sa.CheckConstraint("iteration > 0", name="wf_edge_traversals_iter_chk"),
    sa.CheckConstraint("context_version > 0", name="wf_edge_traversals_ctx_ver_chk"),
    sa.ForeignKeyConstraint(
      ["instance_id"],
      ["workflow_graph_instances.id"],
      name="fk_wf_edge_traversals_instance",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["source_node_instance_id"],
      ["workflow_node_instances.id"],
      name="fk_wf_edge_traversals_source",
      ondelete="CASCADE",
    ),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint(
      "source_node_instance_id",
      "to_node_key",
      name="uq_wf_edge_traversals_source_target",
    ),
  )
  op.create_index(
    "idx_wf_edge_traversals_instance_iter",
    "workflow_edge_traversals",
    ["instance_id", "iteration"],
  )
  op.create_index(
    "idx_wf_edge_traversals_source",
    "workflow_edge_traversals",
    ["source_node_instance_id"],
  )

  op.create_table(
    "workflow_node_activation_dependencies",
    sa.Column("instance_id", sa.Uuid(), nullable=False),
    sa.Column("node_instance_id", sa.Uuid(), nullable=False),
    sa.Column("source_node_instance_id", sa.Uuid(), nullable=False),
    sa.Column("traversal_id", sa.Uuid(), nullable=False),
    sa.Column("iteration", sa.Integer(), nullable=False),
    sa.Column("target_node_key", sa.String(length=64), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="waiting"),
    sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint(
      "status in ('waiting', 'satisfied', 'cancelled', 'invalidated')",
      name="wf_node_activation_deps_status_chk",
    ),
    sa.CheckConstraint("iteration > 0", name="wf_node_activation_deps_iter_chk"),
    sa.ForeignKeyConstraint(
      ["instance_id"],
      ["workflow_graph_instances.id"],
      name="fk_wf_node_activation_deps_instance",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["node_instance_id"],
      ["workflow_node_instances.id"],
      name="fk_wf_node_activation_deps_node",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["source_node_instance_id"],
      ["workflow_node_instances.id"],
      name="fk_wf_node_activation_deps_source",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["traversal_id"],
      ["workflow_edge_traversals.id"],
      name="fk_wf_node_activation_deps_traversal",
      ondelete="CASCADE",
    ),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint(
      "node_instance_id",
      "source_node_instance_id",
      name="uq_wf_node_activation_deps_pair",
    ),
  )
  op.create_index(
    "idx_wf_node_activation_deps_instance_iter",
    "workflow_node_activation_dependencies",
    ["instance_id", "iteration"],
  )
  op.create_index(
    "idx_wf_node_activation_deps_node",
    "workflow_node_activation_dependencies",
    ["node_instance_id", "status"],
  )


def downgrade() -> None:
  op.drop_index("idx_wf_node_activation_deps_node", table_name="workflow_node_activation_dependencies")
  op.drop_index("idx_wf_node_activation_deps_instance_iter", table_name="workflow_node_activation_dependencies")
  op.drop_table("workflow_node_activation_dependencies")
  op.drop_index("idx_wf_edge_traversals_source", table_name="workflow_edge_traversals")
  op.drop_index("idx_wf_edge_traversals_instance_iter", table_name="workflow_edge_traversals")
  op.drop_table("workflow_edge_traversals")

  op.execute(
    "UPDATE workflow_node_instances SET engine_state = 'terminated' "
    "WHERE engine_state IN ('skipped', 'failed', 'suspended')"
  )
  op.drop_constraint("workflow_node_engine_state", "workflow_node_instances", type_="check")
  op.create_check_constraint(
    "workflow_node_engine_state",
    "workflow_node_instances",
    "engine_state in ('pending', 'activated', 'acknowledged', 'completed', 'terminated')",
  )

  op.execute("UPDATE workflow_graph_instances SET status = 'terminated' WHERE status = 'failed'")
  op.drop_constraint("wf_graph_instances_result_chk", "workflow_graph_instances", type_="check")
  op.drop_column("workflow_graph_instances", "diagnostics")
  op.drop_column("workflow_graph_instances", "result")
  op.drop_constraint("workflow_graph_instance_status", "workflow_graph_instances", type_="check")
  op.create_check_constraint(
    "workflow_graph_instance_status",
    "workflow_graph_instances",
    "status in ('pending', 'active', 'completed', 'cancelled', 'terminated')",
  )

  op.drop_constraint("wf_graph_tpl_nodes_route_chk", "workflow_graph_template_nodes", type_="check")
  op.drop_column("workflow_graph_template_nodes", "routing_mode")
