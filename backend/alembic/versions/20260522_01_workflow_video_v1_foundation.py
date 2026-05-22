"""workflow video v1: instance_key, run_label, parent_instance_id

Revision ID: 20260522_01
Revises: 20260519_01
Create Date: 2026-05-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260522_01"
down_revision = "20260519_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column(
    "workflow_graph_instances",
    sa.Column("run_label", sa.String(length=255), nullable=True),
  )
  op.add_column(
    "workflow_graph_instances",
    sa.Column("parent_instance_id", sa.Uuid(), nullable=True),
  )
  op.create_foreign_key(
    "fk_wf_graph_instances_parent",
    "workflow_graph_instances",
    "workflow_graph_instances",
    ["parent_instance_id"],
    ["id"],
  )
  op.create_index(
    "idx_wf_graph_instances_parent",
    "workflow_graph_instances",
    ["parent_instance_id"],
  )

  op.add_column(
    "workflow_node_instances",
    sa.Column("instance_key", sa.String(length=64), server_default="singleton", nullable=False),
  )
  op.drop_constraint("uq_wf_node_instances_iter", "workflow_node_instances", type_="unique")
  op.create_unique_constraint(
    "uq_wf_node_instances_iter",
    "workflow_node_instances",
    ["instance_id", "node_key", "instance_key", "iteration"],
  )


def downgrade() -> None:
  op.drop_constraint("uq_wf_node_instances_iter", "workflow_node_instances", type_="unique")
  op.create_unique_constraint(
    "uq_wf_node_instances_iter",
    "workflow_node_instances",
    ["instance_id", "node_key", "assignee_user_id", "iteration"],
  )
  op.drop_column("workflow_node_instances", "instance_key")

  op.drop_index("idx_wf_graph_instances_parent", table_name="workflow_graph_instances")
  op.drop_constraint("fk_wf_graph_instances_parent", "workflow_graph_instances", type_="foreignkey")
  op.drop_column("workflow_graph_instances", "parent_instance_id")
  op.drop_column("workflow_graph_instances", "run_label")
