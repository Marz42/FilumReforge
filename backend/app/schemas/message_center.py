from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
  NotificationChannel,
  NotificationDeliveryStatus,
  NotificationMessageStatus,
  NotificationReceiptType,
)


class NotificationDeliveryRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  message_id: UUID
  channel: NotificationChannel
  adapter_name: str
  status: NotificationDeliveryStatus
  attempt_count: int
  external_message_id: str | None
  error_message: str | None
  attempted_at: datetime | None
  delivered_at: datetime | None
  created_at: datetime


class NotificationReceiptRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  message_id: UUID
  user_id: UUID
  receipt_type: NotificationReceiptType
  note: str | None
  created_at: datetime


class MessageRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  source_type: str
  source_id: UUID | None
  recipient_user_id: UUID | None
  recipient_email: str | None
  message_type: str
  title: str
  body_text: str
  body_html: str | None
  payload: dict[str, Any]
  status: NotificationMessageStatus
  scheduled_at: datetime | None
  enqueued_at: datetime | None
  completed_at: datetime | None
  created_at: datetime
  deliveries: list[NotificationDeliveryRead] = Field(default_factory=list)
  receipts: list[NotificationReceiptRead] = Field(default_factory=list)


class MessageReceiptCreateRequest(BaseModel):
  receipt_type: NotificationReceiptType
  note: str | None = None
