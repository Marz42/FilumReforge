from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
  NotificationChannel,
  NotificationDeliveryStatus,
  NotificationMessageStatus,
  PushSubscriptionStatus,
)
from app.integrations.notifications.queue import NotificationQueuePublisher
from app.models import NotificationDelivery, NotificationMessage as NotificationMessageModel, PushSubscription
from app.schemas.messages import NotificationMessage


class NotificationService:
  def __init__(
    self,
    session: AsyncSession,
    queue_publisher: NotificationQueuePublisher | None = None,
  ) -> None:
    self._session = session
    self._queue_publisher = queue_publisher

  async def _resolve_channels(self, *, message: NotificationMessage) -> list[NotificationChannel]:
    channels = list(dict.fromkeys(message.channels))
    if (
      message.recipient_user_id is None
      or NotificationChannel.WEB_PUSH not in channels
    ):
      return channels

    active_subscription = await self._session.scalar(
      select(PushSubscription.id).where(
        PushSubscription.user_id == message.recipient_user_id,
        PushSubscription.status == PushSubscriptionStatus.ACTIVE,
      )
    )
    if active_subscription is None:
      return [
        channel
        for channel in channels
        if channel != NotificationChannel.WEB_PUSH
      ]
    return channels

  async def send(
    self,
    message: NotificationMessage,
    *,
    deduplication_key: str | None = None,
  ) -> NotificationMessageModel:
    notification_message = None
    deliveries: list[NotificationDelivery] = []
    if deduplication_key:
      notification_message = await self._session.scalar(
        select(NotificationMessageModel)
        .options(selectinload(NotificationMessageModel.deliveries))
        .where(NotificationMessageModel.deduplication_key == deduplication_key)
      )
      if notification_message is not None:
        deliveries = list(notification_message.deliveries)

    if notification_message is None:
      channels = await self._resolve_channels(message=message)
      notification_message = NotificationMessageModel(
        source_type=message.source_type,
        source_id=message.source_id,
        recipient_user_id=message.recipient_user_id,
        recipient_email=message.recipient_email,
        message_type=message.message_type,
        deduplication_key=deduplication_key,
        title=message.title,
        body_text=message.body_text,
        body_html=message.body_html,
        payload=message.payload,
        enqueued_at=datetime.now(UTC),
      )
      self._session.add(notification_message)
      await self._session.flush()

      for channel in channels:
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
      payload = {
        "message_id": str(notification_message.id),
        "delivery_ids": [str(delivery.id) for delivery in deliveries],
        "source_type": notification_message.source_type,
        "message_type": notification_message.message_type,
      }
      if notification_message.status == NotificationMessageStatus.FAILED:
        notification_message.status = NotificationMessageStatus.QUEUED
        notification_message.completed_at = None
        for delivery in deliveries:
          if delivery.status == NotificationDeliveryStatus.FAILED:
            delivery.status = NotificationDeliveryStatus.PENDING
            delivery.error_message = None
        # Persist retryability before publishing so the consumer never observes stale FAILED rows.
        await self._session.commit()
      try:
        await self._queue_publisher.publish(payload)
      except Exception as exc:  # noqa: BLE001
        failure_time = datetime.now(UTC)
        error_message = f"通知入队失败：{exc}"
        notification_message.status = NotificationMessageStatus.FAILED
        notification_message.completed_at = failure_time
        for delivery in deliveries:
          delivery.status = NotificationDeliveryStatus.FAILED
          delivery.attempt_count += 1
          delivery.attempted_at = failure_time
          delivery.error_message = error_message
        await self._session.commit()
        await self._session.refresh(notification_message)

    hydrated_message = await self._session.scalar(
      select(NotificationMessageModel)
      .options(selectinload(NotificationMessageModel.deliveries))
      .where(NotificationMessageModel.id == notification_message.id)
    )
    return hydrated_message or notification_message
