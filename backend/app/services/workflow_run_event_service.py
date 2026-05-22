"""Persisted workflow run event log (W8)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models import WorkflowGraphInstance, WorkflowRunEvent
from app.schemas.workflow_video import WorkflowRunEventListResponse, WorkflowRunEventRead


class WorkflowRunEventService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def append(
    self,
    *,
    instance_id: UUID,
    event_type: str,
    actor_user_id: UUID | None,
    payload: dict[str, Any] | None = None,
  ) -> WorkflowRunEvent:
    instance = await self._session.get(WorkflowGraphInstance, instance_id)
    if instance is None:
      raise NotFoundError("图实例不存在。")

    event = WorkflowRunEvent(
      instance_id=instance_id,
      event_type=event_type,
      actor_user_id=actor_user_id,
      payload=dict(payload or {}),
    )
    self._session.add(event)
    await self._session.flush()
    return event

  async def list_for_instance(
    self,
    *,
    instance_id: UUID,
    limit: int = 20,
    offset: int = 0,
  ) -> WorkflowRunEventListResponse:
    instance = await self._session.get(WorkflowGraphInstance, instance_id)
    if instance is None:
      raise NotFoundError("图实例不存在。")

    normalized_limit = max(1, min(limit, 100))
    normalized_offset = max(0, offset)

    total = await self._session.scalar(
      select(func.count())
      .select_from(WorkflowRunEvent)
      .where(WorkflowRunEvent.instance_id == instance_id)
    )
    rows = list(
      await self._session.scalars(
        select(WorkflowRunEvent)
        .where(WorkflowRunEvent.instance_id == instance_id)
        .order_by(WorkflowRunEvent.created_at.desc())
        .offset(normalized_offset)
        .limit(normalized_limit)
      )
    )
    return WorkflowRunEventListResponse(
      instance_id=instance_id,
      items=[WorkflowRunEventRead.model_validate(row) for row in rows],
      total=int(total or 0),
      limit=normalized_limit,
      offset=normalized_offset,
    )
