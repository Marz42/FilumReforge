"""Iteration 1: explicit template scope and workflow definition snapshots.

Revision ID: 20260713_01
Revises: 20260709_01
Create Date: 2026-07-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260713_01"
down_revision = "20260709_01"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
  op.add_column(
    "workflow_graph_templates",
    sa.Column("scope_mode", sa.String(length=16), nullable=True, server_default="global"),
  )
  op.create_check_constraint(
    "wf_graph_tpls_scope_mode_chk",
    "workflow_graph_templates",
    "scope_mode in ('global', 'departments')",
  )

  bind = op.get_bind()
  templates = sa.table(
    "workflow_graph_templates",
    sa.column("id"),
    sa.column("scope_mode"),
    sa.column("scope_department_ids", _json_type()),
  )
  rows = bind.execute(sa.select(templates.c.id, templates.c.scope_department_ids)).all()
  for template_id, department_ids in rows:
    scope_mode = "departments" if isinstance(department_ids, list) and department_ids else "global"
    bind.execute(
      templates.update().where(templates.c.id == template_id).values(scope_mode=scope_mode)
    )

  op.add_column(
    "workflow_graph_instances",
    sa.Column("definition_snapshot", _json_type(), nullable=True),
  )
  op.add_column(
    "workflow_graph_instances",
    sa.Column("definition_hash", sa.String(length=64), nullable=True),
  )
  op.add_column(
    "workflow_graph_instances",
    sa.Column("engine_version", sa.String(length=32), nullable=True, server_default="legacy-v1"),
  )
  op.add_column(
    "workflow_graph_instances",
    sa.Column("executor_kind", sa.String(length=16), nullable=True, server_default="legacy"),
  )
  op.create_check_constraint(
    "wf_graph_instances_executor_chk",
    "workflow_graph_instances",
    "executor_kind in ('legacy', 'snapshot')",
  )


def downgrade() -> None:
  op.drop_constraint("wf_graph_instances_executor_chk", "workflow_graph_instances", type_="check")
  op.drop_column("workflow_graph_instances", "executor_kind")
  op.drop_column("workflow_graph_instances", "engine_version")
  op.drop_column("workflow_graph_instances", "definition_hash")
  op.drop_column("workflow_graph_instances", "definition_snapshot")
  op.drop_constraint("wf_graph_tpls_scope_mode_chk", "workflow_graph_templates", type_="check")
  op.drop_column("workflow_graph_templates", "scope_mode")
