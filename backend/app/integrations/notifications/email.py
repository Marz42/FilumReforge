from __future__ import annotations

from app.models import NotificationDelivery, NotificationMessage


class EmailNotificationAdapter:
  async def send(
    self,
    *,
    message: NotificationMessage,
    delivery: NotificationDelivery,
  ) -> str:
    return f"email:{message.id}:{delivery.id}"
