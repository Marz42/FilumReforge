"""phase5 knowledge base, ai router and push schema

Revision ID: 20260417_01
Revises: 20260416_01
Create Date: 2026-04-17 01:00:00.000000
"""

from __future__ import annotations

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260417_01"
down_revision = "20260416_01"
branch_labels = None
depends_on = None

VECTOR_INDEX_NAME = "idx_doc_embeddings_vector"


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _vector_type(dimensions: int) -> sa.JSON:
  return sa.JSON().with_variant(Vector(dimensions), "postgresql")


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
  bind = op.get_bind()
  is_postgresql = bind.dialect.name == "postgresql"

  if is_postgresql:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

  push_subscription_status = sa.Enum(
    "active",
    "expired",
    "revoked",
    name="push_subscription_status",
    native_enum=False,
  )
  document_category = sa.Enum(
    "policy",
    "sop",
    "announcement",
    "faq",
    "other",
    name="document_category",
    native_enum=False,
  )
  document_status = sa.Enum(
    "draft",
    "published",
    "archived",
    name="document_status",
    native_enum=False,
  )

  op.create_table(
    "documents",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("title", sa.String(length=255), nullable=False),
    sa.Column("slug", sa.String(length=255), nullable=False),
    sa.Column("category", document_category, nullable=False),
    sa.Column("status", document_status, nullable=False, server_default=sa.text("'draft'")),
    sa.Column("content_md", sa.Text(), nullable=False),
    sa.Column("author_id", sa.Uuid(), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    _created_at_column(),
    _updated_at_column(),
    sa.ForeignKeyConstraint(["author_id"], ["users.id"], name="fk_documents_author"),
    sa.PrimaryKeyConstraint("id", name="pk_documents"),
    sa.UniqueConstraint("slug", name="uq_documents_slug"),
  )
  op.create_index(
    "idx_documents_category_status",
    "documents",
    ["category", "status"],
    unique=False,
  )

  op.create_table(
    "document_embeddings",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("document_id", sa.Uuid(), nullable=False),
    sa.Column("chunk_index", sa.Integer(), nullable=False),
    sa.Column("chunk_text", sa.Text(), nullable=False),
    sa.Column("token_count", sa.Integer(), nullable=True),
    sa.Column("embedding_model", sa.String(length=128), nullable=False),
    sa.Column("embedding", _vector_type(1536), nullable=False),
    _created_at_column(),
    sa.ForeignKeyConstraint(
      ["document_id"],
      ["documents.id"],
      name="fk_document_embeddings_doc",
      ondelete="CASCADE",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_document_embeddings"),
    sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_embeddings_chunk"),
  )
  op.create_index(
    "idx_document_embeddings_doc_id",
    "document_embeddings",
    ["document_id"],
    unique=False,
  )

  if is_postgresql:
    op.execute(
      sa.text(
        f"CREATE INDEX {VECTOR_INDEX_NAME} "
        "ON document_embeddings USING hnsw (embedding vector_cosine_ops)"
      )
    )

  op.create_table(
    "push_subscriptions",
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("user_id", sa.Uuid(), nullable=False),
    sa.Column("endpoint", sa.Text(), nullable=False),
    sa.Column("p256dh_key", sa.Text(), nullable=False),
    sa.Column("auth_key", sa.Text(), nullable=False),
    sa.Column(
      "status",
      push_subscription_status,
      nullable=False,
      server_default=sa.text("'active'"),
    ),
    sa.Column("user_agent", sa.Text(), nullable=True),
    sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    _created_at_column(),
    _updated_at_column(),
    sa.ForeignKeyConstraint(
      ["user_id"],
      ["users.id"],
      name="fk_push_subscriptions_user",
      ondelete="CASCADE",
    ),
    sa.PrimaryKeyConstraint("id", name="pk_push_subscriptions"),
    sa.UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
  )
  op.create_index(
    "idx_push_subscriptions_user_status",
    "push_subscriptions",
    ["user_id", "status"],
    unique=False,
  )


def downgrade() -> None:
  bind = op.get_bind()
  is_postgresql = bind.dialect.name == "postgresql"

  op.drop_index(
    "idx_push_subscriptions_user_status",
    table_name="push_subscriptions",
  )
  op.drop_table("push_subscriptions")

  if is_postgresql:
    op.execute(sa.text(f"DROP INDEX IF EXISTS {VECTOR_INDEX_NAME}"))

  op.drop_index(
    "idx_document_embeddings_doc_id",
    table_name="document_embeddings",
  )
  op.drop_table("document_embeddings")

  op.drop_index(
    "idx_documents_category_status",
    table_name="documents",
  )
  op.drop_table("documents")
