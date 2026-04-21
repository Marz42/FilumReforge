"""error event tracking

Revision ID: 20260421_01
Revises: 20260420_03
Create Date: 2026-04-21 10:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260421_01"
down_revision = "20260420_03"
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


def upgrade() -> None:
  op.create_table(
    "error_events",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.String(length=64), nullable=False),
    sa.Column("scope", sa.String(length=128), nullable=False),
    sa.Column("actor_user_id", sa.Uuid(), nullable=True),
    sa.Column("source_type", sa.String(length=64), nullable=True),
    sa.Column("source_id", sa.Uuid(), nullable=True),
    sa.Column("http_method", sa.String(length=16), nullable=True),
    sa.Column("path", sa.String(length=255), nullable=True),
    sa.Column("error_type", sa.String(length=255), nullable=False),
    sa.Column("error_message", sa.Text(), nullable=False),
    sa.Column("error_code", sa.String(length=64), nullable=True),
    sa.Column("stage", sa.String(length=64), nullable=True),
    sa.Column("context_json", _json_type(), nullable=False),
    _created_at_column(),
    sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name="fk_error_events_actor_user"),
    sa.PrimaryKeyConstraint("id", name="pk_error_events"),
  )
  op.create_index("idx_error_events_request_id", "error_events", ["request_id"], unique=False)
  op.create_index("idx_error_events_scope_created_at", "error_events", ["scope", "created_at"], unique=False)
  op.create_index("idx_error_events_actor_user_id", "error_events", ["actor_user_id", "created_at"], unique=False)
  op.create_index("idx_error_events_source_binding", "error_events", ["source_type", "source_id"], unique=False)


def downgrade() -> None:
  op.drop_index("idx_error_events_source_binding", table_name="error_events")
  op.drop_index("idx_error_events_actor_user_id", table_name="error_events")
  op.drop_index("idx_error_events_scope_created_at", table_name="error_events")
  op.drop_index("idx_error_events_request_id", table_name="error_events")
  op.drop_table("error_events")
