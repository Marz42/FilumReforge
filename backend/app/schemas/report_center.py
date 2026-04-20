from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import ReportDirection, ReportRouteStatus, ReportStatus


class ReportActionOptionRead(BaseModel):
  action: str
  label: str
  button_type: str = "primary"


class ReportTargetOptionRead(BaseModel):
  user_id: UUID
  label: str
  path_labels: list[str] = Field(default_factory=list)
  hops: int


class WorkflowDefinitionOptionRead(BaseModel):
  id: UUID
  name: str


class ReportRouteRead(BaseModel):
  id: UUID
  sequence_no: int
  sender_user_id: UUID
  sender_label: str
  recipient_user_id: UUID
  recipient_label: str
  assigned_user_id: UUID | None
  assigned_label: str | None = None
  status: ReportRouteStatus
  activated_at: datetime | None
  acted_at: datetime | None
  note: str | None = None


class ReportRead(BaseModel):
  id: UUID
  direction: ReportDirection
  status: ReportStatus
  title: str
  content_md: str
  initiator_user_id: UUID
  initiator_label: str
  target_user_id: UUID
  target_label: str
  current_recipient_user_id: UUID | None
  current_recipient_label: str | None = None
  current_route_sequence: int | None
  workflow_definition_id: UUID | None = None
  workflow_definition_name: str | None = None
  workflow_instance_id: UUID | None = None
  created_at: datetime
  updated_at: datetime
  completed_at: datetime | None = None
  returned_at: datetime | None = None
  archived_at: datetime | None = None
  available_actions: list[ReportActionOptionRead] = Field(default_factory=list)
  routes: list[ReportRouteRead] = Field(default_factory=list)


class ReportCenterPermissionsRead(BaseModel):
  can_create_upward: bool
  can_create_downward: bool


class ReportCenterRead(BaseModel):
  permissions: ReportCenterPermissionsRead
  upward_target_options: list[ReportTargetOptionRead] = Field(default_factory=list)
  downward_target_options: list[ReportTargetOptionRead] = Field(default_factory=list)
  workflow_definition_options: list[WorkflowDefinitionOptionRead] = Field(default_factory=list)
  pending_reports: list[ReportRead] = Field(default_factory=list)
  initiated_reports: list[ReportRead] = Field(default_factory=list)
  history_reports: list[ReportRead] = Field(default_factory=list)


class ReportCreateRequest(BaseModel):
  direction: ReportDirection
  target_user_id: UUID
  title: str = Field(min_length=1, max_length=255)
  content_md: str = Field(min_length=1, max_length=4000)
  workflow_definition_id: UUID | None = None


class ReportActionRequest(BaseModel):
  action: str
  note: str | None = Field(default=None, max_length=4000)
