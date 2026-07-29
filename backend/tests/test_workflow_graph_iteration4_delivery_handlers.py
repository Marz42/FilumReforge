from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.enums import (
  NotificationChannel,
  NotificationDeliveryStatus,
  NotificationMessageStatus,
  UserRole,
  UserStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.models import NotificationDelivery, User
from app.schemas.messages import NotificationMessage
from app.services.notification_service import NotificationService
from app.services.workflow_delivery_handlers import (
  DeliverableCapabilityHandler,
  NotificationCapabilityHandler,
  NotificationCompletionPolicy,
)
from app.services.workflow_node_handlers import (
  WorkflowCapabilityOperationError,
  WorkflowCapabilityOutcome,
)
from app.workers.jobs import process_notification_message_payload


class _RecordingQueuePublisher:
  def __init__(self) -> None:
    self.payloads: list[dict[str, object]] = []

  async def publish(self, payload: dict[str, object]) -> None:
    self.payloads.append(payload)


class _FailingQueuePublisher:
  async def publish(self, payload: dict[str, object]) -> None:
    del payload
    raise RuntimeError("queue unavailable")


def test_i4_deliverable_handler_versions_reviews_and_preserves_accepted_snapshot() -> None:
  handler = DeliverableCapabilityHandler()
  first_submitter = "user-a"
  second_submitter = "user-b"
  reviewer = "reviewer"
  legacy_payload = {
    "latest_submission": {
      "submitted_at": "2026-07-29T08:00:00+00:00",
      "submitted_by_user_id": first_submitter,
      "summary": "legacy v1",
      "attachment_ids": [],
    },
    "submission_history": [
      {
        "submitted_at": "2026-07-29T08:00:00+00:00",
        "submitted_by_user_id": first_submitter,
        "summary": "legacy v1",
        "attachment_ids": [],
      }
    ],
  }

  submitted = handler.submit(
    payload=legacy_payload,
    submitted_by_user_id=second_submitter,
    submitted_at=datetime(2026, 7, 30, 1, tzinfo=UTC),
    summary="v2",
    attachment_ids=["attachment-2"],
    signature_prefix="task:demo",
    current_signature="task:demo:submission:1",
  )
  submitted_payload = dict(submitted.result["deliverable_payload"])
  returned = handler.review(
    payload=submitted_payload,
    reviewed_by_user_id=reviewer,
    reviewed_at=datetime(2026, 7, 30, 2, tzinfo=UTC),
    approve=False,
    comment="revise",
    rework_count=1,
  )
  resubmitted = handler.submit(
    payload=dict(returned.result["deliverable_payload"]),
    submitted_by_user_id=first_submitter,
    submitted_at=datetime(2026, 7, 30, 3, tzinfo=UTC),
    summary="v3",
    attachment_ids=[],
    signature_prefix="task:demo",
    current_signature="task:demo:submission:2",
  )
  accepted = handler.review(
    payload=dict(resubmitted.result["deliverable_payload"]),
    reviewed_by_user_id=reviewer,
    reviewed_at=datetime(2026, 7, 30, 4, tzinfo=UTC),
    approve=True,
    comment="accepted",
    quality_score=5,
  )
  accepted_payload = dict(accepted.result["deliverable_payload"])

  assert submitted.outcome == WorkflowCapabilityOutcome.WAITING
  assert submitted_payload["submission_history"][0]["version"] == 1
  assert submitted_payload["submission_history"][0]["signature"] == "task:demo:submission:1"
  assert returned.business_state == WorkflowNodeBusinessState.RETURNED_FOR_REWORK
  assert accepted.outcome == WorkflowCapabilityOutcome.SUCCEEDED
  assert accepted_payload["current_submission_version"] == 3
  assert accepted_payload["accepted_submission_version"] == 3
  assert accepted_payload["accepted_submission_signature"] == "task:demo:submission:3"
  assert accepted_payload["accepted_submission"]["summary"] == "v3"
  assert [review["submission_version"] for review in accepted_payload["review_history"]] == [2, 3]


def test_i4_deliverable_and_notification_failure_retry_cancel_are_capability_results() -> None:
  deliverable_handler = DeliverableCapabilityHandler()
  failed = deliverable_handler.fail(payload={"schema_version": 2}, code="storage_unavailable")
  retried = deliverable_handler.retry(payload=failed.result["deliverable_payload"])
  cancelled = deliverable_handler.cancel(payload=retried.result["deliverable_payload"])

  assert failed.outcome == WorkflowCapabilityOutcome.FAILED
  assert failed.engine_state == WorkflowNodeEngineState.FAILED
  assert retried.outcome == WorkflowCapabilityOutcome.WAITING
  assert cancelled.outcome == WorkflowCapabilityOutcome.CANCELLED
  assert cancelled.side_effects == ("preserve_deliverable_history",)

  notification_handler = NotificationCapabilityHandler()
  notification_failed = notification_handler.evaluate(
    policy=NotificationCompletionPolicy.ALL_CHANNELS_SUCCESS,
    enqueued=True,
    delivery_statuses=[NotificationDeliveryStatus.SENT, NotificationDeliveryStatus.FAILED],
  )
  notification_retry = notification_handler.retry(
    delivery_statuses=[NotificationDeliveryStatus.SENT, NotificationDeliveryStatus.FAILED],
  )
  notification_cancel = notification_handler.cancel()

  assert notification_failed.outcome == WorkflowCapabilityOutcome.FAILED
  assert notification_retry.side_effects == ("retry_failed_deliveries",)
  assert notification_cancel.side_effects == ("cancel_pending_deliveries",)
  with pytest.raises(WorkflowCapabilityOperationError, match="只有失败投递"):
    notification_handler.retry(delivery_statuses=[NotificationDeliveryStatus.PENDING])


def test_i4_notification_completion_policies_are_explicit() -> None:
  handler = NotificationCapabilityHandler()
  statuses = [NotificationDeliveryStatus.SENT, NotificationDeliveryStatus.PENDING]

  queued = handler.evaluate(
    policy=NotificationCompletionPolicy.QUEUED,
    enqueued=True,
    delivery_statuses=statuses,
  )
  sent = handler.evaluate(
    policy=NotificationCompletionPolicy.SENT,
    enqueued=True,
    delivery_statuses=statuses,
  )
  all_channels = handler.evaluate(
    policy=NotificationCompletionPolicy.ALL_CHANNELS_SUCCESS,
    enqueued=True,
    delivery_statuses=statuses,
  )

  assert queued.outcome == WorkflowCapabilityOutcome.SUCCEEDED
  assert sent.outcome == WorkflowCapabilityOutcome.SUCCEEDED
  assert all_channels.outcome == WorkflowCapabilityOutcome.WAITING
  assert all_channels.diagnostics["delivery_counts"] == {
    "pending": 1,
    "sent": 1,
    "failed": 0,
    "retrying": 0,
  }


@pytest.mark.asyncio
async def test_i4_notification_worker_requires_all_message_channels_not_payload_subset(
  db_session,
) -> None:  # noqa: ANN001
  recipient = User(
    email="iteration4-notification@example.com",
    password_hash="test",
    role=UserRole.EMPLOYEE,
    status=UserStatus.ACTIVE,
  )
  db_session.add(recipient)
  await db_session.commit()
  queue = _RecordingQueuePublisher()
  message = await NotificationService(db_session, queue).send(
    NotificationMessage(
      source_type="workflow",
      source_id=recipient.id,
      recipient_user_id=recipient.id,
      recipient_email=recipient.email,
      message_type="iteration4_delivery_policy",
      title="Iteration 4-D",
      body_text="all channels must finish",
      channels=[NotificationChannel.EMAIL, NotificationChannel.WEBSOCKET],
    )
  )
  deliveries = list(
    await db_session.scalars(
      select(NotificationDelivery)
      .where(NotificationDelivery.message_id == message.id)
      .order_by(NotificationDelivery.channel.asc())
    )
  )
  assert len(deliveries) == 2
  message_id = message.id
  delivery_ids = [delivery.id for delivery in deliveries]

  first = await process_notification_message_payload(
    session=db_session,
    payload={"message_id": str(message_id), "delivery_ids": [str(delivery_ids[0])]},
  )
  assert first is not None
  assert first.status == NotificationMessageStatus.QUEUED

  second = await process_notification_message_payload(
    session=db_session,
    payload={"message_id": str(message_id), "delivery_ids": [str(delivery_ids[1])]},
  )
  assert second is not None
  assert second.status == NotificationMessageStatus.COMPLETED


@pytest.mark.asyncio
async def test_i4_notification_queued_policy_completes_after_publish(db_session) -> None:  # noqa: ANN001
  recipient = User(
    email="iteration4-queued@example.com",
    password_hash="test",
    role=UserRole.EMPLOYEE,
    status=UserStatus.ACTIVE,
  )
  db_session.add(recipient)
  await db_session.commit()
  queue = _RecordingQueuePublisher()
  message = await NotificationService(db_session, queue).send(
    NotificationMessage(
      source_type="workflow",
      source_id=recipient.id,
      recipient_user_id=recipient.id,
      recipient_email=recipient.email,
      message_type="iteration4_queued_policy",
      title="Iteration 4-D queued",
      body_text="queue acceptance completes this capability",
      channels=[NotificationChannel.EMAIL],
      payload={"completion_policy": NotificationCompletionPolicy.QUEUED.value},
    )
  )

  assert len(queue.payloads) == 1
  assert message.status == NotificationMessageStatus.COMPLETED
  assert message.completed_at is not None


@pytest.mark.asyncio
async def test_i4_notification_retry_uses_capability_result_and_requeues_failed_deliveries(
  db_session,
) -> None:  # noqa: ANN001
  recipient = User(
    email="iteration4-retry@example.com",
    password_hash="test",
    role=UserRole.EMPLOYEE,
    status=UserStatus.ACTIVE,
  )
  db_session.add(recipient)
  await db_session.commit()
  failed_message = await NotificationService(db_session, _FailingQueuePublisher()).send(
    NotificationMessage(
      source_type="workflow",
      source_id=recipient.id,
      recipient_user_id=recipient.id,
      recipient_email=recipient.email,
      message_type="iteration4_retry",
      title="Iteration 4-D retry",
      body_text="retry failed delivery",
      channels=[NotificationChannel.EMAIL],
    )
  )
  message_id = failed_message.id
  assert failed_message.status == NotificationMessageStatus.FAILED

  queue = _RecordingQueuePublisher()
  retried_message = await NotificationService(db_session, queue).publish_persisted(
    message_id=message_id,
  )
  deliveries = list(
    await db_session.scalars(
      select(NotificationDelivery).where(NotificationDelivery.message_id == message_id)
    )
  )

  assert len(queue.payloads) == 1
  assert retried_message.status == NotificationMessageStatus.QUEUED
  assert [delivery.status for delivery in deliveries] == [NotificationDeliveryStatus.RETRYING]
