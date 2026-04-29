"""stage2 lifecycle event automation

Revision ID: 20260429_02
Revises: 20260429_01
Create Date: 2026-04-29 14:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260429_02"
down_revision = "20260429_01"
branch_labels = None
depends_on = None


def _is_sqlite() -> bool:
  return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
  is_sqlite = _is_sqlite()

  if is_sqlite:
    with op.batch_alter_table("employment_events") as batch_op:
      batch_op.add_column(sa.Column("task_template_id", sa.Uuid(), nullable=True))
      batch_op.add_column(sa.Column("workflow_definition_id", sa.Uuid(), nullable=True))
      batch_op.add_column(
        sa.Column(
          "trigger_status",
          sa.String(length=32),
          nullable=False,
          server_default=sa.text("'skipped'"),
        )
      )
      batch_op.add_column(sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True))
      batch_op.add_column(sa.Column("trigger_error", sa.Text(), nullable=True))
      batch_op.add_column(
        sa.Column(
          "trigger_attempt_count",
          sa.Integer(),
          nullable=False,
          server_default=sa.text("0"),
        )
      )
      batch_op.add_column(sa.Column("triggered_template_instance_id", sa.Uuid(), nullable=True))
      batch_op.add_column(sa.Column("triggered_workflow_instance_id", sa.Uuid(), nullable=True))
      batch_op.create_check_constraint(
        "employment_events_trigger_status_check",
        "trigger_status in ('pending', 'processing', 'succeeded', 'failed', 'skipped')",
      )
      batch_op.create_foreign_key(
        "fk_employment_events_task_template",
        "task_templates",
        ["task_template_id"],
        ["id"],
      )
      batch_op.create_foreign_key(
        "fk_employment_events_workflow_definition",
        "workflow_definitions",
        ["workflow_definition_id"],
        ["id"],
      )
      batch_op.create_foreign_key(
        "fk_employment_events_template_instance",
        "task_template_instances",
        ["triggered_template_instance_id"],
        ["id"],
      )
      batch_op.create_foreign_key(
        "fk_employment_events_workflow_instance",
        "workflow_instances",
        ["triggered_workflow_instance_id"],
        ["id"],
      )
  else:
    op.add_column("employment_events", sa.Column("task_template_id", sa.Uuid(), nullable=True))
    op.add_column("employment_events", sa.Column("workflow_definition_id", sa.Uuid(), nullable=True))
    op.add_column(
      "employment_events",
      sa.Column(
        "trigger_status",
        sa.String(length=32),
        nullable=False,
        server_default=sa.text("'skipped'"),
      ),
    )
    op.add_column("employment_events", sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("employment_events", sa.Column("trigger_error", sa.Text(), nullable=True))
    op.add_column(
      "employment_events",
      sa.Column(
        "trigger_attempt_count",
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
      ),
    )
    op.add_column("employment_events", sa.Column("triggered_template_instance_id", sa.Uuid(), nullable=True))
    op.add_column("employment_events", sa.Column("triggered_workflow_instance_id", sa.Uuid(), nullable=True))
    op.create_check_constraint(
      "employment_events_trigger_status_check",
      "employment_events",
      "trigger_status in ('pending', 'processing', 'succeeded', 'failed', 'skipped')",
    )
    op.create_foreign_key(
      "fk_employment_events_task_template",
      "employment_events",
      "task_templates",
      ["task_template_id"],
      ["id"],
    )
    op.create_foreign_key(
      "fk_employment_events_workflow_definition",
      "employment_events",
      "workflow_definitions",
      ["workflow_definition_id"],
      ["id"],
    )
    op.create_foreign_key(
      "fk_employment_events_template_instance",
      "employment_events",
      "task_template_instances",
      ["triggered_template_instance_id"],
      ["id"],
    )
    op.create_foreign_key(
      "fk_employment_events_workflow_instance",
      "employment_events",
      "workflow_instances",
      ["triggered_workflow_instance_id"],
      ["id"],
    )


def downgrade() -> None:
  is_sqlite = _is_sqlite()

  if is_sqlite:
    with op.batch_alter_table("employment_events") as batch_op:
      batch_op.drop_constraint("fk_employment_events_workflow_instance", type_="foreignkey")
      batch_op.drop_constraint("fk_employment_events_template_instance", type_="foreignkey")
      batch_op.drop_constraint("fk_employment_events_workflow_definition", type_="foreignkey")
      batch_op.drop_constraint("fk_employment_events_task_template", type_="foreignkey")
      batch_op.drop_constraint("employment_events_trigger_status_check", type_="check")
      batch_op.drop_column("triggered_workflow_instance_id")
      batch_op.drop_column("triggered_template_instance_id")
      batch_op.drop_column("trigger_attempt_count")
      batch_op.drop_column("trigger_error")
      batch_op.drop_column("triggered_at")
      batch_op.drop_column("trigger_status")
      batch_op.drop_column("workflow_definition_id")
      batch_op.drop_column("task_template_id")
  else:
    op.drop_constraint("fk_employment_events_workflow_instance", "employment_events", type_="foreignkey")
    op.drop_constraint("fk_employment_events_template_instance", "employment_events", type_="foreignkey")
    op.drop_constraint("fk_employment_events_workflow_definition", "employment_events", type_="foreignkey")
    op.drop_constraint("fk_employment_events_task_template", "employment_events", type_="foreignkey")
    op.drop_constraint("employment_events_trigger_status_check", "employment_events", type_="check")
    op.drop_column("employment_events", "triggered_workflow_instance_id")
    op.drop_column("employment_events", "triggered_template_instance_id")
    op.drop_column("employment_events", "trigger_attempt_count")
    op.drop_column("employment_events", "trigger_error")
    op.drop_column("employment_events", "triggered_at")
    op.drop_column("employment_events", "trigger_status")
    op.drop_column("employment_events", "workflow_definition_id")
    op.drop_column("employment_events", "task_template_id")
