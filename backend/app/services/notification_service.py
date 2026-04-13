from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.notifications.queue import NotificationQueuePublisher
from app.models import NotificationDelivery, NotificationMessage as NotificationMessageModel
from app.schemas.messages import NotificationMessage


class NotificationService:
  def __init__(
    self,
    session: AsyncSession,
    queue_publisher: NotificationQueuePublisher | None = None,
  ) -> None:
    self._session = session
    self._queue_publisher = queue_publisher

  async def send(self, message: NotificationMessage) -> NotificationMessageModel:
    notification_message = NotificationMessageModel(
      source_type=message.source_type,
      source_id=message.source_id,
      recipient_user_id=message.recipient_user_id,
      recipient_email=message.recipient_email,
      message_type=message.message_type,
      title=message.title,
      body_text=message.body_text,
      body_html=message.body_html,
      payload=message.payload,
      enqueued_at=datetime.now(UTC),
    )
    self._session.add(notification_message)
    await self._session.flush()

    deliveries: list[NotificationDelivery] = []
    for channel in message.channels:
      delivery = NotificationDelivery(
        message_id=notification_message.id,
        channel=channel,
        adapter_name=channel.value,
      )
      deliveries.append(delivery)
    self._session.add_all(deliveries)
    await self._session.commit()
    await self._session.refresh(notification_message)

    if self._queue_publisher is not None:
      await self._queue_publisher.publish(
        {
          "message_id": str(notification_message.id),
          "delivery_ids": [str(delivery.id) for delivery in deliveries],
          "source_type": notification_message.source_type,
          "message_type": notification_message.message_type,
        }
      )

    return notification_message
