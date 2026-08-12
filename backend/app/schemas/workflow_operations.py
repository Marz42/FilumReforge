from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowOperationReasonRequest(BaseModel):
  reason: str = Field(min_length=3, max_length=500)


class WorkflowIncidentUpdateRequest(WorkflowOperationReasonRequest):
  status: Literal["resolved", "ignored"]


class WorkflowOperationActionRead(BaseModel):
  id: UUID
  status: str
  manual_replay_count: int | None = None


class WorkflowOperationsIssueRead(BaseModel):
  category: str
  severity: str
  instance_id: UUID | None
  node_instance_id: UUID | None
  title: str
  message: str
  age_seconds: int | None


class WorkflowOutboxOperationRead(BaseModel):
  id: UUID
  instance_id: UUID
  node_instance_id: UUID | None
  event_type: str
  status: str
  attempt_count: int
  available_at: datetime | None
  last_error: str | None
  manual_replay_count: int
  last_replayed_at: datetime | None
  last_replayed_by_user_id: UUID | None
  last_replay_reason: str | None
  updated_at: datetime


class WorkflowIncidentOperationRead(BaseModel):
  id: UUID
  category: str
  status: str
  severity: str
  occurrence_count: int
  first_seen_at: datetime
  last_seen_at: datetime
  resolved_at: datetime | None
  resolved_by_user_id: UUID | None
  resolution_note: str | None
  instance_id: UUID | None
  node_instance_id: UUID | None
  task_id: UUID | None
  command_receipt_id: UUID | None
  outbox_event_id: UUID | None
  engine_version: str | None
  detail_keys: list[str] = Field(default_factory=list)


class WorkflowProjectionStreamHealthRead(BaseModel):
  stream_name: str
  status: str
  processed_count: int
  source_count: int
  backlog_count: int
  lag_seconds: int
  last_success_at: datetime | None
  last_error: str | None
  sampled_at: datetime


class WorkflowShadowHealthRead(BaseModel):
  scan_id: UUID
  sample_mode: str
  observed_at: datetime
  outcomes: dict[str, int] = Field(default_factory=dict)
  severities: dict[str, int] = Field(default_factory=dict)


class WorkflowOperationsMetricsRead(BaseModel):
  runs: dict[str, int] = Field(default_factory=dict)
  stalled_run_count: int
  suspended_node_count: int
  join_wait_count: int
  oldest_join_wait_seconds: int
  outbox: dict[str, int] = Field(default_factory=dict)
  outbox_backlog_count: int
  oldest_outbox_backlog_seconds: int
  projection_failed_stream_count: int


class WorkflowOperationsDashboardRead(BaseModel):
  generated_at: datetime
  stalled_minutes: int
  metrics: WorkflowOperationsMetricsRead
  projection_streams: list[WorkflowProjectionStreamHealthRead] = Field(default_factory=list)
  shadow: WorkflowShadowHealthRead | None
  issues: list[WorkflowOperationsIssueRead] = Field(default_factory=list)
  failed_outbox: list[WorkflowOutboxOperationRead] = Field(default_factory=list)
  incidents: list[WorkflowIncidentOperationRead] = Field(default_factory=list)


class WorkflowTraceRead(BaseModel):
  id: UUID
  event_type: str
  occurred_at: datetime
  request_id: str | None
  command_id: str | None
  correlation_id: UUID | None
  instance_id: UUID
  node_instance_id: UUID | None
  task_id: UUID | None
  actor_user_id: UUID | None
  payload_keys: list[str] = Field(default_factory=list)


class WorkflowTraceListRead(BaseModel):
  items: list[WorkflowTraceRead] = Field(default_factory=list)
