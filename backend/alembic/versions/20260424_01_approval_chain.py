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


def _is_sqlite() -> bool:
  return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
  is_sqlite = _is_sqlite()

  if is_sqlite:
    with op.batch_alter_table("task_template_steps") as batch_op:
      batch_op.add_column(
        sa.Column("approval_type", sa.String(length=32), nullable=False, server_default=sa.text("'none'"))
      )
      batch_op.add_column(sa.Column("reject_target_step_key", sa.String(length=64), nullable=True))
      batch_op.add_column(sa.Column("downstream_trigger", _json_type(), nullable=True))
      batch_op.create_check_constraint(
        "task_tpl_steps_approval_type_check",
        "approval_type in ('none', 'approve_reject', 'approve_return')",
      )

    with op.batch_alter_table("task_template_step_runs") as batch_op:
      batch_op.add_column(sa.Column("iteration", sa.Integer(), nullable=False, server_default=sa.text("1")))
      batch_op.add_column(sa.Column("decision", sa.String(length=32), nullable=True))
      batch_op.add_column(sa.Column("result_payload", _json_type(), nullable=True))
      batch_op.drop_constraint("uq_task_tpl_step_runs_instance_step_assignee", type_="unique")
      batch_op.create_unique_constraint(
        "uq_task_tpl_step_runs_iter",
        ["instance_id", "template_step_id", "assignee_user_id", "iteration"],
      )
      batch_op.create_check_constraint(
        "task_tpl_step_runs_decision_check",
        "decision IS NULL OR decision IN ('approved', 'rejected', 'returned')",
      )
  else:
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
  is_sqlite = _is_sqlite()

  if is_sqlite:
    with op.batch_alter_table("task_template_step_runs") as batch_op:
      batch_op.drop_constraint("task_tpl_step_runs_decision_check", type_="check")
      batch_op.drop_constraint("uq_task_tpl_step_runs_iter", type_="unique")
      batch_op.create_unique_constraint(
        "uq_task_tpl_step_runs_instance_step_assignee",
        ["instance_id", "template_step_id", "assignee_user_id"],
      )
      batch_op.drop_column("result_payload")
      batch_op.drop_column("decision")
      batch_op.drop_column("iteration")

    with op.batch_alter_table("task_template_steps") as batch_op:
      batch_op.drop_constraint("task_tpl_steps_approval_type_check", type_="check")
      batch_op.drop_column("downstream_trigger")
      batch_op.drop_column("reject_target_step_key")
      batch_op.drop_column("approval_type")
  else:
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
