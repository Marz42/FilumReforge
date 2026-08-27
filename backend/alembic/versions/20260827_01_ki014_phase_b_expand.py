"""KI-014 Phase B: expand task status storage and validate workflow defaults.

Revision ID: 20260827_01
Revises: 20260812_04
Create Date: 2026-08-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260827_01"
down_revision = "20260812_04"
branch_labels = None
depends_on = None


TASKS_STATUS_CHECK = sa.schema.conv("ck_tasks_status_compat_ki014")
TASK_LOGS_FROM_STATUS_CHECK = sa.schema.conv("ck_task_logs_from_status_compat_ki014")
TASK_LOGS_TO_STATUS_CHECK = sa.schema.conv("ck_task_logs_to_status_compat_ki014")
TEMPLATE_SCOPE_MODE_NOT_NULL_CHECK = sa.schema.conv("ck_wf_graph_tpls_scope_mode_nn_ki014")
INSTANCE_ENGINE_VERSION_NOT_NULL_CHECK = sa.schema.conv(
  "ck_wf_graph_instances_engine_version_nn_ki014"
)
INSTANCE_EXECUTOR_KIND_NOT_NULL_CHECK = sa.schema.conv(
  "ck_wf_graph_instances_executor_kind_nn_ki014"
)

TASK_STATUS_VALUES_SQL = "'todo', 'doing', 'review', 'blocked', 'done'"


def _create_postgresql_check(table_name: str, name: str, condition: str) -> None:
  op.create_check_constraint(
    name,
    table_name,
    condition,
    postgresql_not_valid=True,
  )
  op.execute(sa.text(f'ALTER TABLE "{table_name}" VALIDATE CONSTRAINT "{name}"'))


def _backfill_workflow_defaults(dialect: str) -> None:
  if dialect == "postgresql":
    op.execute(
      sa.text(
        """
        UPDATE workflow_graph_templates
        SET scope_mode = CASE
          WHEN jsonb_typeof(scope_department_ids) = 'array'
            AND jsonb_array_length(scope_department_ids) > 0
          THEN 'departments'
          ELSE 'global'
        END
        WHERE scope_mode IS NULL
        """
      )
    )
  else:
    op.execute(
      sa.text(
        """
        UPDATE workflow_graph_templates
        SET scope_mode = CASE
          WHEN json_array_length(scope_department_ids) > 0 THEN 'departments'
          ELSE 'global'
        END
        WHERE scope_mode IS NULL
        """
      )
    )

  op.execute(
    sa.text(
      """
      UPDATE workflow_graph_instances
      SET engine_version = 'legacy-v1'
      WHERE engine_version IS NULL
      """
    )
  )
  op.execute(
    sa.text(
      """
      UPDATE workflow_graph_instances
      SET executor_kind = 'legacy'
      WHERE executor_kind IS NULL
      """
    )
  )


def _upgrade_sqlite() -> None:
  with op.batch_alter_table("tasks", recreate="always") as batch_op:
    batch_op.alter_column(
      "status",
      existing_type=sa.String(length=6),
      type_=sa.String(length=16),
      existing_nullable=False,
      existing_server_default=sa.text("'todo'"),
    )
    batch_op.create_check_constraint(
      TASKS_STATUS_CHECK,
      f"lower(status) in ({TASK_STATUS_VALUES_SQL})",
    )

  with op.batch_alter_table("task_logs", recreate="always") as batch_op:
    batch_op.alter_column(
      "from_status",
      existing_type=sa.String(length=6),
      type_=sa.String(length=16),
      existing_nullable=True,
    )
    batch_op.alter_column(
      "to_status",
      existing_type=sa.String(length=6),
      type_=sa.String(length=16),
      existing_nullable=True,
    )
    batch_op.create_check_constraint(
      TASK_LOGS_FROM_STATUS_CHECK,
      f"from_status IS NULL OR lower(from_status) in ({TASK_STATUS_VALUES_SQL})",
    )
    batch_op.create_check_constraint(
      TASK_LOGS_TO_STATUS_CHECK,
      f"to_status IS NULL OR lower(to_status) in ({TASK_STATUS_VALUES_SQL})",
    )

  with op.batch_alter_table("workflow_graph_templates", recreate="always") as batch_op:
    batch_op.create_check_constraint(
      TEMPLATE_SCOPE_MODE_NOT_NULL_CHECK,
      "scope_mode IS NOT NULL",
    )

  with op.batch_alter_table("workflow_graph_instances", recreate="always") as batch_op:
    batch_op.create_check_constraint(
      INSTANCE_ENGINE_VERSION_NOT_NULL_CHECK,
      "engine_version IS NOT NULL",
    )
    batch_op.create_check_constraint(
      INSTANCE_EXECUTOR_KIND_NOT_NULL_CHECK,
      "executor_kind IS NOT NULL",
    )


def _upgrade_postgresql() -> None:
  op.alter_column(
    "tasks",
    "status",
    existing_type=sa.String(length=6),
    type_=sa.String(length=16),
    existing_nullable=False,
    existing_server_default=sa.text("'todo'::character varying"),
  )
  op.alter_column(
    "task_logs",
    "from_status",
    existing_type=sa.String(length=6),
    type_=sa.String(length=16),
    existing_nullable=True,
  )
  op.alter_column(
    "task_logs",
    "to_status",
    existing_type=sa.String(length=6),
    type_=sa.String(length=16),
    existing_nullable=True,
  )

  _create_postgresql_check(
    "tasks",
    TASKS_STATUS_CHECK,
    f"lower(status) in ({TASK_STATUS_VALUES_SQL})",
  )
  _create_postgresql_check(
    "task_logs",
    TASK_LOGS_FROM_STATUS_CHECK,
    f"from_status IS NULL OR lower(from_status) in ({TASK_STATUS_VALUES_SQL})",
  )
  _create_postgresql_check(
    "task_logs",
    TASK_LOGS_TO_STATUS_CHECK,
    f"to_status IS NULL OR lower(to_status) in ({TASK_STATUS_VALUES_SQL})",
  )
  _create_postgresql_check(
    "workflow_graph_templates",
    TEMPLATE_SCOPE_MODE_NOT_NULL_CHECK,
    "scope_mode IS NOT NULL",
  )
  _create_postgresql_check(
    "workflow_graph_instances",
    INSTANCE_ENGINE_VERSION_NOT_NULL_CHECK,
    "engine_version IS NOT NULL",
  )
  _create_postgresql_check(
    "workflow_graph_instances",
    INSTANCE_EXECUTOR_KIND_NOT_NULL_CHECK,
    "executor_kind IS NOT NULL",
  )


def upgrade() -> None:
  dialect = op.get_bind().dialect.name
  _backfill_workflow_defaults(dialect)
  if dialect == "sqlite":
    _upgrade_sqlite()
    return
  _upgrade_postgresql()


def _assert_statuses_fit_legacy_width(dialect: str) -> None:
  if dialect == "postgresql":
    op.execute(
      sa.text(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM tasks WHERE length(status) > 6)
            OR EXISTS (
              SELECT 1 FROM task_logs
              WHERE length(from_status) > 6 OR length(to_status) > 6
            )
          THEN
            RAISE EXCEPTION
              'KI-014 downgrade refused: task status values exceed legacy VARCHAR(6)';
          END IF;
        END
        $$
        """
      )
    )
    return

  bind = op.get_bind()
  too_wide = bind.execute(
    sa.text(
      """
      SELECT
        (SELECT count(*) FROM tasks WHERE length(status) > 6)
        +
        (SELECT count(*) FROM task_logs
         WHERE length(from_status) > 6 OR length(to_status) > 6)
      """
    )
  ).scalar_one()
  if too_wide:
    raise RuntimeError("KI-014 downgrade refused: task status values exceed legacy VARCHAR(6)")


