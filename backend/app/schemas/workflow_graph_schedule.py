"""F-24: workflow graph template schedule schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ScheduleScopeMode = Literal["self", "subtree"]
ScheduleParticipantMode = Literal["all", "subset"]


class GraphTemplateScheduleCreateRequest(BaseModel):
  template_id: UUID
  name: str = Field(min_length=1, max_length=120)
  scope_department_id: UUID
  scope_mode: ScheduleScopeMode = "self"
  cron_expr: str = Field(min_length=1, max_length=128)
  timezone: str = Field(default="Asia/Shanghai", max_length=64)
  default_inputs: dict[str, object] = Field(default_factory=dict)
  run_label_template: str | None = Field(default=None, max_length=255)
  participant_mode: ScheduleParticipantMode = "all"
  participant_user_ids: list[UUID] = Field(default_factory=list)
  exclude_department_ids: list[UUID] = Field(default_factory=list)
  exclude_user_ids: list[UUID] = Field(default_factory=list)
  is_active: bool = True


class GraphTemplateScheduleUpdateRequest(BaseModel):
  name: str | None = Field(default=None, min_length=1, max_length=120)
  scope_department_id: UUID | None = None
  scope_mode: ScheduleScopeMode | None = None
  cron_expr: str | None = Field(default=None, min_length=1, max_length=128)
  timezone: str | None = Field(default=None, max_length=64)
  default_inputs: dict[str, object] | None = None
  run_label_template: str | None = Field(default=None, max_length=255)
  participant_mode: ScheduleParticipantMode | None = None
  participant_user_ids: list[UUID] | None = None
  exclude_department_ids: list[UUID] | None = None
  exclude_user_ids: list[UUID] | None = None
  is_active: bool | None = None


class GraphTemplateScheduleRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  template_id: UUID
  template_code: str | None = None
  template_name: str | None = None
  name: str
  scope_department_id: UUID
  scope_department_name: str | None = None
  scope_mode: ScheduleScopeMode
  cron_expr: str
  timezone: str
  default_inputs: dict[str, object]
  run_label_template: str | None
  participant_mode: ScheduleParticipantMode
  participant_user_ids: list[UUID]
  exclude_department_ids: list[UUID]
  exclude_user_ids: list[UUID]
  is_active: bool
  created_by: UUID
  next_run_at: datetime | None
  last_run_at: datetime | None
  last_run_status: str | None
  last_run_message: str | None
  last_run_instance_count: int | None
  created_at: datetime
  updated_at: datetime


class GraphTemplateScheduleRunNowResponse(BaseModel):
  created_count: int
  skipped_count: int
  failed_count: int
  details: list[dict[str, object]] = Field(default_factory=list)
