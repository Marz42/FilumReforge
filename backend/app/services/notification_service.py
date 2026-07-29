from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
  NotificationChannel,
  NotificationDeliveryStatus,
  NotificationMessageStatus,
  PushSubscriptionStatus,
)
from app.core.exceptions import NotFoundError
from app.integrations.notifications.queue import NotificationQueuePublisher
from app.models import NotificationDelivery, NotificationMessage as NotificationMessageModel, PushSubscription
from app.schemas.messages import NotificationMessage
from app.services.workflow_delivery_handlers import (
  NotificationCapabilityHandler,
)
from app.services.workflow_node_handlers import WorkflowCapabilityOutcome


class NotificationService:
  def __init__(
    self,
    session: AsyncSession,
    queue_publisher: NotificationQueuePublisher | None = None,
  ) -> None:
    self._session = session
    self._queue_publisher = queue_publisher
    self._capability_handler = NotificationCapabilityHandler()

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
    commit: bool = True,
    publish: bool = True,
  ) -> NotificationMessageModel:
    if publish and not commit:
      raise ValueError("Notification publish requires committed rows.")
    self._capability_handler.resolve_policy(message.payload)
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
      if commit:
        await self._session.commit()
        await self._session.refresh(notification_message)
      else:
        await self._session.flush()

    if publish:
      await self._publish(
        notification_message=notification_message,
        deliveries=deliveries,
      )

    hydrated_message = await self._session.scalar(
      select(NotificationMessageModel)
      .options(selectinload(NotificationMessageModel.deliveries))
      .where(NotificationMessageModel.id == notification_message.id)
    )
    return hydrated_message or notification_message

  async def publish_persisted(self, *, message_id: UUID) -> NotificationMessageModel:
    notification_message = await self._session.scalar(
      select(NotificationMessageModel)
      .options(selectinload(NotificationMessageModel.deliveries))
      .where(NotificationMessageModel.id == message_id)
    )
    if notification_message is None:
      raise NotFoundError("待投递通知不存在。")
    await self._publish(
      notification_message=notification_message,
      deliveries=list(notification_message.deliveries),
    )
    return notification_message

  async def _publish(
    self,
    *,
    notification_message: NotificationMessageModel,
    deliveries: list[NotificationDelivery],
  ) -> None:
    if self._queue_publisher is None:
      return
    notification_message_id = notification_message.id
    payload = {
      "message_id": str(notification_message_id),
      "delivery_ids": [str(delivery.id) for delivery in deliveries],
      "source_type": notification_message.source_type,
      "message_type": notification_message.message_type,
    }
    if notification_message.status == NotificationMessageStatus.FAILED:
      retry_result = self._capability_handler.retry(
        delivery_statuses=[delivery.status for delivery in deliveries],
      )
      if "retry_failed_deliveries" in retry_result.side_effects:
        notification_message.status = NotificationMessageStatus.QUEUED
        notification_message.completed_at = None
        for delivery in deliveries:
          if delivery.status == NotificationDeliveryStatus.FAILED:
            delivery.status = NotificationDeliveryStatus.RETRYING
            delivery.error_message = None
      # Persist retryability before publishing so the consumer never observes stale FAILED rows.
      await self._session.commit()
      refreshed_message = await self._session.scalar(
        select(NotificationMessageModel)
        .execution_options(populate_existing=True)
        .options(selectinload(NotificationMessageModel.deliveries))
        .where(NotificationMessageModel.id == notification_message_id)
      )
      if refreshed_message is None:  # pragma: no cover - guarded by the loaded identity
        raise NotFoundError("待重试通知不存在。")
      notification_message = refreshed_message
      deliveries = list(refreshed_message.deliveries)
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
      return

    completion_result = self._capability_handler.evaluate(
      policy=self._capability_handler.resolve_policy(notification_message.payload),
      enqueued=True,
      delivery_statuses=[delivery.status for delivery in deliveries],
    )
    if completion_result.outcome == WorkflowCapabilityOutcome.SUCCEEDED:
      notification_message.status = NotificationMessageStatus.COMPLETED
      notification_message.completed_at = datetime.now(UTC)
      await self._session.commit()
      await self._session.refresh(notification_message)
