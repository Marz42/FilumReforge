"""Video workflow v1 schemas: form engine + run context (W1)."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

RunKind = Literal["batch", "production"]
CaptureColumnType = Literal["text", "textarea", "number", "datetime", "user"]
AggregateOnConfirmAction = Literal["finalize_topics_and_fork", "advance_only"]


class LaunchFieldSchema(BaseModel):
  key: str = Field(min_length=1, max_length=64)
  label: str = Field(min_length=1, max_length=120)
  type: Literal["text", "textarea", "datetime", "user_multi", "department"] = "text"
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


class ParticipantsSnapshotEntry(BaseModel):
  mode: Literal["all", "subset"]
  user_ids: list[UUID] = Field(default_factory=list)

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
  "LaunchSchema",
  "ParticipantsSnapshotEntry",
  "RunKind",
  "WorkflowGraphTemplateNodeConfigSchema",
  "WorkflowRunContextSchema",
  "validate_aggregate_schema",
  "validate_capture_schema",
  "validate_launch_schema",
  "validate_node_config",
  "validate_run_context",
  "ValidationError",
]
