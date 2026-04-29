from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import (
  WorkflowGraphInstanceStatus,
  WorkflowGraphNodeType,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)


class WorkflowNodeInstanceRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  instance_id: UUID
  template_node_id: UUID | None
  node_key: str
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


class WorkflowGraphInstanceRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  template_id: UUID | None
  initiator_user_id: UUID
  department_id: UUID | None
  source_type: str | None
  status: WorkflowGraphInstanceStatus
  current_node_key: str | None
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
