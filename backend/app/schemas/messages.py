from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationMessage(BaseModel):
  source_type: str
  source_id: UUID | None = None
  recipient_user_id: UUID | None = None
  recipient_email: str | None = None
  message_type: str
  title: str
  body_text: str
  body_html: str | None = None
  payload: dict[str, Any] = Field(default_factory=dict)
