from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class BoardCard(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "board_cards"
  __table_args__ = (
    Index("idx_board_cards_scope_expires", "scope_department_id", "expires_at"),
    Index("idx_board_cards_author_expires", "author_user_id", "expires_at"),
  )

  scope_department_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("departments.id", name="fk_board_cards_scope_department"),
    nullable=True,
  )
  author_user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_board_cards_author"),
    nullable=False,
  )
  title: Mapped[str] = mapped_column(String(120), nullable=False)
  content_md: Mapped[str] = mapped_column(Text, nullable=False)
  expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

  scope_department = relationship("Department")
  author = relationship("User")


class BoardCardArchive(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
  __tablename__ = "board_card_archives"
  __table_args__ = (
    Index("idx_board_card_archives_scope", "scope_department_id"),
    Index("idx_board_card_archives_author", "author_user_id"),
    Index("idx_board_card_archives_archived", "archived_at"),
  )

  original_card_id: Mapped[UUID] = mapped_column(nullable=False)
  scope_department_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("departments.id", name="fk_board_card_archives_scope_department"),
    nullable=True,
  )
  author_user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_board_card_archives_author"),
    nullable=False,
  )
  title: Mapped[str] = mapped_column(String(120), nullable=False)
  content_md: Mapped[str] = mapped_column(Text, nullable=False)
  published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

  scope_department = relationship("Department")
  author = relationship("User")


class Announcement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "announcements"
  __table_args__ = (
    Index("idx_announcements_publisher_published", "publisher_department_id", "published_at"),
  )

  publisher_department_id: Mapped[UUID] = mapped_column(
    ForeignKey("departments.id", name="fk_announcements_publisher_department"),
    nullable=False,
  )
  author_user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_announcements_author"),
    nullable=False,
  )
  title: Mapped[str] = mapped_column(String(160), nullable=False)
  content_md: Mapped[str] = mapped_column(Text, nullable=False)
  published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

  publisher_department = relationship("Department")
  author = relationship("User")


class AnnouncementArchive(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
  __tablename__ = "announcement_archives"
  __table_args__ = (
    Index("idx_announcement_archives_publisher", "publisher_department_id"),
    Index("idx_announcement_archives_archived", "archived_at"),
  )

  original_announcement_id: Mapped[UUID] = mapped_column(nullable=False)
  publisher_department_id: Mapped[UUID] = mapped_column(
    ForeignKey("departments.id", name="fk_announcement_archives_publisher_department"),
    nullable=False,
  )
  author_user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_announcement_archives_author"),
    nullable=False,
  )
  title: Mapped[str] = mapped_column(String(160), nullable=False)
  content_md: Mapped[str] = mapped_column(Text, nullable=False)
  published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

  publisher_department = relationship("Department")
  author = relationship("User")
