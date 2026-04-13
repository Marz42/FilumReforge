from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import build_enum, build_json_type
from app.core.enums import AttachmentStatus, AttachmentTargetType, AttachmentVisibility
from app.models.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class Attachment(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
  __tablename__ = "attachments"
  __table_args__ = (
    UniqueConstraint(
      "storage_provider",
      "bucket",
      "object_key",
      name="uq_attachments_storage_object",
    ),
    Index("idx_attachments_uploader_id", "uploader_id"),
    Index("idx_attachments_status_visibility", "status", "visibility"),
  )

  storage_provider: Mapped[str] = mapped_column(String(32), nullable=False)
  bucket: Mapped[str] = mapped_column(String(128), nullable=False)
  object_key: Mapped[str] = mapped_column(String(512), nullable=False)
  original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
  mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
  size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
  checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
  uploader_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
  visibility: Mapped[AttachmentVisibility] = mapped_column(
    build_enum(enum_cls=AttachmentVisibility, name="attachment_visibility"),
    default=AttachmentVisibility.PRIVATE,
    nullable=False,
  )
  status: Mapped[AttachmentStatus] = mapped_column(
    build_enum(enum_cls=AttachmentStatus, name="attachment_status"),
    default=AttachmentStatus.UPLOADED,
    nullable=False,
  )
  extra_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", build_json_type(), default=dict, nullable=False)
  deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

  uploader = relationship("User", back_populates="uploaded_attachments")
  links = relationship("AttachmentLink", back_populates="attachment", cascade="all, delete-orphan")


class AttachmentLink(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
  __tablename__ = "attachment_links"
  __table_args__ = (
    UniqueConstraint(
      "attachment_id",
      "target_type",
      "target_id",
      "relation",
      name="uq_attachment_links_binding",
    ),
    Index("idx_attachment_links_target", "target_type", "target_id"),
  )

  attachment_id: Mapped[UUID] = mapped_column(ForeignKey("attachments.id", ondelete="CASCADE"), nullable=False)
  target_type: Mapped[AttachmentTargetType] = mapped_column(
    build_enum(enum_cls=AttachmentTargetType, name="attachment_target_type"),
    nullable=False,
  )
  target_id: Mapped[UUID] = mapped_column(nullable=False)
  relation: Mapped[str] = mapped_column(String(64), default="primary", nullable=False)
  created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

  attachment = relationship("Attachment", back_populates="links")
