from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Task


class WorkItemWriteService:
  """Single production write port for Work Item state.

  The coordinator and capability services may request mutations here, but they
  must not assign Task ORM fields directly. Transaction ownership stays with
  the calling application command.
  """

  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  def create(self, **values: Any) -> Task:
    task = Task(**values)
    self._session.add(task)
    return task

  def update(self, task: Task, **changes: Any) -> Task:
    for field_name, value in changes.items():
      if not hasattr(Task, field_name):
        raise AttributeError(f"Task 不存在可写字段：{field_name}")
      setattr(task, field_name, value)
    return task

  def patch_metadata(self, task: Task, patch: dict[str, Any]) -> Task:
    task.extra_metadata = {**dict(task.extra_metadata or {}), **patch}
    return task
