from __future__ import annotations

from app.models import NotificationDelivery, NotificationMessage


class WebSocketNotificationAdapter:
  async def send(
    self,
    *,
    message: NotificationMessage,
    delivery: NotificationDelivery,
  ) -> str:
    return f"websocket:{message.id}:{delivery.id}"
