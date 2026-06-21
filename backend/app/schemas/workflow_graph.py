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
  run_count_total: int | None = None
  run_count_30d: int | None = None
  active_run_count: int | None = None


class WorkflowGraphTemplateNodeSummaryRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  node_key: str
  title: str
  sort_order: int


class WorkflowGraphTemplateDetailRead(WorkflowGraphTemplateSummaryRead):
  nodes: list[WorkflowGraphTemplateNodeSummaryRead] = Field(default_factory=list)


class WorkflowGraphTemplateNodeDetailRead(WorkflowGraphTemplateNodeSummaryRead):
  node_type: WorkflowGraphNodeType = WorkflowGraphNodeType.TASK
  assignment_mode: str = "single"
  join_mode: str = "all"
  assignee_rule: dict[str, object] = Field(default_factory=dict)
  config: dict[str, object] = Field(default_factory=dict)


class WorkflowGraphTemplateEdgeDetailRead(BaseModel):
  id: UUID | None = None
  from_node_key: str
  to_node_key: str
  is_reject_path: bool = False
  condition: dict[str, object] = Field(default_factory=dict)
  priority: int = 0


class WorkflowGraphTemplateDesignerRead(WorkflowGraphTemplateDetailRead):
  base_code: str
  source_template_id: UUID | None = None
  has_instances: bool = False
  structure_locked: bool = False
  nodes: list[WorkflowGraphTemplateNodeDetailRead] = Field(default_factory=list)
  edges: list[WorkflowGraphTemplateEdgeDetailRead] = Field(default_factory=list)


class WorkflowGraphTemplateCreateRequest(BaseModel):
  clone_from_id: UUID
  name: str | None = Field(default=None, min_length=1, max_length=120)


class WorkflowGraphTemplateNodeDraftWrite(BaseModel):
  node_key: str = Field(min_length=1, max_length=64)
  title: str = Field(min_length=1, max_length=255)
  sort_order: int = Field(default=0, ge=0)
  assignment_mode: str = Field(default="single", max_length=32)
  join_mode: str = Field(default="all", max_length=32)
  assignee_rule: dict[str, object] = Field(default_factory=dict)
  config: dict[str, object] = Field(default_factory=dict)


class WorkflowGraphTemplateEdgeDraftWrite(BaseModel):
  from_node_key: str = Field(min_length=1, max_length=64)
  to_node_key: str = Field(min_length=1, max_length=64)
  is_reject_path: bool = False
  condition: dict[str, object] = Field(default_factory=dict)
  priority: int = 0


class WorkflowGraphTemplateDraftSaveRequest(BaseModel):
  name: str = Field(min_length=1, max_length=120)
  description: str | None = Field(default=None, max_length=2000)
  config: dict[str, object] = Field(default_factory=dict)
  nodes: list[WorkflowGraphTemplateNodeDraftWrite] = Field(default_factory=list)
  edges: list[WorkflowGraphTemplateEdgeDraftWrite] | None = None


class WorkflowGraphTemplateStatusUpdateRequest(BaseModel):
  status: WorkflowGraphTemplateStatus


class WorkflowGraphTemplateValidateResponse(BaseModel):
  valid: bool
  errors: list[str] = Field(default_factory=list)


class WorkflowGraphTemplateExportBody(BaseModel):
  name: str
  description: str | None = None
  config: dict[str, object] = Field(default_factory=dict)
  context_schema: dict[str, object] = Field(default_factory=dict)
  nodes: list[WorkflowGraphTemplateNodeDraftWrite] = Field(default_factory=list)
  edges: list[WorkflowGraphTemplateEdgeDraftWrite] = Field(default_factory=list)


class WorkflowGraphTemplateExportBundle(BaseModel):
  format_version: int = 1
  template: WorkflowGraphTemplateExportBody


class WorkflowGraphTemplateImportRequest(BaseModel):
  bundle: WorkflowGraphTemplateExportBundle


class WorkflowGraphTemplateDryRunPolicyPreview(BaseModel):
  policy_ref: str
  mode: str
  user_count: int
  user_ids: list[UUID] = Field(default_factory=list)


class WorkflowGraphTemplateDryRunRequest(BaseModel):
  department_id: UUID | None = None
  inputs: dict[str, object] = Field(default_factory=dict)
  draft: WorkflowGraphTemplateDraftSaveRequest | None = None


class WorkflowGraphTemplateDryRunResponse(BaseModel):
  valid: bool
  errors: list[str] = Field(default_factory=list)
  schema_snapshot: dict[str, object] = Field(default_factory=dict)
  normalized_inputs: dict[str, object] = Field(default_factory=dict)
  entry_node_keys: list[str] = Field(default_factory=list)
  participant_previews: list[WorkflowGraphTemplateDryRunPolicyPreview] = Field(default_factory=list)


class WorkflowGraphTemplateStatsRead(BaseModel):
  template_id: UUID
  run_count_total: int = 0
  run_count_30d: int = 0
  active_run_count: int = 0


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
