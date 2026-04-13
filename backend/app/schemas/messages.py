from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.core.enums import NotificationChannel


class NotificationMessage(BaseModel):
  source_type: str
  source_id: UUID | None = None
  recipient_user_id: UUID | None = None
  recipient_email: str | None = None
  message_type: str
  title: str
  body_text: str
  body_html: str | None = None
  channels: list[NotificationChannel] = Field(default_factory=lambda: [NotificationChannel.WEBSOCKET])
  payload: dict[str, Any] = Field(default_factory=dict)

  @model_validator(mode="after")
  def validate_recipient(self) -> "NotificationMessage":
    if self.recipient_user_id is None and self.recipient_email is None:
      raise ValueError("通知至少需要一个收件目标。")
    return self
