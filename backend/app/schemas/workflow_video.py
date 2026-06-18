"""Video workflow v1 schemas: form engine + run context (W1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

RunKind = Literal["batch", "production"]
CaptureColumnType = Literal["text", "textarea", "number", "datetime", "user"]
AggregateOnConfirmAction = Literal["finalize_topics_and_fork", "advance_only"]


class LaunchFieldSchema(BaseModel):
  key: str = Field(min_length=1, max_length=64)
  label: str = Field(min_length=1, max_length=120)
  type: Literal["text", "textarea", "datetime", "user", "user_multi", "department"] = "text"
  required: bool = False
  policy_ref: str | None = Field(default=None, max_length=64)


class LaunchSchema(BaseModel):
  fields: list[LaunchFieldSchema] = Field(default_factory=list, min_length=1)


class CaptureColumnSchema(BaseModel):
  key: str = Field(min_length=1, max_length=64)
  label: str = Field(min_length=1, max_length=120)
  type: CaptureColumnType = "text"
  required: bool = False


class CaptureSchema(BaseModel):
  mode: Literal["row_table"] = "row_table"
  min_rows: int = Field(default=1, ge=1, le=100)
  max_rows: int = Field(default=20, ge=1, le=200)
  columns: list[CaptureColumnSchema] = Field(min_length=1)
  storage: Literal["deliverable_payload"] = "deliverable_payload"
  completion_policy: Literal["on_capture_submitted"] = "on_capture_submitted"

  @model_validator(mode="after")
  def _validate_row_bounds(self) -> CaptureSchema:
    if self.max_rows < self.min_rows:
      raise ValueError("max_rows 不能小于 min_rows。")
    return self


class AggregateAssigneeColumnSchema(BaseModel):
  key: str = Field(min_length=1, max_length=64)
  label: str = Field(min_length=1, max_length=120)
  type: Literal["user"] = "user"


class AcceptanceRejectToSchema(BaseModel):
  node_key: str = Field(min_length=1, max_length=64)
  instance_key_from: Literal["topic_id", "assignee"] | None = None


class AcceptanceSpecSchema(BaseModel):
  reject_to: AcceptanceRejectToSchema | None = None


class AggregateOnConfirmSchema(BaseModel):
  action: AggregateOnConfirmAction
  child_template_code: str | None = Field(default=None, max_length=64)
  idempotency_key: str | None = Field(default=None, max_length=64)


class AggregateSchema(BaseModel):
  mode: Literal["submission_matrix"] = "submission_matrix"
  source_node_key: str = Field(min_length=1, max_length=64)
  row_id_field: str = Field(default="topic_id", max_length=64)
  row_actions: list[Literal["approve", "reject"]] = Field(default_factory=lambda: ["approve", "reject"])
  assignee_column: AggregateAssigneeColumnSchema | None = None
  on_confirm: AggregateOnConfirmSchema

  @model_validator(mode="after")
  def _validate_fork_action(self) -> AggregateSchema:
    if self.on_confirm.action == "finalize_topics_and_fork":
      if not self.on_confirm.child_template_code:
        raise ValueError("finalize_topics_and_fork 必须配置 child_template_code。")
      if not self.on_confirm.idempotency_key:
        raise ValueError("finalize_topics_and_fork 必须配置 idempotency_key。")
    return self


class ParticipantPolicyDefinition(BaseModel):
  type: Literal["department_members"] = "department_members"
  department_id: UUID | None = None
  exclude_initiator_by_default: bool = True


class ParticipantsSnapshotEntry(BaseModel):
  mode: Literal["all", "subset"]
  user_ids: list[UUID] = Field(default_factory=list)
  include_initiator: bool = False

  @model_validator(mode="after")
  def _validate_subset(self) -> ParticipantsSnapshotEntry:
    if self.mode == "subset" and not self.user_ids:
      raise ValueError("subset 模式至少选择一名参与人。")
    return self


class ApprovedTopic(BaseModel):
  topic_id: UUID
  title: str = Field(min_length=1, max_length=255)
  content: str | None = None
  reason: str | None = None
  source_submitter_id: UUID | None = None
  source_node_instance_id: UUID | None = None
  script_author_id: UUID
  due_at: str | None = None


class TopicCaptureRow(BaseModel):
  model_config = ConfigDict(extra="allow")

  topic_id: UUID | None = None
  title: str | None = Field(default=None, max_length=255)
  content: str | None = None
  reason: str | None = None


class TopicCaptureSubmitRequest(BaseModel):
  topics: list[TopicCaptureRow] = Field(default_factory=list)


class TopicCaptureSubmitResponse(BaseModel):
  task_id: UUID
  node_instance_id: UUID
  topic_count: int
  topics: list[TopicCaptureRow]


class NodeSubmissionRead(BaseModel):
  node_instance_id: UUID
  node_key: str
  instance_key: str
  assignee_user_id: UUID | None
  assignee_email: str | None = None
  assignee_display_name: str | None = None
  submitted_at: datetime | None = None
  topics: list[TopicCaptureRow] = Field(default_factory=list)


class InstanceSubmissionsResponse(BaseModel):
  instance_id: UUID
  node_key: str
  submissions: list[NodeSubmissionRead]


class RejectedCaptureItem(BaseModel):
  reason: str = Field(min_length=1, max_length=2000)
  topic_id: UUID | None = None
  instance_key: str | None = Field(default=None, max_length=64)

  @model_validator(mode="after")
  def _validate_target(self) -> RejectedCaptureItem:
    has_topic = self.topic_id is not None
    has_instance = bool(self.instance_key and str(self.instance_key).strip())
    if has_topic == has_instance:
      raise ValueError("必须且只能指定 topic_id 或 instance_key 之一。")
    return self


class RejectCapturesRequest(BaseModel):
  rejections: list[RejectedCaptureItem] = Field(min_length=1)
  source_node_key: str = Field(default="N1_PROPOSE", min_length=1, max_length=64)


class RejectCapturesResponse(BaseModel):
  instance_id: UUID
  reopened_count: int
  reopened_instance_keys: list[str]


class RejectProductionStepRequest(BaseModel):
  reason: str = Field(min_length=1, max_length=2000)
  target_node_key: str | None = Field(default=None, max_length=64)


class RejectProductionStepResponse(BaseModel):
  instance_id: UUID
  target_node_key: str
  target_node_instance_id: UUID
  iteration: int


class FinalizeTopicsRequest(BaseModel):
  approved_topics: list[ApprovedTopic] = Field(default_factory=list)
  rejected_topics: list[RejectedCaptureItem] = Field(default_factory=list)

  @model_validator(mode="after")
  def _validate_finalize_payload(self) -> FinalizeTopicsRequest:
    if not self.approved_topics and not self.rejected_topics:
      raise ValueError("approved_topics 与 rejected_topics 不能同时为空。")
    return self


class ForkProductionRunsResponse(BaseModel):
  batch_instance_id: UUID
  forked_count: int
  skipped_count: int
  child_instance_ids: list[UUID]
  fork_status: str


class FinalizeTopicsResponse(BaseModel):
  instance_id: UUID
  approved_count: int
  fork_status: str
  fork_deferred: bool = False
  child_instance_ids: list[UUID] = Field(default_factory=list)
  message: str | None = None


class DispatchTopicRequest(BaseModel):
  topic_id: UUID
  title: str = Field(min_length=1, max_length=255)
  script_writer_user_id: UUID
  source_node_instance_id: UUID | None = None


class DispatchTopicResponse(BaseModel):
  instance_id: UUID
  child_instance_id: UUID
  fork_status: str
  message: str | None = None


class CreateGraphTemplateRunRequest(BaseModel):
  inputs: dict[str, Any] = Field(default_factory=dict)
  participants_snapshot: dict[str, ParticipantsSnapshotEntry] = Field(min_length=1)
  department_id: UUID | None = None
  run_label: str | None = Field(default=None, max_length=255)


class CreateGraphTemplateRunResponse(BaseModel):
  instance_id: UUID
  root_task_id: UUID
  run_kind: str
  activated_task_count: int
  node_instance_count: int
  current_node_key: str | None = None


class PreviewParticipantsRequest(BaseModel):
  mode: Literal["all", "subset"] = "all"
  user_ids: list[UUID] = Field(default_factory=list)
  department_id: UUID | None = None


class ParticipantUserPreview(BaseModel):
  id: UUID
  email: str
  display_name: str | None = None


class PreviewParticipantsResponse(BaseModel):
  policy_ref: str
  mode: Literal["all", "subset"]
  user_ids: list[UUID]
  users: list[ParticipantUserPreview]
  snapshot: ParticipantsSnapshotEntry


class WorkflowRunEventRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  instance_id: UUID
  event_type: str
  actor_user_id: UUID | None
  payload: dict[str, Any] = Field(default_factory=dict)
  created_at: datetime


class WorkflowRunEventListResponse(BaseModel):
  instance_id: UUID
  items: list[WorkflowRunEventRead]
  total: int
  limit: int
  offset: int


class WorkflowRunContextSchema(BaseModel):
  """Validated subset of graph instance context for video v1."""

  model_config = ConfigDict(extra="allow")

  run_kind: RunKind | None = None
  run_label: str | None = None
  inputs: dict[str, Any] = Field(default_factory=dict)
  participants_snapshot: dict[str, ParticipantsSnapshotEntry] = Field(default_factory=dict)
  root_task_id: UUID | None = None
  template_version: int | None = Field(default=None, ge=1)
  schema_snapshot: dict[str, Any] = Field(default_factory=dict)
  approved_topics: list[ApprovedTopic] = Field(default_factory=list)
  fork_status: Literal["pending", "completed", "partial"] | None = None
  parent_instance_id: UUID | None = None
  topic_id: UUID | None = None
  topic_title: str | None = None
  script_author_id: UUID | None = None
  edit_assignee_id: UUID | None = None
  publish_at: str | None = None
  platform: str | None = None
  publish_title: str | None = None
  archived: bool | None = None
  archived_at: str | None = None
  forked_child_instance_ids: list[UUID] = Field(default_factory=list)


class WorkflowGraphTemplateNodeConfigSchema(BaseModel):
  """Node config including graph execution + form engine (W1)."""

  model_config = ConfigDict(extra="allow")

  kind: Literal["single", "multi_instance"] = "single"
  expand_from: str | None = Field(default=None, max_length=64)
  participant_policy_ref: str | None = Field(default=None, max_length=64)
  launch_schema: LaunchSchema | None = None
  capture_schema: CaptureSchema | None = None
  aggregate_schema: AggregateSchema | None = None
  acceptance_spec: AcceptanceSpecSchema | None = None
  handshake_required: bool = False
  completion_policy: str | None = None

  @model_validator(mode="after")
  def _validate_multi_instance(self) -> WorkflowGraphTemplateNodeConfigSchema:
    if self.kind == "multi_instance" and not self.expand_from:
      raise ValueError("multi_instance 节点必须配置 expand_from。")
    if self.capture_schema is not None and self.aggregate_schema is not None:
      raise ValueError("同一节点不能同时配置 capture_schema 与 aggregate_schema。")
    return self


def validate_launch_schema(payload: dict[str, Any]) -> LaunchSchema:
  return LaunchSchema.model_validate(payload)


def validate_capture_schema(payload: dict[str, Any]) -> CaptureSchema:
  return CaptureSchema.model_validate(payload)


def validate_aggregate_schema(payload: dict[str, Any]) -> AggregateSchema:
  return AggregateSchema.model_validate(payload)


def validate_node_config(payload: dict[str, Any]) -> WorkflowGraphTemplateNodeConfigSchema:
  return WorkflowGraphTemplateNodeConfigSchema.model_validate(payload)


def validate_run_context(payload: dict[str, Any]) -> WorkflowRunContextSchema:
  return WorkflowRunContextSchema.model_validate(payload)


__all__ = [
  "AggregateOnConfirmAction",
  "AggregateSchema",
  "ApprovedTopic",
  "CaptureSchema",
  "CreateGraphTemplateRunRequest",
  "CreateGraphTemplateRunResponse",
  "LaunchSchema",
  "ParticipantPolicyDefinition",
  "ParticipantUserPreview",
  "ParticipantsSnapshotEntry",
  "PreviewParticipantsRequest",
  "PreviewParticipantsResponse",
  "RunKind",
  "WorkflowGraphTemplateNodeConfigSchema",
  "WorkflowRunContextSchema",
  "WorkflowRunEventListResponse",
  "WorkflowRunEventRead",
  "validate_aggregate_schema",
  "validate_capture_schema",
  "validate_launch_schema",
  "validate_node_config",
  "validate_run_context",
  "ValidationError",
]
