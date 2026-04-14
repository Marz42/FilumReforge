"""phase4 workflow and messaging schema

Revision ID: 20260416_01
Revises: 20260415_01
Create Date: 2026-04-16 01:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260416_01"
down_revision = "20260415_01"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _created_at_column() -> sa.Column:
  return sa.Column(
    "created_at",
    sa.DateTime(timezone=True),
    nullable=False,
    server_default=sa.text("CURRENT_TIMESTAMP"),
  )


def _updated_at_column() -> sa.Column:
  return sa.Column(
    "updated_at",
    sa.DateTime(timezone=True),
    nullable=False,
    server_default=sa.text("CURRENT_TIMESTAMP"),
  )


def upgrade() -> None:
  workflow_definition_status = sa.Enum(
    "draft",
    "active",
    "archived",
    name="workflow_definition_status",
    native_enum=False,
  )
  workflow_step_type = sa.Enum(
    "task",
    "approval",
    "notify",
    name="workflow_step_type",
    native_enum=False,
  )
  approval_mode = sa.Enum(
    "single",
    "parallel_all",
    "parallel_any",
    name="approval_mode",
    native_enum=False,
  )
  workflow_instance_status = sa.Enum(
    "pending",
    "in_progress",
    "approved",
    "rejected",
    "returned",
    "cancelled",
    "completed",
    name="workflow_instance_status",
    native_enum=False,
  )
  workflow_step_run_status = sa.Enum(
    "pending",
    "approved",
    "rejected",
    "returned",
    "delegated",
    "skipped",
    name="workflow_step_run_status",
    native_enum=False,
  )
  notification_receipt_type = sa.Enum(
    "delivered",
    "read",
    "acknowledged",
    name="notification_receipt_type",
    native_enum=False,
  )

  op.create_table(
    "task_templates",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("code", sa.String(length=64), nullable=False),
    sa.Column("name", sa.String(length=120), nullable=False),
    sa.Column("category", sa.String(length=64), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("trigger_type", sa.String(length=32), nullable=False, server_default=sa.text("'manual'")),
    sa.Column("config", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    _created_at_column(),
    _updated_at_column(),
    sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_task_templates_created_by"),
    sa.PrimaryKeyConstraint("id", name="pk_task_templates"),
    sa.UniqueConstraint("code", name="uq_task_templates_code"),
  )
  op.create_index(
    "idx_task_templates_category_active",
    "task_templates",
    ["category", "is_active"],
    unique=False,
  )

  op.create_table(
    "task_template_steps",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("template_id", sa.Uuid(), nullable=False),
    sa.Column("step_key", sa.String(length=64), nullable=False),
    sa.Column("title", sa.String(length=255), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("step_type", sa.String(length=32), nullable=False, server_default=sa.text("'task'")),
    sa.Column("default_assignee_rule", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("default_due_offset_hours", sa.Integer(), nullable=True),
    sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("config", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    _created_at_column(),
    _updated_at_column(),
    sa.ForeignKeyConstraint(["template_id"], ["task_templates.id"], name="fk_task_template_steps_template"),
    sa.PrimaryKeyConstraint("id", name="pk_task_template_steps"),
    sa.UniqueConstraint("template_id", "step_key", name="uq_task_template_steps_template_key"),
  )
  op.create_index(
    "idx_task_template_steps_template_order",
    "task_template_steps",
    ["template_id", "sort_order"],
    unique=False,
  )

  op.create_table(
    "task_template_step_dependencies",
    sa.Column("step_id", sa.Uuid(), nullable=False),
    sa.Column("depends_on_step_id", sa.Uuid(), nullable=False),
    sa.Column("dependency_type", sa.String(length=32), nullable=False, server_default=sa.text("'blocks'")),
    _created_at_column(),
    sa.CheckConstraint("step_id <> depends_on_step_id", name="task_tpl_step_deps_not_self"),
    sa.ForeignKeyConstraint(
      ["depends_on_step_id"],
      ["task_template_steps.id"],
      name="fk_task_tpl_step_deps_depends_on",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["step_id"],
      ["task_template_steps.id"],
      name="fk_task_tpl_step_deps_step",
      ondelete="CASCADE",
    ),
    sa.PrimaryKeyConstraint("step_id", "depends_on_step_id", name="pk_task_template_step_dependencies"),
  )
  op.create_index(
    "idx_task_tpl_step_deps_depends_on",
    "task_template_step_dependencies",
    ["depends_on_step_id"],
    unique=False,
  )

  op.create_table(
    "workflow_definitions",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("code", sa.String(length=64), nullable=False),
    sa.Column("name", sa.String(length=120), nullable=False),
    sa.Column("scope_type", sa.String(length=64), nullable=False),
    sa.Column("status", workflow_definition_status, nullable=False, server_default=sa.text("'draft'")),
    sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    sa.Column("config", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    _created_at_column(),
    _updated_at_column(),
    sa.ForeignKeyConstraint(
      ["created_by"],
      ["users.id"],
      name="fk_workflow_definitions_created_by",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_workflow_definitions"),
    sa.UniqueConstraint("code", name="uq_workflow_definitions_code"),
  )
  op.create_index(
    "idx_workflow_definitions_scope_status",
    "workflow_definitions",
    ["scope_type", "status"],
    unique=False,
  )

  op.create_table(
    "workflow_steps",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("definition_id", sa.Uuid(), nullable=False),
    sa.Column("step_key", sa.String(length=64), nullable=False),
    sa.Column("name", sa.String(length=120), nullable=False),
    sa.Column("step_type", workflow_step_type, nullable=False),
    sa.Column("approval_mode", approval_mode, nullable=True),
    sa.Column("assignee_rule", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("reject_target_step_key", sa.String(length=64), nullable=True),
    sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("config", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    _created_at_column(),
    _updated_at_column(),
    sa.ForeignKeyConstraint(
      ["definition_id"],
      ["workflow_definitions.id"],
      name="fk_workflow_steps_definition",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_workflow_steps"),
    sa.UniqueConstraint("definition_id", "step_key", name="uq_workflow_steps_definition_key"),
  )
  op.create_index(
    "idx_workflow_steps_definition_order",
    "workflow_steps",
    ["definition_id", "sort_order"],
    unique=False,
  )

  op.create_table(
    "workflow_instances",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("definition_id", sa.Uuid(), nullable=False),
    sa.Column("source_type", sa.String(length=64), nullable=False),
    sa.Column("source_id", sa.Uuid(), nullable=True),
    sa.Column("initiator_user_id", sa.Uuid(), nullable=False),
    sa.Column("status", workflow_instance_status, nullable=False, server_default=sa.text("'pending'")),
    sa.Column("current_step_key", sa.String(length=64), nullable=True),
    sa.Column("payload", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column(
      "started_at",
      sa.DateTime(timezone=True),
      nullable=False,
      server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    _created_at_column(),
    _updated_at_column(),
    sa.ForeignKeyConstraint(
      ["definition_id"],
      ["workflow_definitions.id"],
      name="fk_workflow_instances_definition",
    ),
    sa.ForeignKeyConstraint(
      ["initiator_user_id"],
      ["users.id"],
      name="fk_workflow_instances_initiator",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_workflow_instances"),
  )
  op.create_index(
    "idx_workflow_instances_source",
    "workflow_instances",
    ["source_type", "source_id"],
    unique=False,
  )
  op.create_index(
    "idx_workflow_instances_status",
    "workflow_instances",
    ["status"],
    unique=False,
  )

  op.create_table(
    "workflow_step_runs",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("instance_id", sa.Uuid(), nullable=False),
    sa.Column("step_id", sa.Uuid(), nullable=False),
    sa.Column("assignee_user_id", sa.Uuid(), nullable=False),
    sa.Column("delegated_from_user_id", sa.Uuid(), nullable=True),
    sa.Column("status", workflow_step_run_status, nullable=False, server_default=sa.text("'pending'")),
    sa.Column("acted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("comment", sa.Text(), nullable=True),
    sa.Column("payload", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    _created_at_column(),
    _updated_at_column(),
    sa.ForeignKeyConstraint(
      ["assignee_user_id"],
      ["users.id"],
      name="fk_workflow_step_runs_assignee",
    ),
    sa.ForeignKeyConstraint(
      ["delegated_from_user_id"],
      ["users.id"],
      name="fk_workflow_step_runs_delegated_from",
    ),
    sa.ForeignKeyConstraint(
      ["instance_id"],
      ["workflow_instances.id"],
      name="fk_workflow_step_runs_instance",
    ),
    sa.ForeignKeyConstraint(
      ["step_id"],
      ["workflow_steps.id"],
      name="fk_workflow_step_runs_step",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_workflow_step_runs"),
  )
  op.create_index(
    "idx_workflow_step_runs_instance_status",
    "workflow_step_runs",
    ["instance_id", "status"],
    unique=False,
  )
  op.create_index(
    "idx_workflow_step_runs_assignee_status",
    "workflow_step_runs",
    ["assignee_user_id", "status"],
    unique=False,
  )

  op.create_table(
    "task_watchers",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("task_id", sa.Uuid(), nullable=False),
    sa.Column("user_id", sa.Uuid(), nullable=False),
    sa.Column("relation", sa.String(length=32), nullable=False, server_default=sa.text("'cc'")),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    _created_at_column(),
    sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_task_watchers_created_by"),
    sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name="fk_task_watchers_task", ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_task_watchers_user"),
    sa.PrimaryKeyConstraint("id", name="pk_task_watchers"),
    sa.UniqueConstraint("task_id", "user_id", "relation", name="uq_task_watchers_binding"),
  )
  op.create_index("idx_task_watchers_user_id", "task_watchers", ["user_id"], unique=False)

  op.create_table(
    "task_schedules",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("template_id", sa.Uuid(), nullable=False),
    sa.Column("owner_user_id", sa.Uuid(), nullable=False),
    sa.Column("cron_expr", sa.String(length=128), nullable=False),
    sa.Column("timezone", sa.String(length=64), nullable=False, server_default=sa.text("'UTC'")),
    sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
    sa.Column("payload", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    _created_at_column(),
    _updated_at_column(),
    sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name="fk_task_schedules_owner"),
    sa.ForeignKeyConstraint(["template_id"], ["task_templates.id"], name="fk_task_schedules_template"),
    sa.PrimaryKeyConstraint("id", name="pk_task_schedules"),
  )
  op.create_index(
    "idx_task_schedules_active_next_run",
    "task_schedules",
    ["is_active", "next_run_at"],
    unique=False,
  )
  op.create_index(
    "idx_task_schedules_owner_user_id",
    "task_schedules",
    ["owner_user_id"],
    unique=False,
  )

  op.create_table(
    "notification_receipts",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("message_id", sa.Uuid(), nullable=False),
    sa.Column("user_id", sa.Uuid(), nullable=False),
    sa.Column("receipt_type", notification_receipt_type, nullable=False),
    sa.Column("note", sa.Text(), nullable=True),
    _created_at_column(),
    sa.ForeignKeyConstraint(
      ["message_id"],
      ["notification_messages.id"],
      name="fk_notification_receipts_message",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(
      ["user_id"],
      ["users.id"],
      name="fk_notification_receipts_user",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_notification_receipts"),
    sa.UniqueConstraint(
      "message_id",
      "user_id",
      "receipt_type",
      name="uq_notification_receipts_binding",
    ),
  )
  op.create_index(
    "idx_notification_receipts_user_id_created_at",
    "notification_receipts",
    ["user_id", "created_at"],
    unique=False,
  )


def downgrade() -> None:
  op.drop_index(
    "idx_notification_receipts_user_id_created_at",
    table_name="notification_receipts",
  )
  op.drop_table("notification_receipts")
  op.drop_index("idx_task_schedules_owner_user_id", table_name="task_schedules")
  op.drop_index("idx_task_schedules_active_next_run", table_name="task_schedules")
  op.drop_table("task_schedules")
  op.drop_index("idx_task_watchers_user_id", table_name="task_watchers")
  op.drop_table("task_watchers")
  op.drop_index(
    "idx_workflow_step_runs_assignee_status",
    table_name="workflow_step_runs",
  )
  op.drop_index(
    "idx_workflow_step_runs_instance_status",
    table_name="workflow_step_runs",
  )
  op.drop_table("workflow_step_runs")
  op.drop_index("idx_workflow_instances_status", table_name="workflow_instances")
  op.drop_index("idx_workflow_instances_source", table_name="workflow_instances")
  op.drop_table("workflow_instances")
  op.drop_index("idx_workflow_steps_definition_order", table_name="workflow_steps")
  op.drop_table("workflow_steps")
  op.drop_index(
    "idx_workflow_definitions_scope_status",
    table_name="workflow_definitions",
  )
  op.drop_table("workflow_definitions")
  op.drop_index(
    "idx_task_tpl_step_deps_depends_on",
    table_name="task_template_step_dependencies",
  )
  op.drop_table("task_template_step_dependencies")
  op.drop_index(
    "idx_task_template_steps_template_order",
    table_name="task_template_steps",
  )
  op.drop_table("task_template_steps")
  op.drop_index(
    "idx_task_templates_category_active",
    table_name="task_templates",
  )
  op.drop_table("task_templates")
