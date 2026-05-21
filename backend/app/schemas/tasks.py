from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import CommentFormat, TaskActionType, TaskPriority, TaskSourceType, TaskStatus
from app.schemas.attachments import AttachmentRead


class TaskSearchResultRead(BaseModel):
  id: UUID
  title: str
  description: str | None
  status: TaskStatus
  priority: TaskPriority
  department_id: UUID | None
  department_name: str | None = None
  assignee_id: UUID
  updated_at: datetime


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


class TaskWatcherRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  task_id: UUID
  user_id: UUID
  relation: str
  created_by: UUID
  created_at: datetime


class TaskWatcherBatchRequest(BaseModel):
  user_ids: list[UUID] = Field(default_factory=list)


class TaskCreateRequest(BaseModel):
  title: str = Field(min_length=1, max_length=255)
  assignee_id: UUID
  description: str | None = None
  department_id: UUID | None = None
  due_date: datetime | None = None
  priority: TaskPriority = TaskPriority.MEDIUM
  dependency_ids: list[UUID] = Field(default_factory=list)
  attachment_ids: list[UUID] = Field(default_factory=list, max_length=10)


class TaskUpdateRequest(BaseModel):
  title: str | None = Field(default=None, min_length=1, max_length=255)
  description: str | None = None
  assignee_id: UUID | None = None
  department_id: UUID | None = None
  due_date: datetime | None = None
  priority: TaskPriority | None = None


class TaskStatusUpdateRequest(BaseModel):
  status: TaskStatus


class TaskDeliverableSubmitRequest(BaseModel):
  summary: str | None = None
  attachment_ids: list[UUID] = Field(default_factory=list)


class TaskAssignmentRejectRequest(BaseModel):
  reason: str | None = None


class TaskAssignmentDelegateRequest(BaseModel):
  assignee_id: UUID
  reason: str | None = None


class TaskDeliverableReviewRequest(BaseModel):
  action: Literal["approve", "return_for_rework"]
  comment: str | None = None
  quality_score: int | None = Field(default=None, ge=1, le=5)


class TaskCommentRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  task_id: UUID
  user_id: UUID
  author_label: str | None = None
  content: str
  content_format: CommentFormat
  is_internal: bool
  created_at: datetime
  updated_at: datetime
  attachments: list[AttachmentRead] = Field(default_factory=list)


class TaskLogRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  task_id: UUID
  operator_id: UUID
  operator_label: str | None = None
  action_type: TaskActionType
  from_status: TaskStatus | None
  to_status: TaskStatus | None
  detail: dict[str, Any]
  created_at: datetime


class TaskActivityEntryRead(BaseModel):
  entry_type: Literal["comment", "log"]
  created_at: datetime
  comment: TaskCommentRead | None = None
  log: TaskLogRead | None = None


class TaskStatsSummaryRead(BaseModel):
  total_tasks: int
  completed_tasks: int
  completion_rate: float
  overdue_tasks: int
  overdue_rate: float
  tasks_by_status: dict[str, int]


class TaskWorkloadEntryRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  assignee_id: UUID
  assignee_email: str
  assignee_label: str
  department_id: UUID | None
  department_name: str | None
  total_tasks: int
  open_tasks: int
  completed_tasks: int
  overdue_tasks: int


class TaskBoardColumnRead(BaseModel):
  status: TaskStatus
  tasks: list[TaskRead]


class TaskGanttEntryRead(BaseModel):
  task: TaskRead
  dependency_ids: list[UUID]
