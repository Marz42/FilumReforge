from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import TaskPriority, TaskSourceType, TaskStatus


class TaskRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  title: str
  description: str | None
  creator_id: UUID
  assignee_id: UUID
  department_id: UUID | None
  status: TaskStatus
  priority: TaskPriority
  due_date: datetime | None
  started_at: datetime | None
  completed_at: datetime | None
  parent_task_id: UUID | None
  source_type: TaskSourceType
  extra_metadata: dict[str, Any]
  created_at: datetime
  updated_at: datetime


class TaskCreateRequest(BaseModel):
  title: str = Field(min_length=1, max_length=255)
  assignee_id: UUID
  description: str | None = None
  department_id: UUID | None = None
  due_date: datetime | None = None
  priority: TaskPriority = TaskPriority.MEDIUM
  dependency_ids: list[UUID] = Field(default_factory=list)


class TaskUpdateRequest(BaseModel):
  title: str | None = Field(default=None, min_length=1, max_length=255)
  description: str | None = None
  assignee_id: UUID | None = None
  department_id: UUID | None = None
  due_date: datetime | None = None
  priority: TaskPriority | None = None
