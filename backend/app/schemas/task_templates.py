from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.tasks import TaskRead


class TaskTemplateStepInput(BaseModel):
  step_key: str = Field(min_length=1, max_length=64)
  title: str = Field(min_length=1, max_length=255)
  description: str | None = None
  step_type: str = Field(default="task", min_length=1, max_length=32)
  assignment_mode: str = Field(default="single", min_length=1, max_length=32)
  join_mode: str = Field(default="all", min_length=1, max_length=32)
  default_assignee_rule: dict[str, Any] = Field(default_factory=dict)
  default_due_offset_hours: int | None = None
  sort_order: int | None = None
  config: dict[str, Any] = Field(default_factory=dict)
  depends_on_step_keys: list[str] = Field(default_factory=list)
  approval_type: str = Field(default="none", min_length=1, max_length=32)
  reject_target_step_key: str | None = None
  downstream_trigger: dict[str, Any] | None = None


class TaskScheduleRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  template_id: UUID
  owner_user_id: UUID
  cron_expr: str
  timezone: str
  next_run_at: datetime | None
  is_active: bool
  payload: dict[str, Any]
  last_run_at: datetime | None
  last_run_status: str | None
  last_run_message: str | None
  last_run_task_count: int | None
  created_at: datetime
  updated_at: datetime


class TaskTemplateStepRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  template_id: UUID
  step_key: str
  title: str
  description: str | None
  step_type: str
  assignment_mode: str
  join_mode: str
  default_assignee_rule: dict[str, Any]
  default_due_offset_hours: int | None
  sort_order: int
  config: dict[str, Any]
  approval_type: str
  reject_target_step_key: str | None
  downstream_trigger: dict[str, Any] | None
  created_at: datetime
  updated_at: datetime
  depends_on_step_keys: list[str] = Field(default_factory=list)


class TaskTemplateRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  code: str
  base_code: str
  version: int
  name: str
  category: str
  description: str | None
  trigger_type: str
  config: dict[str, Any]
  is_active: bool
  created_by: UUID
  source_template_id: UUID | None
  latest_version: int = 1
  has_instances: bool = False
  is_structure_locked: bool = False
  created_at: datetime
  updated_at: datetime
  steps: list[TaskTemplateStepRead] = Field(default_factory=list)
  schedules: list[TaskScheduleRead] = Field(default_factory=list)


class TaskTemplateStepRunRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  instance_id: UUID
  template_step_id: UUID
  assignee_user_id: UUID
  assignee_email: str | None = None
  iteration: int
  status: str
  decision: str | None
  result_payload: dict[str, Any] | None
  completed_at: datetime | None
  created_at: datetime
  updated_at: datetime
  task: TaskRead | None = None


class TaskTemplateInstanceStepRead(BaseModel):
  step: TaskTemplateStepRead
  status: str
  blocked_dependency_keys: list[str] = Field(default_factory=list)
  total_run_count: int = 0
  active_run_count: int = 0
  completed_run_count: int = 0
  history_iteration_count: int = 0
  latest_iteration: int = 0
  step_runs: list[TaskTemplateStepRunRead] = Field(default_factory=list)


class TaskTemplateInstanceRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  template_id: UUID
  initiator_user_id: UUID
  initiator_email: str | None = None
  department_id: UUID | None
  department_name: str | None = None
  status: str
  payload: dict[str, Any]
  completed_at: datetime | None
  total_step_count: int = 0
  completed_step_count: int = 0
  active_step_count: int = 0
  blocked_step_count: int = 0
  ready_step_count: int = 0
  progress_percent: int = 0
  created_at: datetime
  updated_at: datetime
  step_snapshots: list[TaskTemplateInstanceStepRead] = Field(default_factory=list)


class TaskTemplateCreateRequest(BaseModel):
  code: str = Field(min_length=1, max_length=64)
  source_template_id: UUID | None = None
  name: str = Field(min_length=1, max_length=120)
  category: str = Field(min_length=1, max_length=64)
  description: str | None = None
  trigger_type: str = Field(default="manual", min_length=1, max_length=32)
  config: dict[str, Any] = Field(default_factory=dict)
  is_active: bool = True
  steps: list[TaskTemplateStepInput] = Field(default_factory=list)


class TaskTemplateUpdateRequest(BaseModel):
  code: str | None = Field(default=None, min_length=1, max_length=64)
  name: str | None = Field(default=None, min_length=1, max_length=120)
  category: str | None = Field(default=None, min_length=1, max_length=64)
  description: str | None = None
  trigger_type: str | None = Field(default=None, min_length=1, max_length=32)
  config: dict[str, Any] | None = None
  is_active: bool | None = None
  steps: list[TaskTemplateStepInput] | None = None


class TaskTemplateInstantiateRequest(BaseModel):
  department_id: UUID | None = None
  watcher_user_ids: list[UUID] = Field(default_factory=list)
  payload: dict[str, Any] = Field(default_factory=dict)


class TaskScheduleCreateRequest(BaseModel):
  template_id: UUID
  cron_expr: str = Field(min_length=1, max_length=128)
  timezone: str = Field(default="UTC", min_length=1, max_length=64)
  payload: dict[str, Any] = Field(default_factory=dict)
  is_active: bool = True


class TaskScheduleUpdateRequest(BaseModel):
  cron_expr: str | None = Field(default=None, min_length=1, max_length=128)
  timezone: str | None = Field(default=None, min_length=1, max_length=64)
  payload: dict[str, Any] | None = None
  is_active: bool | None = None


class TaskTemplateInstantiationRead(BaseModel):
  template: TaskTemplateRead
  instance: TaskTemplateInstanceRead
  tasks: list[TaskRead] = Field(default_factory=list)


class StepRunDecideRequest(BaseModel):
  decision: str = Field(min_length=1, max_length=32)
  comment: str | None = None
