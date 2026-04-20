"""overview module schema

Revision ID: 20260420_01
Revises: 20260417_01
Create Date: 2026-04-20 10:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260420_01"
down_revision = "20260417_01"
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
  op.add_column(
    "departments",
    sa.Column(
      "capabilities",
      _json_type(),
      nullable=False,
      server_default=sa.text("'[]'"),
    ),
  )

  op.create_table(
    "board_cards",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("scope_department_id", sa.Uuid(), nullable=True),
    sa.Column("author_user_id", sa.Uuid(), nullable=False),
    sa.Column("title", sa.String(length=120), nullable=False),
    sa.Column("content_md", sa.Text(), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    _created_at_column(),
    _updated_at_column(),
    sa.ForeignKeyConstraint(
      ["scope_department_id"],
      ["departments.id"],
      name="fk_board_cards_scope_department",
    ),
    sa.ForeignKeyConstraint(
      ["author_user_id"],
      ["users.id"],
      name="fk_board_cards_author",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_board_cards"),
  )
  op.create_index(
    "idx_board_cards_scope_expires",
    "board_cards",
    ["scope_department_id", "expires_at"],
    unique=False,
  )
  op.create_index(
    "idx_board_cards_author_expires",
    "board_cards",
    ["author_user_id", "expires_at"],
    unique=False,
  )

  op.create_table(
    "board_card_archives",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("original_card_id", sa.Uuid(), nullable=False),
    sa.Column("scope_department_id", sa.Uuid(), nullable=True),
    sa.Column("author_user_id", sa.Uuid(), nullable=False),
    sa.Column("title", sa.String(length=120), nullable=False),
    sa.Column("content_md", sa.Text(), nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
    _created_at_column(),
    sa.ForeignKeyConstraint(
      ["scope_department_id"],
      ["departments.id"],
      name="fk_board_card_archives_scope_department",
    ),
    sa.ForeignKeyConstraint(
      ["author_user_id"],
      ["users.id"],
      name="fk_board_card_archives_author",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_board_card_archives"),
  )
  op.create_index(
    "idx_board_card_archives_scope",
    "board_card_archives",
    ["scope_department_id"],
    unique=False,
  )
  op.create_index(
    "idx_board_card_archives_author",
    "board_card_archives",
    ["author_user_id"],
    unique=False,
  )
  op.create_index(
    "idx_board_card_archives_archived",
    "board_card_archives",
    ["archived_at"],
    unique=False,
  )

  op.create_table(
    "announcements",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("publisher_department_id", sa.Uuid(), nullable=False),
    sa.Column("author_user_id", sa.Uuid(), nullable=False),
    sa.Column("title", sa.String(length=160), nullable=False),
    sa.Column("content_md", sa.Text(), nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    _created_at_column(),
    _updated_at_column(),
    sa.ForeignKeyConstraint(
      ["publisher_department_id"],
      ["departments.id"],
      name="fk_announcements_publisher_department",
    ),
    sa.ForeignKeyConstraint(
      ["author_user_id"],
      ["users.id"],
      name="fk_announcements_author",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_announcements"),
  )
  op.create_index(
    "idx_announcements_publisher_published",
    "announcements",
    ["publisher_department_id", "published_at"],
    unique=False,
  )

  op.create_table(
    "announcement_archives",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("original_announcement_id", sa.Uuid(), nullable=False),
    sa.Column("publisher_department_id", sa.Uuid(), nullable=False),
    sa.Column("author_user_id", sa.Uuid(), nullable=False),
    sa.Column("title", sa.String(length=160), nullable=False),
    sa.Column("content_md", sa.Text(), nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
    _created_at_column(),
    sa.ForeignKeyConstraint(
      ["publisher_department_id"],
      ["departments.id"],
      name="fk_announcement_archives_publisher_department",
    ),
    sa.ForeignKeyConstraint(
      ["author_user_id"],
      ["users.id"],
      name="fk_announcement_archives_author",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_announcement_archives"),
  )
  op.create_index(
    "idx_announcement_archives_publisher",
    "announcement_archives",
    ["publisher_department_id"],
    unique=False,
  )
  op.create_index(
    "idx_announcement_archives_archived",
    "announcement_archives",
    ["archived_at"],
    unique=False,
  )


def downgrade() -> None:
  op.drop_index(
    "idx_announcement_archives_archived",
    table_name="announcement_archives",
  )
  op.drop_index(
    "idx_announcement_archives_publisher",
    table_name="announcement_archives",
  )
  op.drop_table("announcement_archives")

  op.drop_index(
    "idx_announcements_publisher_published",
    table_name="announcements",
  )
  op.drop_table("announcements")

  op.drop_index(
    "idx_board_card_archives_archived",
    table_name="board_card_archives",
  )
  op.drop_index(
    "idx_board_card_archives_author",
    table_name="board_card_archives",
  )
  op.drop_index(
    "idx_board_card_archives_scope",
    table_name="board_card_archives",
  )
  op.drop_table("board_card_archives")

  op.drop_index(
    "idx_board_cards_author_expires",
    table_name="board_cards",
  )
  op.drop_index(
    "idx_board_cards_scope_expires",
    table_name="board_cards",
  )
  op.drop_table("board_cards")

  op.drop_column("departments", "capabilities")
