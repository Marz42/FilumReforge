"""phase1 foundation schema

Revision ID: 20260413_01
Revises:
Create Date: 2026-04-13 18:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260413_01"
down_revision = None
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
  user_role = sa.Enum("admin", "hr", "employee", name="user_role", native_enum=False)
  user_status = sa.Enum(
    "active",
    "inactive",
    "suspended",
    "offboarded",
    name="user_status",
    native_enum=False,
  )
  task_status = sa.Enum("todo", "doing", "review", "done", name="task_status", native_enum=False)
  task_priority = sa.Enum("low", "medium", "high", "urgent", name="task_priority", native_enum=False)
  task_source_type = sa.Enum(
    "manual",
    "template",
    "event",
    "ai",
    name="task_source_type",
    native_enum=False,
  )
  attachment_visibility = sa.Enum(
    "private",
    "internal",
    "public",
    name="attachment_visibility",
    native_enum=False,
  )
  attachment_status = sa.Enum(
    "uploaded",
    "deleted",
    "quarantined",
    name="attachment_status",
    native_enum=False,
  )
  attachment_target_type = sa.Enum(
    "task_comment",
    "task",
    "profile",
    "document",
    name="attachment_target_type",
    native_enum=False,
  )
  notification_channel = sa.Enum(
    "email",
    "web_push",
    "websocket",
    name="notification_channel",
    native_enum=False,
  )
  notification_message_status = sa.Enum(
    "queued",
    "processing",
    "completed",
    "failed",
    name="notification_message_status",
    native_enum=False,
  )
  notification_delivery_status = sa.Enum(
    "pending",
    "sent",
    "failed",
    "retrying",
    name="notification_delivery_status",
    native_enum=False,
  )

  op.create_table(
    "users",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("email", sa.String(length=255), nullable=False),
    sa.Column("password_hash", sa.String(length=255), nullable=False),
    sa.Column("role", user_role, nullable=False),
    sa.Column("status", user_status, nullable=False, server_default=sa.text("'active'")),
    sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    _created_at_column(),
    _updated_at_column(),
    sa.PrimaryKeyConstraint("id", name="pk_users"),
    sa.UniqueConstraint("email", name="uq_users_email"),
  )
  op.create_index("idx_users_role_status", "users", ["role", "status"], unique=False)

  op.create_table(
    "departments",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("name", sa.String(length=120), nullable=False),
    sa.Column("code", sa.String(length=64), nullable=False),
    sa.Column("parent_id", sa.Uuid(), nullable=True),
    sa.Column("manager_id", sa.Uuid(), nullable=True),
    sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
    _created_at_column(),
    _updated_at_column(),
    sa.ForeignKeyConstraint(["manager_id"], ["users.id"], name="fk_departments_manager_id_users"),
    sa.ForeignKeyConstraint(["parent_id"], ["departments.id"], name="fk_departments_parent_id_departments"),
    sa.PrimaryKeyConstraint("id", name="pk_departments"),
    sa.UniqueConstraint("code", name="uq_departments_code"),
    sa.UniqueConstraint("parent_id", "name", name="uq_departments_parent_name"),
  )
  op.create_index("idx_departments_parent_id", "departments", ["parent_id"], unique=False)

  op.create_table(
    "profiles",
    sa.Column("user_id", sa.Uuid(), nullable=False),
    sa.Column("employee_no", sa.String(length=64), nullable=False),
    sa.Column("real_name", sa.String(length=120), nullable=False),
    sa.Column("department_id", sa.Uuid(), nullable=False),
    sa.Column("job_title", sa.String(length=120), nullable=True),
    sa.Column("phone", sa.String(length=32), nullable=True),
    sa.Column("hire_date", sa.Date(), nullable=True),
    sa.Column("custom_fields", _json_type(), nullable=False),
    _created_at_column(),
    _updated_at_column(),
    sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_profiles_department_id_departments"),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_profiles_user_id_users", ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("user_id", name="pk_profiles"),
    sa.UniqueConstraint("employee_no", name="uq_profiles_employee_no"),
  )
  op.create_index("idx_profiles_department_id", "profiles", ["department_id"], unique=False)
  op.create_index(
    "idx_profiles_custom_fields_gin",
    "profiles",
    ["custom_fields"],
    unique=False,
    postgresql_using="gin",
  )

  op.create_table(
    "refresh_tokens",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("user_id", sa.Uuid(), nullable=False),
    sa.Column("token_id", sa.String(length=64), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    _created_at_column(),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_refresh_tokens_user_id_users", ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
    sa.UniqueConstraint("token_id", name="uq_refresh_tokens_token_id"),
  )
  op.create_index("idx_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False)

  op.create_table(
    "attachments",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("storage_provider", sa.String(length=32), nullable=False),
    sa.Column("bucket", sa.String(length=128), nullable=False),
    sa.Column("object_key", sa.String(length=512), nullable=False),
    sa.Column("original_filename", sa.String(length=255), nullable=False),
    sa.Column("mime_type", sa.String(length=127), nullable=False),
    sa.Column("size_bytes", sa.BigInteger(), nullable=False),
    sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
    sa.Column("uploader_id", sa.Uuid(), nullable=False),
    sa.Column(
      "visibility",
      attachment_visibility,
      nullable=False,
      server_default=sa.text("'private'"),
    ),
    sa.Column("status", attachment_status, nullable=False, server_default=sa.text("'uploaded'")),
    sa.Column("metadata", _json_type(), nullable=False),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    _created_at_column(),
    sa.ForeignKeyConstraint(["uploader_id"], ["users.id"], name="fk_attachments_uploader_id_users"),
    sa.PrimaryKeyConstraint("id", name="pk_attachments"),
    sa.UniqueConstraint(
      "storage_provider",
      "bucket",
      "object_key",
      name="uq_attachments_storage_object",
    ),
  )
  op.create_index("idx_attachments_uploader_id", "attachments", ["uploader_id"], unique=False)
  op.create_index(
    "idx_attachments_status_visibility",
    "attachments",
    ["status", "visibility"],
    unique=False,
  )

  op.create_table(
    "tasks",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("title", sa.String(length=255), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("creator_id", sa.Uuid(), nullable=False),
    sa.Column("assignee_id", sa.Uuid(), nullable=False),
    sa.Column("department_id", sa.Uuid(), nullable=True),
    sa.Column("status", task_status, nullable=False, server_default=sa.text("'todo'")),
    sa.Column("priority", task_priority, nullable=False, server_default=sa.text("'medium'")),
    sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("parent_task_id", sa.Uuid(), nullable=True),
    sa.Column("source_type", task_source_type, nullable=False, server_default=sa.text("'manual'")),
    sa.Column("metadata", _json_type(), nullable=False),
    _created_at_column(),
    _updated_at_column(),
    sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], name="fk_tasks_assignee_id_users"),
    sa.ForeignKeyConstraint(["creator_id"], ["users.id"], name="fk_tasks_creator_id_users"),
    sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_tasks_department_id_departments"),
    sa.ForeignKeyConstraint(["parent_task_id"], ["tasks.id"], name="fk_tasks_parent_task_id_tasks"),
    sa.PrimaryKeyConstraint("id", name="pk_tasks"),
  )
  op.create_index("idx_tasks_assignee_status", "tasks", ["assignee_id", "status"], unique=False)
  op.create_index("idx_tasks_department_status", "tasks", ["department_id", "status"], unique=False)
  op.create_index("idx_tasks_due_date", "tasks", ["due_date"], unique=False)

  op.create_table(
    "task_dependencies",
    sa.Column("task_id", sa.Uuid(), nullable=False),
    sa.Column("depends_on_task_id", sa.Uuid(), nullable=False),
    sa.Column("dependency_type", sa.String(length=32), nullable=False, server_default=sa.text("'blocks'")),
    _created_at_column(),
    sa.CheckConstraint("task_id <> depends_on_task_id", name="task_dependencies_self_reference"),
    sa.ForeignKeyConstraint(["depends_on_task_id"], ["tasks.id"], name="fk_task_dependencies_depends_on_task_id_tasks", ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name="fk_task_dependencies_task_id_tasks", ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("task_id", "depends_on_task_id", name="pk_task_dependencies"),
  )
  op.create_index(
    "idx_task_dependencies_depends_on_task_id",
    "task_dependencies",
    ["depends_on_task_id"],
    unique=False,
  )

  op.create_table(
    "attachment_links",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("attachment_id", sa.Uuid(), nullable=False),
    sa.Column("target_type", attachment_target_type, nullable=False),
    sa.Column("target_id", sa.Uuid(), nullable=False),
    sa.Column("relation", sa.String(length=64), nullable=False, server_default=sa.text("'primary'")),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    _created_at_column(),
    sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"], name="fk_attachment_links_attachment_id_attachments", ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_attachment_links_created_by_users"),
    sa.PrimaryKeyConstraint("id", name="pk_attachment_links"),
    sa.UniqueConstraint(
      "attachment_id",
      "target_type",
      "target_id",
      "relation",
      name="uq_attachment_links_binding",
    ),
  )
  op.create_index(
    "idx_attachment_links_target",
    "attachment_links",
    ["target_type", "target_id"],
    unique=False,
  )

  op.create_table(
    "notification_messages",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("source_type", sa.String(length=64), nullable=False),
    sa.Column("source_id", sa.Uuid(), nullable=True),
    sa.Column("recipient_user_id", sa.Uuid(), nullable=True),
    sa.Column("recipient_email", sa.String(length=255), nullable=True),
    sa.Column("message_type", sa.String(length=64), nullable=False),
    sa.Column("title", sa.String(length=255), nullable=False),
    sa.Column("body_text", sa.Text(), nullable=False),
    sa.Column("body_html", sa.Text(), nullable=True),
    sa.Column("payload", _json_type(), nullable=False),
    sa.Column(
      "status",
      notification_message_status,
      nullable=False,
      server_default=sa.text("'queued'"),
    ),
    sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    _created_at_column(),
    sa.ForeignKeyConstraint(
      ["recipient_user_id"],
      ["users.id"],
      name="fk_notification_messages_recipient_user_id_users",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_notification_messages"),
  )
  op.create_index(
    "idx_notification_messages_status_scheduled_at",
    "notification_messages",
    ["status", "scheduled_at"],
    unique=False,
  )
  op.create_index(
    "idx_notification_messages_recipient_user_id",
    "notification_messages",
    ["recipient_user_id"],
    unique=False,
  )

  op.create_table(
    "notification_deliveries",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("message_id", sa.Uuid(), nullable=False),
    sa.Column("channel", notification_channel, nullable=False),
    sa.Column("adapter_name", sa.String(length=64), nullable=False),
    sa.Column(
      "status",
      notification_delivery_status,
      nullable=False,
      server_default=sa.text("'pending'"),
    ),
    sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("external_message_id", sa.String(length=255), nullable=True),
    sa.Column("error_message", sa.Text(), nullable=True),
    sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    _created_at_column(),
    sa.ForeignKeyConstraint(
      ["message_id"],
      ["notification_messages.id"],
      name="fk_notification_deliveries_message_id_notification_messages",
      ondelete="CASCADE",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_notification_deliveries"),
  )
  op.create_index(
    "idx_notification_deliveries_message_id",
    "notification_deliveries",
    ["message_id"],
    unique=False,
  )
  op.create_index(
    "idx_notification_deliveries_status_channel",
    "notification_deliveries",
    ["status", "channel"],
    unique=False,
  )


def downgrade() -> None:
  op.drop_index("idx_notification_deliveries_status_channel", table_name="notification_deliveries")
  op.drop_index("idx_notification_deliveries_message_id", table_name="notification_deliveries")
  op.drop_table("notification_deliveries")

  op.drop_index("idx_notification_messages_recipient_user_id", table_name="notification_messages")
  op.drop_index("idx_notification_messages_status_scheduled_at", table_name="notification_messages")
  op.drop_table("notification_messages")

  op.drop_index("idx_attachment_links_target", table_name="attachment_links")
  op.drop_table("attachment_links")

  op.drop_index("idx_task_dependencies_depends_on_task_id", table_name="task_dependencies")
  op.drop_table("task_dependencies")

  op.drop_index("idx_tasks_due_date", table_name="tasks")
  op.drop_index("idx_tasks_department_status", table_name="tasks")
  op.drop_index("idx_tasks_assignee_status", table_name="tasks")
  op.drop_table("tasks")

  op.drop_index("idx_attachments_status_visibility", table_name="attachments")
  op.drop_index("idx_attachments_uploader_id", table_name="attachments")
  op.drop_table("attachments")

  op.drop_index("idx_refresh_tokens_user_id", table_name="refresh_tokens")
  op.drop_table("refresh_tokens")

  op.drop_index("idx_profiles_custom_fields_gin", table_name="profiles")
  op.drop_index("idx_profiles_department_id", table_name="profiles")
  op.drop_table("profiles")

  op.drop_index("idx_departments_parent_id", table_name="departments")
  op.drop_table("departments")

  op.drop_index("idx_users_role_status", table_name="users")
  op.drop_table("users")
