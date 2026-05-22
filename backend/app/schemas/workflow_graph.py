from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
  WorkflowGraphInstanceStatus,
  WorkflowGraphNodeType,
  WorkflowGraphTemplateStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)


class WorkflowNodeInstanceRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  instance_id: UUID
  template_node_id: UUID | None
  node_key: str
  instance_key: str = "singleton"
  title: str
  node_type: WorkflowGraphNodeType
  engine_state: WorkflowNodeEngineState
  business_state: WorkflowNodeBusinessState
  assignee_user_id: UUID | None
  iteration: int
  activated_at: datetime | None
  completed_at: datetime | None
  terminated_at: datetime | None
  created_at: datetime


class WorkflowGraphTemplateSummaryRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  code: str
  name: str
  description: str | None = None
  status: WorkflowGraphTemplateStatus
  version: int
  run_kind: str | None = None
  config: dict[str, object] = {}


class WorkflowGraphTemplateNodeSummaryRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  node_key: str
  title: str
  sort_order: int


class WorkflowGraphTemplateDetailRead(WorkflowGraphTemplateSummaryRead):
  nodes: list[WorkflowGraphTemplateNodeSummaryRead] = Field(default_factory=list)


class WorkflowGraphTemplateUpdateRequest(BaseModel):
  name: str | None = Field(default=None, min_length=1, max_length=120)
  description: str | None = Field(default=None, max_length=2000)
  config: dict[str, object] | None = None


class WorkflowGraphInstanceRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  template_id: UUID | None
  initiator_user_id: UUID
  department_id: UUID | None
  source_type: str | None
  status: WorkflowGraphInstanceStatus
  current_node_key: str | None
  run_label: str | None = None
  parent_instance_id: UUID | None = None
  context: dict[str, object]
  context_version: int
  max_iterations: int
  completed_at: datetime | None
  created_at: datetime
  node_instances: list[WorkflowNodeInstanceRead] = []


class WorkflowGraphInstanceDetailRead(WorkflowGraphInstanceRead):
  total_node_count: int
  completed_node_count: int
  active_node_count: int
  pending_node_count: int
  progress_percent: int


class WorkflowNodeCompleteRequest(BaseModel):
  summary: str | None = None
  context_updates: dict[str, object] | None = None


class WorkflowNodeDeepRejectRequest(BaseModel):
  target_node_key: str
  reason: str | None = None


class WorkflowNodeTakeoverRequest(BaseModel):
  assignee_user_id: UUID
  reason: str


class WorkflowSmartNoticeCandidatesRequest(BaseModel):
  initiator_user_id: UUID
  target_user_id: UUID
  include_user_ids: list[UUID] = []
  exclude_user_ids: list[UUID] = []


class WorkflowSmartNoticeCandidatesResponse(BaseModel):
  candidate_user_ids: list[UUID]
  reached_initiator: bool
