from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import NotificationMessageStatus, PushSubscriptionStatus


class PushSubscriptionCreateRequest(BaseModel):
  endpoint: str = Field(min_length=1, max_length=4000)
  p256dh_key: str = Field(min_length=1, max_length=1024)
  auth_key: str = Field(min_length=1, max_length=1024)
  user_agent: str | None = Field(default=None, max_length=1024)


class PushSubscriptionRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  user_id: UUID
  endpoint: str
  status: PushSubscriptionStatus
  user_agent: str | None
  last_seen_at: datetime | None
  created_at: datetime
  updated_at: datetime


class PushSubscriptionConfigRead(BaseModel):
  public_key: str | None
  is_enabled: bool


class PushTestNotificationRead(BaseModel):
  message_id: UUID
  status: NotificationMessageStatus
  detail: str
