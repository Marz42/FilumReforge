from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
  DelegationScopeType,
  DelegationStatus,
  EmploymentEventTriggerStatus,
  EmploymentEventType,
  PositionAssignmentType,
  ReportingLineType,
  UserStatus,
)


class ProfileFieldAccessRead(BaseModel):
  field_key: str
  label: str
  field_type: str
  storage_target: str
  is_sensitive: bool
  value: Any
  can_view: bool
  can_edit: bool


class PositionRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  code: str
  name: str
  level: str | None
  extra_metadata: dict[str, Any]
  is_active: bool
  created_at: datetime
  updated_at: datetime


class ProfilePositionRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  user_id: UUID
  position_id: UUID
  department_id: UUID
  assignment_type: PositionAssignmentType
  is_primary: bool
  starts_at: date
  ends_at: date | None
  created_at: datetime
  updated_at: datetime


class ReportingLineRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  user_id: UUID
  manager_user_id: UUID
  department_id: UUID | None
  line_type: ReportingLineType
  is_primary: bool
  starts_at: date
  ends_at: date | None
  created_at: datetime
  updated_at: datetime


class EmploymentEventRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  user_id: UUID
  event_type: EmploymentEventType
  effective_date: date
  title: str
  summary: str | None
  payload: dict[str, Any]
  task_template_id: UUID | None
  workflow_definition_id: UUID | None
  trigger_status: EmploymentEventTriggerStatus
  triggered_at: datetime | None
  trigger_error: str | None
  trigger_attempt_count: int
  triggered_template_instance_id: UUID | None
  triggered_workflow_instance_id: UUID | None
  created_by: UUID
  created_at: datetime


class DelegationRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  delegator_user_id: UUID
  delegate_user_id: UUID
  scope_type: DelegationScopeType
  scope_department_id: UUID | None
  scope_filters: dict[str, Any]
  status: DelegationStatus
  starts_at: datetime
  ends_at: datetime
  created_by: UUID
  created_at: datetime
  updated_at: datetime


class ProfileFieldDefinitionRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  field_key: str
  label: str
  field_type: str
  storage_target: str
  is_sensitive: bool
  config: dict[str, Any]
  is_active: bool
  created_at: datetime
  updated_at: datetime


class ProfileFieldPermissionRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  field_definition_id: UUID
  subject_type: str
  subject_value: str | None
  can_view: bool
  can_edit: bool
  scope_filters: dict[str, Any]
  priority: int
  created_at: datetime
  updated_at: datetime


class ProfileRead(BaseModel):
  user_id: UUID
  user_email: str | None
  user_status: UserStatus | None
  employee_no: str | None
  real_name: str | None
  department_id: UUID | None
  job_title: str | None
  phone: str | None
  hire_date: date | None
  custom_fields: dict[str, Any]
  visible_fields: list[ProfileFieldAccessRead] = Field(default_factory=list)
  positions: list[ProfilePositionRead] = Field(default_factory=list)
  reporting_lines: list[ReportingLineRead] = Field(default_factory=list)
  employment_events: list[EmploymentEventRead] = Field(default_factory=list)
  delegations: list[DelegationRead] = Field(default_factory=list)
  created_at: datetime
  updated_at: datetime


class ProfileCreateRequest(BaseModel):
  user_id: UUID
  employee_no: str = Field(min_length=1, max_length=64)
  real_name: str = Field(min_length=1, max_length=120)
  department_id: UUID
  job_title: str | None = Field(default=None, max_length=120)
  phone: str | None = Field(default=None, max_length=32)
  hire_date: date | None = None
  custom_fields: dict[str, Any] = Field(default_factory=dict)


class ProfileUpdateRequest(BaseModel):
  employee_no: str | None = Field(default=None, min_length=1, max_length=64)
  real_name: str | None = Field(default=None, min_length=1, max_length=120)
  department_id: UUID | None = None
  job_title: str | None = Field(default=None, max_length=120)
  phone: str | None = Field(default=None, max_length=32)
  hire_date: date | None = None
  custom_fields: dict[str, Any] | None = None


class PositionCreateRequest(BaseModel):
  code: str = Field(min_length=1, max_length=64)
  name: str = Field(min_length=1, max_length=120)
  level: str | None = Field(default=None, max_length=64)
  extra_metadata: dict[str, Any] = Field(default_factory=dict)
  is_active: bool = True


class ProfilePositionCreateRequest(BaseModel):
  position_id: UUID
  department_id: UUID
  assignment_type: PositionAssignmentType = PositionAssignmentType.PRIMARY
  is_primary: bool = False
  starts_at: date
  ends_at: date | None = None


class ReportingLineCreateRequest(BaseModel):
  manager_user_id: UUID
  department_id: UUID | None = None
  line_type: ReportingLineType
  is_primary: bool = False
  starts_at: date
  ends_at: date | None = None


class EmploymentEventCreateRequest(BaseModel):
  event_type: EmploymentEventType
  effective_date: date
  title: str = Field(min_length=1, max_length=255)
  summary: str | None = None
  payload: dict[str, Any] = Field(default_factory=dict)
  task_template_id: UUID | None = None
  workflow_definition_id: UUID | None = None


class DelegationCreateRequest(BaseModel):
  delegator_user_id: UUID
  delegate_user_id: UUID
  scope_type: DelegationScopeType = DelegationScopeType.DATA_ACCESS
  scope_department_id: UUID | None = None
  scope_filters: dict[str, Any] = Field(default_factory=dict)
  starts_at: datetime
  ends_at: datetime


class DelegationUpdateRequest(BaseModel):
  status: DelegationStatus | None = None
  starts_at: datetime | None = None
  ends_at: datetime | None = None
  scope_department_id: UUID | None = None
  scope_filters: dict[str, Any] | None = None


class ProfileFieldDefinitionCreateRequest(BaseModel):
  field_key: str = Field(min_length=1, max_length=64)
  label: str = Field(min_length=1, max_length=120)
  field_type: str = Field(min_length=1, max_length=32)
  storage_target: str = Field(min_length=1, max_length=32)
  is_sensitive: bool = False
  config: dict[str, Any] = Field(default_factory=dict)
  is_active: bool = True


class ProfileFieldDefinitionUpdateRequest(BaseModel):
  label: str | None = Field(default=None, min_length=1, max_length=120)
  field_type: str | None = Field(default=None, min_length=1, max_length=32)
  storage_target: str | None = Field(default=None, min_length=1, max_length=32)
  is_sensitive: bool | None = None
  config: dict[str, Any] | None = None
  is_active: bool | None = None


class ProfileFieldPermissionCreateRequest(BaseModel):
  field_definition_id: UUID
  subject_type: str = Field(min_length=1, max_length=32)
  subject_value: str | None = Field(default=None, max_length=64)
  can_view: bool = False
  can_edit: bool = False
  scope_filters: dict[str, Any] = Field(default_factory=dict)
  priority: int = 100


class ProfileFieldPermissionUpdateRequest(BaseModel):
  subject_type: str | None = Field(default=None, min_length=1, max_length=32)
  subject_value: str | None = Field(default=None, max_length=64)
  can_view: bool | None = None
  can_edit: bool | None = None
  scope_filters: dict[str, Any] | None = None
  priority: int | None = None
