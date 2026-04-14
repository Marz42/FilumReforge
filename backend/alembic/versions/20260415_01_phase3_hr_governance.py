"""phase3 hr governance schema

Revision ID: 20260415_01
Revises: 20260414_01
Create Date: 2026-04-15 15:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260415_01"
down_revision = "20260414_01"
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
  position_assignment_type = sa.Enum(
    "primary",
    "part_time",
    "acting",
    name="position_assignment_type",
    native_enum=False,
  )
  reporting_line_type = sa.Enum(
    "solid",
    "dotted",
    name="reporting_line_type",
    native_enum=False,
  )
  employment_event_type = sa.Enum(
    "onboard",
    "transfer",
    "promotion",
    "reward",
    "discipline",
    "offboard",
    "rehire",
    name="employment_event_type",
    native_enum=False,
  )
  delegation_scope_type = sa.Enum(
    "approval",
    "task",
    "data_access",
    "all",
    name="delegation_scope_type",
    native_enum=False,
  )
  delegation_status = sa.Enum(
    "pending",
    "active",
    "expired",
    "revoked",
    name="delegation_status",
    native_enum=False,
  )

  op.create_table(
    "positions",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("code", sa.String(length=64), nullable=False),
    sa.Column("name", sa.String(length=120), nullable=False),
    sa.Column("level", sa.String(length=64), nullable=True),
    sa.Column("metadata", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
    _created_at_column(),
    _updated_at_column(),
    sa.PrimaryKeyConstraint("id", name="pk_positions"),
    sa.UniqueConstraint("code", name="uq_positions_code"),
  )
  op.create_index("idx_positions_is_active", "positions", ["is_active"], unique=False)

  op.create_table(
    "profile_field_definitions",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("field_key", sa.String(length=64), nullable=False),
    sa.Column("label", sa.String(length=120), nullable=False),
    sa.Column("field_type", sa.String(length=32), nullable=False),
    sa.Column("storage_target", sa.String(length=32), nullable=False),
    sa.Column("is_sensitive", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    sa.Column("config", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
    _created_at_column(),
    _updated_at_column(),
    sa.PrimaryKeyConstraint("id", name="pk_profile_field_definitions"),
    sa.UniqueConstraint("field_key", name="uq_profile_field_definitions_field_key"),
  )
  op.create_index(
    "idx_profile_field_definitions_is_active",
    "profile_field_definitions",
    ["is_active"],
    unique=False,
  )

  op.create_table(
    "profile_positions",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("user_id", sa.Uuid(), nullable=False),
    sa.Column("position_id", sa.Uuid(), nullable=False),
    sa.Column("department_id", sa.Uuid(), nullable=False),
    sa.Column(
      "assignment_type",
      position_assignment_type,
      nullable=False,
      server_default=sa.text("'primary'"),
    ),
    sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    sa.Column("starts_at", sa.Date(), nullable=False),
    sa.Column("ends_at", sa.Date(), nullable=True),
    _created_at_column(),
    _updated_at_column(),
    sa.CheckConstraint("ends_at IS NULL OR ends_at >= starts_at", name="profile_positions_valid_period"),
    sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_profile_positions_department_id_departments"),
    sa.ForeignKeyConstraint(["position_id"], ["positions.id"], name="fk_profile_positions_position_id_positions"),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_profile_positions_user_id_users"),
    sa.PrimaryKeyConstraint("id", name="pk_profile_positions"),
    sa.UniqueConstraint(
      "user_id",
      "position_id",
      "department_id",
      "starts_at",
      name="uq_profile_positions_assignment",
    ),
  )
  op.create_index("idx_profile_positions_user_id", "profile_positions", ["user_id"], unique=False)
  op.create_index("idx_profile_positions_department_id", "profile_positions", ["department_id"], unique=False)
  op.create_index(
    "idx_profile_positions_is_primary",
    "profile_positions",
    ["user_id", "is_primary"],
    unique=False,
  )

  op.create_table(
    "reporting_lines",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("user_id", sa.Uuid(), nullable=False),
    sa.Column("manager_user_id", sa.Uuid(), nullable=False),
    sa.Column("department_id", sa.Uuid(), nullable=True),
    sa.Column("line_type", reporting_line_type, nullable=False),
    sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    sa.Column("starts_at", sa.Date(), nullable=False),
    sa.Column("ends_at", sa.Date(), nullable=True),
    _created_at_column(),
    _updated_at_column(),
    sa.CheckConstraint("user_id <> manager_user_id", name="reporting_lines_not_self"),
    sa.CheckConstraint("ends_at IS NULL OR ends_at >= starts_at", name="reporting_lines_valid_period"),
    sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_reporting_lines_department_id_departments"),
    sa.ForeignKeyConstraint(["manager_user_id"], ["users.id"], name="fk_reporting_lines_manager_user_id_users"),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_reporting_lines_user_id_users"),
    sa.PrimaryKeyConstraint("id", name="pk_reporting_lines"),
    sa.UniqueConstraint(
      "user_id",
      "manager_user_id",
      "line_type",
      "department_id",
      "starts_at",
      name="uq_reporting_lines_relation",
    ),
  )
  op.create_index("idx_reporting_lines_user_id", "reporting_lines", ["user_id"], unique=False)
  op.create_index(
    "idx_reporting_lines_manager_user_id",
    "reporting_lines",
    ["manager_user_id"],
    unique=False,
  )

  op.create_table(
    "profile_field_permissions",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("field_definition_id", sa.Uuid(), nullable=False),
    sa.Column("subject_type", sa.String(length=32), nullable=False),
    sa.Column("subject_value", sa.String(length=64), nullable=True),
    sa.Column("can_view", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    sa.Column("can_edit", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    sa.Column("scope_filters", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100")),
    _created_at_column(),
    _updated_at_column(),
    sa.ForeignKeyConstraint(
      ["field_definition_id"],
      ["profile_field_definitions.id"],
      name="fk_profile_field_permissions_field_definition_id_profile_field_definitions",
      ondelete="CASCADE",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_profile_field_permissions"),
  )
  op.create_index(
    "idx_profile_field_permissions_definition",
    "profile_field_permissions",
    ["field_definition_id"],
    unique=False,
  )
  op.create_index(
    "idx_profile_field_permissions_priority",
    "profile_field_permissions",
    ["priority"],
    unique=False,
  )

  op.create_table(
    "employment_events",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("user_id", sa.Uuid(), nullable=False),
    sa.Column("event_type", employment_event_type, nullable=False),
    sa.Column("effective_date", sa.Date(), nullable=False),
    sa.Column("title", sa.String(length=255), nullable=False),
    sa.Column("summary", sa.Text(), nullable=True),
    sa.Column("payload", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    _created_at_column(),
    sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_employment_events_created_by_users"),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_employment_events_user_id_users"),
    sa.PrimaryKeyConstraint("id", name="pk_employment_events"),
  )
  op.create_index(
    "idx_employment_events_user_id_date",
    "employment_events",
    ["user_id", "effective_date"],
    unique=False,
  )
  op.create_index("idx_employment_events_type", "employment_events", ["event_type"], unique=False)

  op.create_table(
    "delegations",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("delegator_user_id", sa.Uuid(), nullable=False),
    sa.Column("delegate_user_id", sa.Uuid(), nullable=False),
    sa.Column(
      "scope_type",
      delegation_scope_type,
      nullable=False,
      server_default=sa.text("'data_access'"),
    ),
    sa.Column("scope_department_id", sa.Uuid(), nullable=True),
    sa.Column("scope_filters", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column(
      "status",
      delegation_status,
      nullable=False,
      server_default=sa.text("'pending'"),
    ),
    sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    _created_at_column(),
    _updated_at_column(),
    sa.CheckConstraint("delegator_user_id <> delegate_user_id", name="delegations_not_self"),
    sa.CheckConstraint("ends_at > starts_at", name="delegations_valid_window"),
    sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_delegations_created_by_users"),
    sa.ForeignKeyConstraint(["delegate_user_id"], ["users.id"], name="fk_delegations_delegate_user_id_users"),
    sa.ForeignKeyConstraint(["delegator_user_id"], ["users.id"], name="fk_delegations_delegator_user_id_users"),
    sa.ForeignKeyConstraint(
      ["scope_department_id"],
      ["departments.id"],
      name="fk_delegations_scope_department_id_departments",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_delegations"),
  )
  op.create_index(
    "idx_delegations_delegator_status",
    "delegations",
    ["delegator_user_id", "status"],
    unique=False,
  )
  op.create_index(
    "idx_delegations_delegate_status",
    "delegations",
    ["delegate_user_id", "status"],
    unique=False,
  )


def downgrade() -> None:
  op.drop_index("idx_delegations_delegate_status", table_name="delegations")
  op.drop_index("idx_delegations_delegator_status", table_name="delegations")
  op.drop_table("delegations")

  op.drop_index("idx_employment_events_type", table_name="employment_events")
  op.drop_index("idx_employment_events_user_id_date", table_name="employment_events")
  op.drop_table("employment_events")

  op.drop_index("idx_profile_field_permissions_priority", table_name="profile_field_permissions")
  op.drop_index("idx_profile_field_permissions_definition", table_name="profile_field_permissions")
  op.drop_table("profile_field_permissions")

  op.drop_index("idx_reporting_lines_manager_user_id", table_name="reporting_lines")
  op.drop_index("idx_reporting_lines_user_id", table_name="reporting_lines")
  op.drop_table("reporting_lines")

  op.drop_index("idx_profile_positions_is_primary", table_name="profile_positions")
  op.drop_index("idx_profile_positions_department_id", table_name="profile_positions")
  op.drop_index("idx_profile_positions_user_id", table_name="profile_positions")
  op.drop_table("profile_positions")

  op.drop_index("idx_profile_field_definitions_is_active", table_name="profile_field_definitions")
  op.drop_table("profile_field_definitions")

  op.drop_index("idx_positions_is_active", table_name="positions")
  op.drop_table("positions")
