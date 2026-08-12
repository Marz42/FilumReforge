"""Iteration 5-C expand: privacy-safe projection shadow evidence.

Revision ID: 20260812_03
Revises: 20260812_02
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260812_03"
down_revision = "20260812_02"
branch_labels = None
depends_on = None


_REVISION_TABLES = (
  "task_center_items",
  "process_run_summaries",
  "node_timeline_entries",
)


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _is_sqlite() -> bool:
  return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
  if not _is_sqlite():
    for table_name in _REVISION_TABLES:
      op.alter_column(
        table_name,
        "source_revision",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
      )
    op.alter_column(
      "projection_checkpoints",
      "processed_count",
      existing_type=sa.Integer(),
      type_=sa.BigInteger(),
      existing_nullable=False,
    )

  op.create_table(
    "projection_shadow_observations",
    sa.Column("scan_id", sa.Uuid(), nullable=False),
    sa.Column("comparison_name", sa.String(length=64), nullable=False),
    sa.Column("subject_type", sa.String(length=32), nullable=False),
    sa.Column("subject_id", sa.Uuid(), nullable=False),
    sa.Column("sample_mode", sa.String(length=16), nullable=False),
    sa.Column("outcome", sa.String(length=32), nullable=False),
    sa.Column("severity", sa.String(length=16), nullable=False),
    sa.Column("mismatch_fields", _json_type(), nullable=False),
    sa.Column("expected_fingerprint", sa.String(length=64), nullable=False),
    sa.Column("actual_fingerprint", sa.String(length=64), nullable=True),
    sa.Column("expected_source_revision", sa.BigInteger(), nullable=True),
    sa.Column("actual_source_revision", sa.BigInteger(), nullable=True),
    sa.Column("lag_ms", sa.BigInteger(), nullable=True),
    sa.Column("details", _json_type(), nullable=False),
    sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint(
      "sample_mode in ('recent', 'full')",
      name=op.f("projection_shadow_sample_mode_chk"),
    ),
    sa.CheckConstraint(
      "outcome in ('match', 'difference', 'missing_projection', 'lagging', "
      "'orphan_projection', 'error')",
      name=op.f("projection_shadow_outcome_chk"),
    ),
    sa.CheckConstraint(
      "severity in ('info', 'warning', 'error', 'critical')",
      name=op.f("projection_shadow_severity_chk"),
    ),
    sa.CheckConstraint(
      "lag_ms IS NULL OR lag_ms >= 0",
      name=op.f("projection_shadow_lag_chk"),
    ),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint(
      "scan_id",
      "comparison_name",
      "subject_type",
      "subject_id",
      name=op.f("uq_projection_shadow_scan_subject"),
    ),
  )
  op.create_index(
    "idx_projection_shadow_scan_outcome",
    "projection_shadow_observations",
    ["scan_id", "outcome"],
  )
  op.create_index(
    "idx_projection_shadow_subject",
    "projection_shadow_observations",
    ["subject_type", "subject_id", "created_at"],
  )
  op.create_index(
    "idx_projection_shadow_severity",
    "projection_shadow_observations",
    ["severity", "created_at"],
  )
  op.create_index(
    "idx_projection_shadow_created_at",
    "projection_shadow_observations",
    ["created_at"],
  )


def downgrade() -> None:
  op.drop_index("idx_projection_shadow_created_at", table_name="projection_shadow_observations")
  op.drop_index("idx_projection_shadow_severity", table_name="projection_shadow_observations")
  op.drop_index("idx_projection_shadow_subject", table_name="projection_shadow_observations")
  op.drop_index(
    "idx_projection_shadow_scan_outcome",
    table_name="projection_shadow_observations",
  )
  op.drop_table("projection_shadow_observations")

  if not _is_sqlite():
    # Projection rows are reconstructible; clearing them avoids unsafe BIGINT→INTEGER casts.
    for table_name in _REVISION_TABLES:
      op.execute(sa.text(f'DELETE FROM "{table_name}"'))
      op.alter_column(
        table_name,
        "source_revision",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="source_revision::integer",
      )
    op.execute(
      sa.text(
        'UPDATE "projection_checkpoints" '
        "SET processed_count = 0, cursor_occurred_at = NULL, cursor_source_id = NULL, "
        "status = 'idle', last_error = NULL"
      )
    )
    op.alter_column(
      "projection_checkpoints",
      "processed_count",
      existing_type=sa.BigInteger(),
      type_=sa.Integer(),
      existing_nullable=False,
      postgresql_using="processed_count::integer",
    )
