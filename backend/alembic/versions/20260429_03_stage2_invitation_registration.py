"""stage2 invitation registration

Revision ID: 20260429_03
Revises: 20260429_02
Create Date: 2026-04-29 20:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260429_03"
down_revision = "20260429_02"
branch_labels = None
depends_on = None


def _is_sqlite() -> bool:
  return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
  is_sqlite = _is_sqlite()

  if is_sqlite:
    with op.batch_alter_table("users") as batch_op:
      batch_op.add_column(sa.Column("invited_by", sa.Uuid(), nullable=True))
      batch_op.add_column(sa.Column("invitation_token_hash", sa.String(length=64), nullable=True))
      batch_op.add_column(sa.Column("invitation_sent_at", sa.DateTime(timezone=True), nullable=True))
      batch_op.add_column(sa.Column("invitation_expires_at", sa.DateTime(timezone=True), nullable=True))
      batch_op.add_column(sa.Column("invitation_revoked_at", sa.DateTime(timezone=True), nullable=True))
      batch_op.add_column(sa.Column("invitation_accepted_at", sa.DateTime(timezone=True), nullable=True))
      batch_op.create_foreign_key("fk_users_invited_by", "users", ["invited_by"], ["id"])
      batch_op.create_index("idx_users_invitation_token_hash", ["invitation_token_hash"], unique=False)
  else:
    op.add_column("users", sa.Column("invited_by", sa.Uuid(), nullable=True))
    op.add_column("users", sa.Column("invitation_token_hash", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("invitation_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("invitation_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("invitation_revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("invitation_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_users_invited_by", "users", "users", ["invited_by"], ["id"])
    op.create_index("idx_users_invitation_token_hash", "users", ["invitation_token_hash"], unique=False)


def downgrade() -> None:
  is_sqlite = _is_sqlite()

  if is_sqlite:
    with op.batch_alter_table("users") as batch_op:
      batch_op.drop_index("idx_users_invitation_token_hash")
      batch_op.drop_constraint("fk_users_invited_by", type_="foreignkey")
      batch_op.drop_column("invitation_accepted_at")
      batch_op.drop_column("invitation_revoked_at")
      batch_op.drop_column("invitation_expires_at")
      batch_op.drop_column("invitation_sent_at")
      batch_op.drop_column("invitation_token_hash")
      batch_op.drop_column("invited_by")
  else:
    op.drop_index("idx_users_invitation_token_hash", table_name="users")
    op.drop_constraint("fk_users_invited_by", "users", type_="foreignkey")
    op.drop_column("users", "invitation_accepted_at")
    op.drop_column("users", "invitation_revoked_at")
    op.drop_column("users", "invitation_expires_at")
    op.drop_column("users", "invitation_sent_at")
    op.drop_column("users", "invitation_token_hash")
    op.drop_column("users", "invited_by")