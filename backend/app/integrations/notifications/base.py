from dataclasses import dataclass
from typing import Protocol

from app.models import NotificationDelivery, NotificationMessage


@dataclass(frozen=True)
class NotificationSendResult:
  external_message_id: str
  warning: str | None = None


class NotificationAdapter(Protocol):
  async def send(
    self,
    *,
    message: NotificationMessage,
    delivery: NotificationDelivery,
  ) -> str | NotificationSendResult | None: ...
