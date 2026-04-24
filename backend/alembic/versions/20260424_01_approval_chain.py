"""approval chain: step approval_type, reject routing, downstream trigger

Revision ID: 20260424_01
Revises: 20260422_01
Create Date: 2026-04-24 10:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260424_01"
down_revision = "20260422_01"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
  # --- task_template_steps: add approval fields ---
  op.add_column(
    "task_template_steps",
    sa.Column("approval_type", sa.String(length=32), nullable=False, server_default=sa.text("'none'")),
  )
  op.add_column(
    "task_template_steps",
    sa.Column("reject_target_step_key", sa.String(length=64), nullable=True),
  )
  op.add_column(
    "task_template_steps",
    sa.Column("downstream_trigger", _json_type(), nullable=True),
  )
  op.create_check_constraint(
    "task_tpl_steps_approval_type_check",
    "task_template_steps",
    "approval_type in ('none', 'approve_reject', 'approve_return')",
  )

  # --- task_template_step_runs: add decision + result_payload + iteration ---
  op.add_column(
    "task_template_step_runs",
    sa.Column("iteration", sa.Integer(), nullable=False, server_default=sa.text("1")),
  )
  op.add_column(
    "task_template_step_runs",
    sa.Column("decision", sa.String(length=32), nullable=True),
  )
  op.add_column(
    "task_template_step_runs",
    sa.Column("result_payload", _json_type(), nullable=True),
  )

  # Replace old unique constraint (instance, step, assignee) with one that includes iteration
  op.drop_constraint(
    "uq_task_tpl_step_runs_instance_step_assignee",
    "task_template_step_runs",
    type_="unique",
  )
  op.create_unique_constraint(
    "uq_task_tpl_step_runs_iter",
    "task_template_step_runs",
    ["instance_id", "template_step_id", "assignee_user_id", "iteration"],
  )
  op.create_check_constraint(
    "task_tpl_step_runs_decision_check",
    "task_template_step_runs",
    "decision IS NULL OR decision IN ('approved', 'rejected', 'returned')",
  )


def downgrade() -> None:
  op.drop_constraint("task_tpl_step_runs_decision_check", "task_template_step_runs", type_="check")
  op.drop_constraint("uq_task_tpl_step_runs_iter", "task_template_step_runs", type_="unique")
  op.create_unique_constraint(
    "uq_task_tpl_step_runs_instance_step_assignee",
    "task_template_step_runs",
    ["instance_id", "template_step_id", "assignee_user_id"],
  )
  op.drop_column("task_template_step_runs", "result_payload")
  op.drop_column("task_template_step_runs", "decision")
  op.drop_column("task_template_step_runs", "iteration")

  op.drop_constraint("task_tpl_steps_approval_type_check", "task_template_steps", type_="check")
  op.drop_column("task_template_steps", "downstream_trigger")
  op.drop_column("task_template_steps", "reject_target_step_key")
  op.drop_column("task_template_steps", "approval_type")
