"""report center support

Revision ID: 20260420_03
Revises: 20260420_02
Create Date: 2026-04-20 16:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260420_03"
down_revision = "20260420_02"
branch_labels = None
depends_on = None


REPORT_DIRECTION_ENUM = sa.Enum(
  "upward",
  "downward",
  name="report_direction",
  native_enum=False,
  create_constraint=True,
)
REPORT_STATUS_ENUM = sa.Enum(
  "in_progress",
  "completed",
  "returned",
  "archived",
  name="report_status",
  native_enum=False,
  create_constraint=True,
)
REPORT_ROUTE_STATUS_ENUM = sa.Enum(
  "queued",
  "pending",
  "forwarded",
  "completed",
  "returned",
  name="report_route_status",
  native_enum=False,
  create_constraint=True,
)


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
  op.create_table(
    "reports",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("direction", REPORT_DIRECTION_ENUM, nullable=False),
    sa.Column(
      "status",
      REPORT_STATUS_ENUM,
      nullable=False,
      server_default=sa.text("'in_progress'"),
    ),
    sa.Column("title", sa.String(length=255), nullable=False),
    sa.Column("content_md", sa.Text(), nullable=False),
    sa.Column("initiator_user_id", sa.Uuid(), nullable=False),
    sa.Column("target_user_id", sa.Uuid(), nullable=False),
    sa.Column("current_recipient_user_id", sa.Uuid(), nullable=True),
    sa.Column("current_route_sequence", sa.Integer(), nullable=True),
    sa.Column("workflow_definition_id", sa.Uuid(), nullable=True),
    sa.Column("workflow_instance_id", sa.Uuid(), nullable=True),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    _created_at_column(),
    _updated_at_column(),
    sa.ForeignKeyConstraint(["initiator_user_id"], ["users.id"], name="fk_reports_initiator"),
    sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], name="fk_reports_target"),
    sa.ForeignKeyConstraint(
      ["current_recipient_user_id"],
      ["users.id"],
      name="fk_reports_current_recipient",
    ),
    sa.ForeignKeyConstraint(
      ["workflow_definition_id"],
      ["workflow_definitions.id"],
      name="fk_reports_workflow_definition",
    ),
    sa.ForeignKeyConstraint(
      ["workflow_instance_id"],
      ["workflow_instances.id"],
      name="fk_reports_workflow_instance",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_reports"),
  )
  op.create_index(
    "idx_reports_initiator_status",
    "reports",
    ["initiator_user_id", "status"],
    unique=False,
  )
  op.create_index(
    "idx_reports_current_recipient",
    "reports",
    ["current_recipient_user_id", "status"],
    unique=False,
  )
  op.create_index(
    "idx_reports_target_status",
    "reports",
    ["target_user_id", "status"],
    unique=False,
  )

  op.create_table(
    "report_routes",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("report_id", sa.Uuid(), nullable=False),
    sa.Column("sequence_no", sa.Integer(), nullable=False),
    sa.Column("sender_user_id", sa.Uuid(), nullable=False),
    sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
    sa.Column("assigned_user_id", sa.Uuid(), nullable=True),
    sa.Column(
      "status",
      REPORT_ROUTE_STATUS_ENUM,
      nullable=False,
      server_default=sa.text("'queued'"),
    ),
    sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("acted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("note", sa.Text(), nullable=True),
    _created_at_column(),
    _updated_at_column(),
    sa.ForeignKeyConstraint(
      ["report_id"],
      ["reports.id"],
      name="fk_report_routes_report",
      ondelete="CASCADE",
    ),
    sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], name="fk_report_routes_sender"),
    sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], name="fk_report_routes_recipient"),
    sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], name="fk_report_routes_assigned"),
    sa.PrimaryKeyConstraint("id", name="pk_report_routes"),
    sa.UniqueConstraint("report_id", "sequence_no", name="uq_report_routes_sequence"),
  )
  op.create_index(
    "idx_report_routes_assigned_status",
    "report_routes",
    ["assigned_user_id", "status"],
    unique=False,
  )
  op.create_index(
    "idx_report_routes_report_status",
    "report_routes",
    ["report_id", "status"],
    unique=False,
  )


def downgrade() -> None:
  op.drop_index("idx_report_routes_report_status", table_name="report_routes")
  op.drop_index("idx_report_routes_assigned_status", table_name="report_routes")
  op.drop_table("report_routes")
  op.drop_index("idx_reports_target_status", table_name="reports")
  op.drop_index("idx_reports_current_recipient", table_name="reports")
  op.drop_index("idx_reports_initiator_status", table_name="reports")
  op.drop_table("reports")
