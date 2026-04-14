from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
  ApprovalMode,
  WorkflowDefinitionStatus,
  WorkflowInstanceStatus,
  WorkflowStepRunStatus,
  WorkflowStepType,
)


class WorkflowStepInput(BaseModel):
  step_key: str = Field(min_length=1, max_length=64)
  name: str = Field(min_length=1, max_length=120)
  step_type: WorkflowStepType = WorkflowStepType.APPROVAL
  approval_mode: ApprovalMode | None = None
  assignee_rule: dict[str, Any] = Field(default_factory=dict)
  reject_target_step_key: str | None = Field(default=None, max_length=64)
  sort_order: int | None = None
  config: dict[str, Any] = Field(default_factory=dict)


class WorkflowStepRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  definition_id: UUID
  step_key: str
  name: str
  step_type: WorkflowStepType
  approval_mode: ApprovalMode | None
  assignee_rule: dict[str, Any]
  reject_target_step_key: str | None
  sort_order: int
  config: dict[str, Any]
  created_at: datetime
  updated_at: datetime


class WorkflowDefinitionRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  code: str
  name: str
  scope_type: str
  status: WorkflowDefinitionStatus
  version: int
  config: dict[str, Any]
  created_by: UUID
  created_at: datetime
  updated_at: datetime
  steps: list[WorkflowStepRead] = Field(default_factory=list)


class WorkflowDefinitionCreateRequest(BaseModel):
  code: str = Field(min_length=1, max_length=64)
  name: str = Field(min_length=1, max_length=120)
  scope_type: str = Field(min_length=1, max_length=64)
  status: WorkflowDefinitionStatus = WorkflowDefinitionStatus.DRAFT
  version: int = 1
  config: dict[str, Any] = Field(default_factory=dict)
  steps: list[WorkflowStepInput] = Field(default_factory=list)


class WorkflowDefinitionUpdateRequest(BaseModel):
  code: str | None = Field(default=None, min_length=1, max_length=64)
  name: str | None = Field(default=None, min_length=1, max_length=120)
  scope_type: str | None = Field(default=None, min_length=1, max_length=64)
  status: WorkflowDefinitionStatus | None = None
  version: int | None = None
  config: dict[str, Any] | None = None
  steps: list[WorkflowStepInput] | None = None


class WorkflowStepRunRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  instance_id: UUID
  step_id: UUID
  assignee_user_id: UUID
  delegated_from_user_id: UUID | None
  status: WorkflowStepRunStatus
  acted_at: datetime | None
  comment: str | None
  payload: dict[str, Any]
  created_at: datetime
  updated_at: datetime
  step: WorkflowStepRead | None = None


class WorkflowInstanceRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  definition_id: UUID
  source_type: str
  source_id: UUID | None
  initiator_user_id: UUID
  status: WorkflowInstanceStatus
  current_step_key: str | None
  payload: dict[str, Any]
  started_at: datetime
  completed_at: datetime | None
  created_at: datetime
  updated_at: datetime
  step_runs: list[WorkflowStepRunRead] = Field(default_factory=list)
  definition: WorkflowDefinitionRead | None = None


class WorkflowStartRequest(BaseModel):
  definition_id: UUID
  source_type: str = Field(min_length=1, max_length=64)
  source_id: UUID | None = None
  payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowActionRequest(BaseModel):
  action: Literal["approve", "reject", "return"]
  comment: str | None = None
