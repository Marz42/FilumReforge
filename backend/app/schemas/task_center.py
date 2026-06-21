from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import TaskPriority, TaskSourceType, TaskStatus


class TaskCenterTemplateSummaryRead(BaseModel):
  id: UUID
  name: str
  category: str
  is_active: bool
  step_count: int


class TaskCenterDepartmentOptionRead(BaseModel):
  id: UUID
  label: str


class TaskCenterUserOptionRead(BaseModel):
  user_id: UUID
  email: str
  real_name: str | None
  department_id: UUID | None
  department_name: str | None
  label: str


class TaskCenterInboxItemRead(BaseModel):
  task_id: UUID
  title: str
  priority: TaskPriority
  status: TaskStatus
  due_date: datetime | None
  department_name: str | None
  current_stage_label: str
  current_handler_label: str | None
  run_label: str | None = None
  user_facing_state: str | None = None


class TaskCenterTrackingItemRead(BaseModel):
  task_id: UUID
  title: str
  priority: TaskPriority
  status: TaskStatus
  due_date: datetime | None
  department_name: str | None
  relation_types: list[str] = Field(default_factory=list)
  current_stage_label: str
  current_handler_label: str | None
  latest_deliverable_submitted_at: datetime | None = None
  rework_count: int = 0
  review_quality_score: int | None = None
  is_pending_review: bool = False
  run_label: str | None = None
  user_facing_state: str | None = None


class TaskCenterHistoryItemRead(BaseModel):
  task_id: UUID
  title: str
  priority: TaskPriority
  due_date: datetime | None
  completed_at: datetime | None
  department_name: str | None
  relation_types: list[str] = Field(default_factory=list)
  source_type: TaskSourceType
  run_label: str | None = None
  user_facing_state: str | None = None


class TaskCenterTaskReferenceRead(BaseModel):
  id: UUID
  title: str
  status: TaskStatus
  priority: TaskPriority
  due_date: datetime | None


class TaskMemoRead(BaseModel):
  id: UUID
  owner_user_id: UUID
  related_task_id: UUID | None
  title: str | None
  content: str
  is_pinned: bool
  created_at: datetime
  updated_at: datetime
  related_task: TaskCenterTaskReferenceRead | None = None


class TaskMemoCreateRequest(BaseModel):
  title: str | None = Field(default=None, max_length=200)
  content: str = Field(min_length=1, max_length=4000)
  related_task_id: UUID | None = None
  is_pinned: bool = False


class TaskMemoUpdateRequest(BaseModel):
  title: str | None = Field(default=None, max_length=200)
  content: str | None = Field(default=None, min_length=1, max_length=4000)
  related_task_id: UUID | None = None
  is_pinned: bool | None = None


class TaskCenterPermissionsRead(BaseModel):
  can_manage_templates: bool
  can_publish_task: bool


class TaskCenterRead(BaseModel):
  permissions: TaskCenterPermissionsRead
  template_summaries: list[TaskCenterTemplateSummaryRead] = Field(default_factory=list)
  publish_department_options: list[TaskCenterDepartmentOptionRead] = Field(default_factory=list)
  publish_user_options: list[TaskCenterUserOptionRead] = Field(default_factory=list)
  task_inbox: list[TaskCenterInboxItemRead] = Field(default_factory=list)
  task_tracking: list[TaskCenterTrackingItemRead] = Field(default_factory=list)
  task_history: list[TaskCenterHistoryItemRead] = Field(default_factory=list)
  task_memos: list[TaskMemoRead] = Field(default_factory=list)
