"""W10: additive graph-template bind columns on employment_events.

Revision ID: 20260914_01
Revises: 20260827_01
Create Date: 2026-09-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260914_01"
down_revision = "20260827_01"
branch_labels = None
depends_on = None


def _is_sqlite() -> bool:
  return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
  is_sqlite = _is_sqlite()
  if is_sqlite:
    with op.batch_alter_table("employment_events") as batch_op:
      batch_op.add_column(sa.Column("workflow_graph_template_id", sa.Uuid(), nullable=True))
      batch_op.add_column(sa.Column("workflow_graph_template_version", sa.Integer(), nullable=True))
      batch_op.add_column(
        sa.Column("triggered_workflow_graph_instance_id", sa.Uuid(), nullable=True)
      )
      batch_op.create_foreign_key(
        "fk_employment_events_graph_template",
        "workflow_graph_templates",
        ["workflow_graph_template_id"],
        ["id"],
      )
      batch_op.create_foreign_key(
        "fk_employment_events_graph_instance",
        "workflow_graph_instances",
        ["triggered_workflow_graph_instance_id"],
        ["id"],
      )
      batch_op.create_index(
        "idx_employment_events_graph_template",
        ["workflow_graph_template_id"],
      )
    return

  op.add_column(
    "employment_events",
    sa.Column("workflow_graph_template_id", sa.Uuid(), nullable=True),
  )
  op.add_column(
    "employment_events",
    sa.Column("workflow_graph_template_version", sa.Integer(), nullable=True),
  )
  op.add_column(
    "employment_events",
    sa.Column("triggered_workflow_graph_instance_id", sa.Uuid(), nullable=True),
  )
  op.create_foreign_key(
    "fk_employment_events_graph_template",
    "employment_events",
    "workflow_graph_templates",
    ["workflow_graph_template_id"],
    ["id"],
  )
  op.create_foreign_key(
    "fk_employment_events_graph_instance",
    "employment_events",
    "workflow_graph_instances",
    ["triggered_workflow_graph_instance_id"],
    ["id"],
  )
  op.create_index(
    "idx_employment_events_graph_template",
    "employment_events",
    ["workflow_graph_template_id"],
  )


def downgrade() -> None:
  is_sqlite = _is_sqlite()
  if is_sqlite:
    with op.batch_alter_table("employment_events") as batch_op:
      batch_op.drop_index("idx_employment_events_graph_template")
      batch_op.drop_constraint("fk_employment_events_graph_instance", type_="foreignkey")
      batch_op.drop_constraint("fk_employment_events_graph_template", type_="foreignkey")
      batch_op.drop_column("triggered_workflow_graph_instance_id")
      batch_op.drop_column("workflow_graph_template_version")
      batch_op.drop_column("workflow_graph_template_id")
    return

  op.drop_index("idx_employment_events_graph_template", table_name="employment_events")
  op.drop_constraint("fk_employment_events_graph_instance", "employment_events", type_="foreignkey")
  op.drop_constraint("fk_employment_events_graph_template", "employment_events", type_="foreignkey")
  op.drop_column("employment_events", "triggered_workflow_graph_instance_id")
  op.drop_column("employment_events", "workflow_graph_template_version")
  op.drop_column("employment_events", "workflow_graph_template_id")
