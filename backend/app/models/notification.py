from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import build_enum, build_json_type
from app.core.enums import (
  NotificationChannel,
  NotificationDeliveryStatus,
  NotificationMessageStatus,
  NotificationReceiptType,
)
from app.models.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class NotificationMessage(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
  __tablename__ = "notification_messages"
  __table_args__ = (
    Index("idx_notification_messages_status_scheduled_at", "status", "scheduled_at"),
    Index("idx_notification_messages_recipient_user_id", "recipient_user_id"),
    UniqueConstraint("deduplication_key", name="uq_notification_messages_dedup_key"),
  )

  source_type: Mapped[str] = mapped_column(String(64), nullable=False)
  source_id: Mapped[UUID | None] = mapped_column(nullable=True)
  recipient_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
  recipient_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
  message_type: Mapped[str] = mapped_column(String(64), nullable=False)
  deduplication_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
  title: Mapped[str] = mapped_column(String(255), nullable=False)
  body_text: Mapped[str] = mapped_column(Text, nullable=False)
  body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
  payload: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  status: Mapped[NotificationMessageStatus] = mapped_column(
    build_enum(enum_cls=NotificationMessageStatus, name="notification_message_status"),
    default=NotificationMessageStatus.QUEUED,
    nullable=False,
  )
  scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  enqueued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

  recipient_user = relationship("User", back_populates="notification_messages")
  deliveries = relationship("NotificationDelivery", back_populates="message", cascade="all, delete-orphan")
  receipts = relationship("NotificationReceipt", back_populates="message", cascade="all, delete-orphan")


class NotificationDelivery(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
  __tablename__ = "notification_deliveries"
  __table_args__ = (
    Index("idx_notification_deliveries_message_id", "message_id"),
    Index("idx_notification_deliveries_status_channel", "status", "channel"),
  )

  message_id: Mapped[UUID] = mapped_column(
    ForeignKey("notification_messages.id", ondelete="CASCADE"),
    nullable=False,
  )
  channel: Mapped[NotificationChannel] = mapped_column(
    build_enum(enum_cls=NotificationChannel, name="notification_channel"),
    nullable=False,
  )
  adapter_name: Mapped[str] = mapped_column(String(64), nullable=False)
  status: Mapped[NotificationDeliveryStatus] = mapped_column(
    build_enum(enum_cls=NotificationDeliveryStatus, name="notification_delivery_status"),
    default=NotificationDeliveryStatus.PENDING,
    nullable=False,
  )
  attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
  external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
  error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
  attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

  message = relationship("NotificationMessage", back_populates="deliveries")


class NotificationReceipt(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
  __tablename__ = "notification_receipts"
  __table_args__ = (
    UniqueConstraint("message_id", "user_id", "receipt_type", name="uq_notification_receipts_binding"),
    Index("idx_notification_receipts_user_id_created_at", "user_id", "created_at"),
  )

  message_id: Mapped[UUID] = mapped_column(
    ForeignKey(
      "notification_messages.id",
      name="fk_notification_receipts_message",
      ondelete="CASCADE",
    ),
    nullable=False,
  )
  user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_notification_receipts_user"),
    nullable=False,
  )
  receipt_type: Mapped[NotificationReceiptType] = mapped_column(
    build_enum(enum_cls=NotificationReceiptType, name="notification_receipt_type"),
    nullable=False,
  )
  note: Mapped[str | None] = mapped_column(Text, nullable=True)

  message = relationship("NotificationMessage", back_populates="receipts")
  user = relationship("User", back_populates="notification_receipts")