def _downgrade_sqlite() -> None:
  with op.batch_alter_table("workflow_graph_instances", recreate="always") as batch_op:
    batch_op.drop_constraint(INSTANCE_EXECUTOR_KIND_NOT_NULL_CHECK, type_="check")
    batch_op.drop_constraint(INSTANCE_ENGINE_VERSION_NOT_NULL_CHECK, type_="check")

  with op.batch_alter_table("workflow_graph_templates", recreate="always") as batch_op:
    batch_op.drop_constraint(TEMPLATE_SCOPE_MODE_NOT_NULL_CHECK, type_="check")

  with op.batch_alter_table("task_logs", recreate="always") as batch_op:
    batch_op.drop_constraint(TASK_LOGS_TO_STATUS_CHECK, type_="check")
    batch_op.drop_constraint(TASK_LOGS_FROM_STATUS_CHECK, type_="check")
    batch_op.alter_column(
      "to_status",
      existing_type=sa.String(length=16),
      type_=sa.String(length=6),
      existing_nullable=True,
    )
    batch_op.alter_column(
      "from_status",
      existing_type=sa.String(length=16),
      type_=sa.String(length=6),
      existing_nullable=True,
    )

  with op.batch_alter_table("tasks", recreate="always") as batch_op:
    batch_op.drop_constraint(TASKS_STATUS_CHECK, type_="check")
    batch_op.alter_column(
      "status",
      existing_type=sa.String(length=16),
      type_=sa.String(length=6),
      existing_nullable=False,
      existing_server_default=sa.text("'todo'"),
    )


def _downgrade_postgresql() -> None:
  op.drop_constraint(
    INSTANCE_EXECUTOR_KIND_NOT_NULL_CHECK,
    "workflow_graph_instances",
    type_="check",
  )
  op.drop_constraint(
    INSTANCE_ENGINE_VERSION_NOT_NULL_CHECK,
    "workflow_graph_instances",
    type_="check",
  )
  op.drop_constraint(
    TEMPLATE_SCOPE_MODE_NOT_NULL_CHECK,
    "workflow_graph_templates",
    type_="check",
  )
  op.drop_constraint(TASK_LOGS_TO_STATUS_CHECK, "task_logs", type_="check")
  op.drop_constraint(TASK_LOGS_FROM_STATUS_CHECK, "task_logs", type_="check")
  op.drop_constraint(TASKS_STATUS_CHECK, "tasks", type_="check")

  op.alter_column(
    "task_logs",
    "to_status",
    existing_type=sa.String(length=16),
    type_=sa.String(length=6),
    existing_nullable=True,
  )
  op.alter_column(
    "task_logs",
    "from_status",
    existing_type=sa.String(length=16),
    type_=sa.String(length=6),
    existing_nullable=True,
  )
  op.alter_column(
    "tasks",
    "status",
    existing_type=sa.String(length=16),
    type_=sa.String(length=6),
    existing_nullable=False,
    existing_server_default=sa.text("'todo'::character varying"),
  )


def downgrade() -> None:
  dialect = op.get_bind().dialect.name
  _assert_statuses_fit_legacy_width(dialect)
  if dialect == "sqlite":
    _downgrade_sqlite()
    return
  _downgrade_postgresql()
