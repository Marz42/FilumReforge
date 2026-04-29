"""stage2 template versioning and schedule runtime metadata

Revision ID: 20260429_01
Revises: 20260424_01
Create Date: 2026-04-29 09:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260429_01"
down_revision = "20260424_01"
branch_labels = None
depends_on = None


def _is_sqlite() -> bool:
  return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
  is_sqlite = _is_sqlite()

  if is_sqlite:
    with op.batch_alter_table("task_templates") as batch_op:
      batch_op.add_column(sa.Column("base_code", sa.String(length=64), nullable=True))
      batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")))
      batch_op.add_column(sa.Column("source_template_id", sa.Uuid(), nullable=True))

    op.execute("UPDATE task_templates SET base_code = code WHERE base_code IS NULL")

    with op.batch_alter_table("task_templates") as batch_op:
      batch_op.alter_column("base_code", existing_type=sa.String(length=64), nullable=False)
      batch_op.create_index("idx_task_templates_base_code", ["base_code"], unique=False)
      batch_op.create_unique_constraint("uq_task_templates_base_version", ["base_code", "version"])
      batch_op.create_foreign_key(
        "fk_task_templates_source_template",
        "task_templates",
        ["source_template_id"],
        ["id"],
      )

    with op.batch_alter_table("task_schedules") as batch_op:
      batch_op.add_column(sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True))
      batch_op.add_column(sa.Column("last_run_status", sa.String(length=32), nullable=True))
      batch_op.add_column(sa.Column("last_run_message", sa.Text(), nullable=True))
      batch_op.add_column(sa.Column("last_run_task_count", sa.Integer(), nullable=True))
      batch_op.create_check_constraint(
        "task_schedules_last_run_status_check",
        "last_run_status IS NULL OR last_run_status in ('success', 'failed')",
      )
  else:
    op.add_column("task_templates", sa.Column("base_code", sa.String(length=64), nullable=True))
    op.add_column(
      "task_templates",
      sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column("task_templates", sa.Column("source_template_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE task_templates SET base_code = code WHERE base_code IS NULL")
    op.alter_column("task_templates", "base_code", existing_type=sa.String(length=64), nullable=False)
    op.create_index("idx_task_templates_base_code", "task_templates", ["base_code"], unique=False)
    op.create_unique_constraint(
      "uq_task_templates_base_version",
      "task_templates",
      ["base_code", "version"],
    )
    op.create_foreign_key(
      "fk_task_templates_source_template",
      "task_templates",
      "task_templates",
      ["source_template_id"],
      ["id"],
    )

    op.add_column("task_schedules", sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("task_schedules", sa.Column("last_run_status", sa.String(length=32), nullable=True))
    op.add_column("task_schedules", sa.Column("last_run_message", sa.Text(), nullable=True))
    op.add_column("task_schedules", sa.Column("last_run_task_count", sa.Integer(), nullable=True))
    op.create_check_constraint(
      "task_schedules_last_run_status_check",
      "task_schedules",
      "last_run_status IS NULL OR last_run_status in ('success', 'failed')",
    )


def downgrade() -> None:
  is_sqlite = _is_sqlite()

  if is_sqlite:
    with op.batch_alter_table("task_schedules") as batch_op:
      batch_op.drop_constraint("task_schedules_last_run_status_check", type_="check")
      batch_op.drop_column("last_run_task_count")
      batch_op.drop_column("last_run_message")
      batch_op.drop_column("last_run_status")
      batch_op.drop_column("last_run_at")

    with op.batch_alter_table("task_templates") as batch_op:
      batch_op.drop_constraint("fk_task_templates_source_template", type_="foreignkey")
      batch_op.drop_constraint("uq_task_templates_base_version", type_="unique")
      batch_op.drop_index("idx_task_templates_base_code")
      batch_op.drop_column("source_template_id")
      batch_op.drop_column("version")
      batch_op.drop_column("base_code")
  else:
    op.drop_constraint("task_schedules_last_run_status_check", "task_schedules", type_="check")
    op.drop_column("task_schedules", "last_run_task_count")
    op.drop_column("task_schedules", "last_run_message")
    op.drop_column("task_schedules", "last_run_status")
    op.drop_column("task_schedules", "last_run_at")

    op.drop_constraint("fk_task_templates_source_template", "task_templates", type_="foreignkey")
    op.drop_constraint("uq_task_templates_base_version", "task_templates", type_="unique")
    op.drop_index("idx_task_templates_base_code", table_name="task_templates")
    op.drop_column("task_templates", "source_template_id")
    op.drop_column("task_templates", "version")
    op.drop_column("task_templates", "base_code")