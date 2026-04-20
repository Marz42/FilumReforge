from typing import Protocol

from app.models import NotificationDelivery, NotificationMessage


class NotificationAdapter(Protocol):
  async def send(
    self,
    *,
    message: NotificationMessage,
    delivery: NotificationDelivery,
  ) -> str | None: ...
