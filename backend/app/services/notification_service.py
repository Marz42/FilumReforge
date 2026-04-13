from app.schemas.messages import NotificationMessage


class NotificationService:
  async def send(self, message: NotificationMessage) -> None:
    raise NotImplementedError(
      f"Redis-backed notification dispatch is scheduled for Phase 1. message_type={message.message_type}"
    )
