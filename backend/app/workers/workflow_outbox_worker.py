"""workflow_outbox_worker.py — ARQ worker 任务：扫描并投递 workflow_outbox_events。

处理逻辑：
1. 扫描 status=PENDING 且 available_at <= now 的事件（批次上限 50 条）。
2. 将事件状态标记为 RETRYING，独立提交，避免长事务。
3. 调用 NotificationService 发送通知。
4. 成功 → status=DISPATCHED，dispatched_at=now。
5. 失败 → attempt_count++，last_error=..., 未超上限则退回 RETRYING + 指数退避 available_at，
         超过 MAX_ATTEMPTS 则标记 FAILED（可人工干预或后续 dead-letter 处理）。
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.enums import (
  DEFAULT_USER_NOTIFICATION_CHANNELS,
  WorkflowOutboxEventStatus,
)
from app.models.workflow_graph import WorkflowOutboxEvent
from app.schemas.messages import NotificationMessage
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
BATCH_SIZE = 50


def _backoff_seconds(attempt: int) -> int:
  """指数退避：30s、60s、120s、240s、…"""
  return 30 * (2 ** max(attempt - 1, 0))


async def _dispatch_event(
  *,
  event: WorkflowOutboxEvent,
  session: AsyncSession,
  notification_service: NotificationService,
) -> None:
  """根据 event_type 发送对应通知。不抛出异常；失败写入 last_error。"""
  payload: dict[str, Any] = event.payload or {}
  now = datetime.now(UTC)

  try:
    if event.event_type == "workflow_node_taken_over":
      recipient_user_id = payload.get("recipient_user_id")
      recipient_email = payload.get("recipient_email")
      if not recipient_user_id or not recipient_email:
        raise ValueError("outbox payload 缺少 recipient_user_id / recipient_email")

      await notification_service.send(
        NotificationMessage(
          source_type="workflow_graph",
          source_id=UUID(str(event.instance_id)),
          recipient_user_id=UUID(str(recipient_user_id)),
          recipient_email=str(recipient_email),
          message_type="workflow_node_taken_over",
          title=str(payload.get("title", "节点已被管理员接管")),
          body_text=str(payload.get("body_text", "")),
          channels=list(DEFAULT_USER_NOTIFICATION_CHANNELS),
          payload={
            k: v
            for k, v in payload.items()
            if k not in {"recipient_user_id", "recipient_email", "title", "body_text"}
          },
        )
      )
    elif event.event_type == "workflow_node_activated":
      recipient_user_id = payload.get("recipient_user_id")
      recipient_email = payload.get("recipient_email")
      if not recipient_user_id or not recipient_email:
        raise ValueError("outbox payload 缺少 recipient_user_id / recipient_email")

      await notification_service.send(
        NotificationMessage(
          source_type="workflow_graph",
          source_id=UUID(str(event.instance_id)),
          recipient_user_id=UUID(str(recipient_user_id)),
          recipient_email=str(recipient_email),
          message_type="workflow_node_activated",
          title=str(payload.get("title", "您有待处理的工作流节点")),
          body_text=str(payload.get("body_text", "")),
          channels=list(DEFAULT_USER_NOTIFICATION_CHANNELS),
          payload={
            k: v
            for k, v in payload.items()
            if k not in {"recipient_user_id", "recipient_email", "title", "body_text"}
          },
        )
      )
    else:
      logger.warning("未知的 outbox event_type=%s，跳过", event.event_type)

    event.status = WorkflowOutboxEventStatus.DISPATCHED
    event.dispatched_at = now
    event.last_error = None
  except Exception as exc:  # noqa: BLE001
    attempt = event.attempt_count
    event.last_error = str(exc)[:1024]
    if attempt >= MAX_ATTEMPTS:
      event.status = WorkflowOutboxEventStatus.FAILED
      logger.error(
        "outbox event %s 超过最大重试次数 (%d)，标记为 FAILED。last_error=%s",
        event.id,
        MAX_ATTEMPTS,
        event.last_error,
      )
    else:
      event.status = WorkflowOutboxEventStatus.RETRYING
      event.available_at = now + timedelta(seconds=_backoff_seconds(attempt))
      logger.warning(
        "outbox event %s 投递失败（attempt=%d），退避 %ds 后重试。error=%s",
        event.id,
        attempt,
        _backoff_seconds(attempt),
        event.last_error,
      )

  await session.flush()


async def process_workflow_outbox_events(
  session_factory: async_sessionmaker[AsyncSession],
  queue_publisher: object,
) -> int:
  """扫描并投递一批 PENDING/RETRYING 的 workflow outbox 事件，返回处理数量。

  该函数被 ARQ worker 以定时任务方式调用；session_factory 从 ctx 传入。
  每个事件独立使用一个 session（防止单条失败影响整批）。
  """
  now = datetime.now(UTC)
  dispatched = 0

  # 第一步：查询待处理事件 IDs（只读事务）
  async with session_factory() as session:
    pending_ids: list[UUID] = list(
      await session.scalars(
        select(WorkflowOutboxEvent.id)
        .where(
          and_(
            WorkflowOutboxEvent.status.in_(
              [WorkflowOutboxEventStatus.PENDING, WorkflowOutboxEventStatus.RETRYING]
            ),
            (WorkflowOutboxEvent.available_at == None) | (WorkflowOutboxEvent.available_at <= now),  # noqa: E711
          )
        )
        .order_by(WorkflowOutboxEvent.created_at.asc())
        .limit(BATCH_SIZE)
      )
    )

  if not pending_ids:
    return 0

  # 第二步：逐条在独立 session 中处理，避免单条错误回滚整批
  for event_id in pending_ids:
    async with session_factory() as session:
      event: WorkflowOutboxEvent | None = await session.scalar(
        select(WorkflowOutboxEvent)
        .where(WorkflowOutboxEvent.id == event_id)
        .with_for_update(skip_locked=True)
      )
      if event is None:
        # 已被另一个 worker 实例处理
        continue
      if event.status not in (
        WorkflowOutboxEventStatus.PENDING,
        WorkflowOutboxEventStatus.RETRYING,
      ):
        continue

      # 先递增 attempt_count（在同一 session 中）
      event.attempt_count += 1
      await session.flush()

      # notification_service.send() 内部会 commit；_dispatch_event 结束后再 commit 一次
      notification_service = NotificationService(session, queue_publisher)  # type: ignore[arg-type]
      await _dispatch_event(
        event=event,
        session=session,
        notification_service=notification_service,
      )
      await session.commit()
      dispatched += 1

  return dispatched
