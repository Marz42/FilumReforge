from typing import Protocol

from app.schemas.messages import NotificationMessage


class NotificationAdapter(Protocol):
  async def send(self, message: NotificationMessage) -> None: ...
