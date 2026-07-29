"""Add audit events for published template availability scope expansion.

Revision ID: 20260730_01
Revises: 20260722_01
Create Date: 2026-07-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260730_01"
down_revision = "20260722_01"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
  op.create_table(
    "workflow_graph_template_scope_events",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("template_id", sa.Uuid(), nullable=False),
    sa.Column("actor_user_id", sa.Uuid(), nullable=False),
    sa.Column("action", sa.String(length=32), nullable=False),
    sa.Column("before_scope_mode", sa.String(length=16), nullable=False),
    sa.Column("before_department_ids", _json_type(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("after_scope_mode", sa.String(length=16), nullable=False),
    sa.Column("after_department_ids", _json_type(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("added_department_ids", _json_type(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("reason", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(
      ["template_id"],
      ["workflow_graph_templates.id"],
      name="fk_wf_graph_tpl_scope_events_template",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["actor_user_id"],
      ["users.id"],
      name="fk_wf_graph_tpl_scope_events_actor",
    ),
    sa.PrimaryKeyConstraint("id"),
  )
  op.create_index(
    "idx_wf_graph_tpl_scope_events_template",
    "workflow_graph_template_scope_events",
    ["template_id", "created_at"],
  )
  op.create_index(
    "idx_wf_graph_tpl_scope_events_actor",
    "workflow_graph_template_scope_events",
    ["actor_user_id", "created_at"],
  )


def downgrade() -> None:
  op.drop_index("idx_wf_graph_tpl_scope_events_actor", table_name="workflow_graph_template_scope_events")
  op.drop_index("idx_wf_graph_tpl_scope_events_template", table_name="workflow_graph_template_scope_events")
  op.drop_table("workflow_graph_template_scope_events")
