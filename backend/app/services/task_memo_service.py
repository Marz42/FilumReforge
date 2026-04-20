from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models import TaskMemo, User
from app.services.access_control import ensure_active_user
from app.services.task_service import TaskService

UNSET: Final = object()


class TaskMemoService:
  def __init__(
    self,
    session: AsyncSession,
    task_service: TaskService,
  ) -> None:
    self._session = session
    self._task_service = task_service

  def _statement(self):
    return select(TaskMemo).options(selectinload(TaskMemo.related_task))

  async def _get_memo_or_raise(self, *, actor: User, memo_id: UUID) -> TaskMemo:
    memo = await self._session.scalar(
      self._statement().where(TaskMemo.id == memo_id, TaskMemo.owner_user_id == actor.id)
    )
    if memo is None:
      raise NotFoundError("备忘不存在。")
    return memo

  async def _validate_related_task(self, *, actor: User, related_task_id: UUID | None) -> None:
    if related_task_id is None:
      return
    await self._task_service.get_task(actor=actor, task_id=related_task_id)

  async def list_memos(self, *, actor: User) -> list[TaskMemo]:
    ensure_active_user(actor)
    return list(
      await self._session.scalars(
        self._statement()
        .where(TaskMemo.owner_user_id == actor.id)
        .order_by(TaskMemo.is_pinned.desc(), TaskMemo.updated_at.desc(), TaskMemo.created_at.desc())
      )
    )

  async def create_memo(
    self,
    *,
    actor: User,
    content: str,
    related_task_id: UUID | None = None,
    is_pinned: bool = False,
  ) -> TaskMemo:
    ensure_active_user(actor)
    await self._validate_related_task(actor=actor, related_task_id=related_task_id)
    memo = TaskMemo(
      owner_user_id=actor.id,
      related_task_id=related_task_id,
      content=content.strip(),
      is_pinned=is_pinned,
    )
    self._session.add(memo)
    await self._session.commit()
    return await self._get_memo_or_raise(actor=actor, memo_id=memo.id)

  async def update_memo(
    self,
    *,
    actor: User,
    memo_id: UUID,
    content: str | None = None,
    related_task_id=UNSET,  # noqa: ANN001
    is_pinned: bool | None = None,
  ) -> TaskMemo:
    ensure_active_user(actor)
    memo = await self._get_memo_or_raise(actor=actor, memo_id=memo_id)
    if content is not None:
      memo.content = content.strip()
    if related_task_id is not UNSET:
      await self._validate_related_task(actor=actor, related_task_id=related_task_id)
      memo.related_task_id = related_task_id
    if is_pinned is not None:
      memo.is_pinned = is_pinned
    await self._session.commit()
    return await self._get_memo_or_raise(actor=actor, memo_id=memo_id)

  async def delete_memo(
    self,
    *,
    actor: User,
    memo_id: UUID,
  ) -> None:
    ensure_active_user(actor)
    memo = await self._get_memo_or_raise(actor=actor, memo_id=memo_id)
    await self._session.delete(memo)
    await self._session.commit()
