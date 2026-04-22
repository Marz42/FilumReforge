from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import build_enum, build_vector_type
from app.core.enums import DocumentCategory, DocumentStatus
from app.models.base import Base
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "documents"
  __table_args__ = (
    UniqueConstraint("slug", name="uq_documents_slug"),
    Index("idx_documents_category_status", "category", "status"),
  )

  title: Mapped[str] = mapped_column(String(255), nullable=False)
  slug: Mapped[str] = mapped_column(String(255), nullable=False)
  category: Mapped[DocumentCategory] = mapped_column(
    build_enum(enum_cls=DocumentCategory, name="document_category"),
    nullable=False,
  )
  status: Mapped[DocumentStatus] = mapped_column(
    build_enum(enum_cls=DocumentStatus, name="document_status"),
    default=DocumentStatus.DRAFT,
    nullable=False,
  )
  content_md: Mapped[str] = mapped_column(Text, nullable=False)
  author_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_documents_author"),
    nullable=False,
  )
  version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
  published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

  author = relationship("User", back_populates="authored_documents")
  embeddings = relationship(
    "DocumentEmbedding",
    back_populates="document",
    cascade="all, delete-orphan",
    order_by="DocumentEmbedding.chunk_index",
  )


class DocumentEmbedding(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
  __tablename__ = "document_embeddings"
  __table_args__ = (
    UniqueConstraint("document_id", "chunk_index", name="uq_document_embeddings_chunk"),
    Index("idx_document_embeddings_doc_id", "document_id"),
    Index(
      "idx_doc_embeddings_vector",
      "embedding",
      postgresql_using="hnsw",
      postgresql_ops={"embedding": "vector_cosine_ops"},
    ),
  )

  document_id: Mapped[UUID] = mapped_column(
    ForeignKey("documents.id", name="fk_document_embeddings_doc", ondelete="CASCADE"),
    nullable=False,
  )
  chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
  chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
  token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
  embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
  embedding: Mapped[list[float]] = mapped_column(
    build_vector_type(dimensions=1536),
    nullable=False,
  )

  document = relationship("Document", back_populates="embeddings")
