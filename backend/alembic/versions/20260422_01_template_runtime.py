"""task template runtime

Revision ID: 20260422_01
Revises: 20260421_01
Create Date: 2026-04-22 21:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260422_01"
down_revision = "20260421_01"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _timestamp_columns() -> list[sa.Column]:
  return [
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
  ]


def upgrade() -> None:
  op.add_column(
    "task_template_steps",
    sa.Column("assignment_mode", sa.String(length=32), nullable=False, server_default=sa.text("'single'")),
  )
  op.add_column(
    "task_template_steps",
    sa.Column("join_mode", sa.String(length=32), nullable=False, server_default=sa.text("'all'")),
  )
  op.create_check_constraint(
    "task_tpl_steps_assignment_mode_check",
    "task_template_steps",
    "assignment_mode in ('single', 'fan_out')",
  )
  op.create_check_constraint(
    "task_tpl_steps_join_mode_check",
    "task_template_steps",
    "join_mode in ('all', 'any')",
  )

  op.create_table(
    "task_template_instances",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("template_id", sa.Uuid(), nullable=False),
    sa.Column("initiator_user_id", sa.Uuid(), nullable=False),
    sa.Column("department_id", sa.Uuid(), nullable=True),
    sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'in_progress'")),
    sa.Column("payload", _json_type(), nullable=False),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    *_timestamp_columns(),
    sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_task_tpl_instances_department"),
    sa.ForeignKeyConstraint(["initiator_user_id"], ["users.id"], name="fk_task_tpl_instances_initiator"),
    sa.ForeignKeyConstraint(["template_id"], ["task_templates.id"], name="fk_task_tpl_instances_template"),
    sa.CheckConstraint("status in ('in_progress', 'completed', 'cancelled')", name="task_tpl_instances_status_check"),
    sa.PrimaryKeyConstraint("id", name="pk_task_template_instances"),
  )
  op.create_index("idx_task_tpl_instances_template_status", "task_template_instances", ["template_id", "status"], unique=False)
  op.create_index("idx_task_tpl_instances_initiator_created", "task_template_instances", ["initiator_user_id", "created_at"], unique=False)

  op.create_table(
    "task_template_step_runs",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("instance_id", sa.Uuid(), nullable=False),
    sa.Column("template_step_id", sa.Uuid(), nullable=False),
    sa.Column("assignee_user_id", sa.Uuid(), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'active'")),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    *_timestamp_columns(),
    sa.ForeignKeyConstraint(["assignee_user_id"], ["users.id"], name="fk_task_tpl_step_runs_assignee"),
    sa.ForeignKeyConstraint(["instance_id"], ["task_template_instances.id"], name="fk_task_tpl_step_runs_instance", ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["template_step_id"], ["task_template_steps.id"], name="fk_task_tpl_step_runs_step", ondelete="CASCADE"),
    sa.CheckConstraint("status in ('active', 'completed', 'skipped', 'cancelled')", name="task_tpl_step_runs_status_check"),
    sa.PrimaryKeyConstraint("id", name="pk_task_template_step_runs"),
    sa.UniqueConstraint("instance_id", "template_step_id", "assignee_user_id", name="uq_task_tpl_step_runs_instance_step_assignee"),
  )
  op.create_index("idx_task_tpl_step_runs_instance_status", "task_template_step_runs", ["instance_id", "status"], unique=False)
  op.create_index("idx_task_tpl_step_runs_assignee_status", "task_template_step_runs", ["assignee_user_id", "status"], unique=False)

  op.add_column("tasks", sa.Column("template_instance_id", sa.Uuid(), nullable=True))
  op.add_column("tasks", sa.Column("template_step_run_id", sa.Uuid(), nullable=True))
  op.create_foreign_key("fk_tasks_template_instance", "tasks", "task_template_instances", ["template_instance_id"], ["id"], ondelete="SET NULL")
  op.create_foreign_key("fk_tasks_template_step_run", "tasks", "task_template_step_runs", ["template_step_run_id"], ["id"], ondelete="SET NULL")
  op.create_index("idx_tasks_template_instance_id", "tasks", ["template_instance_id"], unique=False)
  op.create_index("idx_tasks_template_step_run_id", "tasks", ["template_step_run_id"], unique=False)


def downgrade() -> None:
  op.drop_index("idx_tasks_template_step_run_id", table_name="tasks")
  op.drop_index("idx_tasks_template_instance_id", table_name="tasks")
  op.drop_constraint("fk_tasks_template_step_run", "tasks", type_="foreignkey")
  op.drop_constraint("fk_tasks_template_instance", "tasks", type_="foreignkey")
  op.drop_column("tasks", "template_step_run_id")
  op.drop_column("tasks", "template_instance_id")

  op.drop_index("idx_task_tpl_step_runs_assignee_status", table_name="task_template_step_runs")
  op.drop_index("idx_task_tpl_step_runs_instance_status", table_name="task_template_step_runs")
  op.drop_table("task_template_step_runs")

  op.drop_index("idx_task_tpl_instances_initiator_created", table_name="task_template_instances")
  op.drop_index("idx_task_tpl_instances_template_status", table_name="task_template_instances")
  op.drop_table("task_template_instances")

  op.drop_constraint("task_tpl_steps_join_mode_check", "task_template_steps", type_="check")
  op.drop_constraint("task_tpl_steps_assignment_mode_check", "task_template_steps", type_="check")
  op.drop_column("task_template_steps", "join_mode")
  op.drop_column("task_template_steps", "assignment_mode")