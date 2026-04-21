from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
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


class MessageSourceTargetRead(BaseModel):
  route_name: str | None = None
  route_query: dict[str, str] = Field(default_factory=dict)
  can_navigate: bool


class MessageSourceRead(BaseModel):
  module_key: str
  module_label: str
  object_type: str
  object_id: UUID | None = None
  object_label: str | None = None
  target: MessageSourceTargetRead


class MessageReceiptStateRead(BaseModel):
  is_read: bool
  is_acknowledged: bool
  read_at: datetime | None = None
  acknowledged_at: datetime | None = None


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
  source: MessageSourceRead
  receipt_state: MessageReceiptStateRead
  deliveries: list[NotificationDeliveryRead] = Field(default_factory=list)
  receipts: list[NotificationReceiptRead] = Field(default_factory=list)


class MessageSourceCountRead(BaseModel):
  source_type: str
  label: str
  count: int


class MessageCenterSnapshotRead(BaseModel):
  items: list[MessageRead] = Field(default_factory=list)
  total_count: int
  filtered_count: int
  unread_count: int
  unacknowledged_count: int
  source_counts: list[MessageSourceCountRead] = Field(default_factory=list)
  applied_source_type: str | None = None
  applied_state: Literal["all", "unread", "read", "unacknowledged", "acknowledged"] = "all"


class MessageReceiptCreateRequest(BaseModel):
  receipt_type: NotificationReceiptType
  note: str | None = None
