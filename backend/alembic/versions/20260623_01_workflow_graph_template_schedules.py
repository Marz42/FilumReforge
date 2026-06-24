"""F-24: workflow graph template run schedules

Revision ID: 20260623_01
Revises: 20260523_01
Create Date: 2026-06-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260623_01"
down_revision = "20260523_01"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
  op.create_table(
    "workflow_graph_template_schedules",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("template_id", sa.Uuid(), nullable=False),
    sa.Column("name", sa.String(length=120), nullable=False),
    sa.Column("scope_department_id", sa.Uuid(), nullable=False),
    sa.Column("scope_mode", sa.String(length=16), nullable=False, server_default="self"),
    sa.Column("cron_expr", sa.String(length=128), nullable=False),
    sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Asia/Shanghai"),
    sa.Column("default_inputs", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("run_label_template", sa.String(length=255), nullable=True),
    sa.Column("participant_mode", sa.String(length=16), nullable=False, server_default="all"),
    sa.Column("participant_user_ids", _json_type(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("exclude_department_ids", _json_type(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("exclude_user_ids", _json_type(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_run_status", sa.String(length=32), nullable=True),
    sa.Column("last_run_message", sa.Text(), nullable=True),
    sa.Column("last_run_instance_count", sa.Integer(), nullable=True),
    sa.Column(
      "created_at",
      sa.DateTime(timezone=True),
      nullable=False,
      server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.Column(
      "updated_at",
      sa.DateTime(timezone=True),
      nullable=False,
      server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.CheckConstraint(
      "scope_mode in ('self', 'subtree')",
      name="wf_graph_tpl_schedules_scope_mode_chk",
    ),
    sa.CheckConstraint(
      "participant_mode in ('all', 'subset')",
      name="wf_graph_tpl_schedules_participant_mode_chk",
    ),
    sa.CheckConstraint(
      "last_run_status IS NULL OR last_run_status in ('success', 'failed', 'partial')",
      name="wf_graph_tpl_schedules_last_run_status_chk",
    ),
    sa.ForeignKeyConstraint(
      ["template_id"],
      ["workflow_graph_templates.id"],
      name="fk_wf_graph_tpl_schedules_template",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["scope_department_id"],
      ["departments.id"],
      name="fk_wf_graph_tpl_schedules_scope_department",
    ),
    sa.ForeignKeyConstraint(
      ["created_by"],
      ["users.id"],
      name="fk_wf_graph_tpl_schedules_created_by",
    ),
    sa.PrimaryKeyConstraint("id"),
  )
  op.create_index(
    "idx_wf_graph_tpl_schedules_active_next_run",
    "workflow_graph_template_schedules",
    ["is_active", "next_run_at"],
  )
  op.create_index(
    "idx_wf_graph_tpl_schedules_template",
    "workflow_graph_template_schedules",
    ["template_id"],
  )


def downgrade() -> None:
  op.drop_index("idx_wf_graph_tpl_schedules_template", table_name="workflow_graph_template_schedules")
  op.drop_index("idx_wf_graph_tpl_schedules_active_next_run", table_name="workflow_graph_template_schedules")
  op.drop_table("workflow_graph_template_schedules")
