from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.core.enums import PositionAssignmentType, ReportingLineType, UserStatus
from app.schemas.profiles import PositionRead


class PositionImpactCountsRead(BaseModel):
  assignee_count: int
  primary_count: int
  secondary_count: int
  department_count: int
  active_reporting_line_count: int


class PositionWorkbenchSummaryRead(BaseModel):
  total_positions: int
  active_positions: int
  total_assignees: int


class PositionWorkbenchCatalogItemRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  code: str
  name: str
  level: str | None
  extra_metadata: dict[str, Any]
  is_active: bool
  created_at: datetime
  updated_at: datetime
  impact: PositionImpactCountsRead


class PositionWorkbenchCatalogRead(BaseModel):
  summary: PositionWorkbenchSummaryRead
  positions: list[PositionWorkbenchCatalogItemRead]
  as_of: date


class PositionAssigneeUserSummaryRead(BaseModel):
  user_id: UUID
  email: EmailStr
  real_name: str | None
  employee_no: str | None
  status: UserStatus
  department_id: UUID | None
  department_name: str | None


class PositionAssignmentDetailRead(BaseModel):
  id: UUID
  user: PositionAssigneeUserSummaryRead
  department_id: UUID
  department_name: str | None
  assignment_type: PositionAssignmentType
  is_primary: bool
  starts_at: date
  ends_at: date | None
  is_effective: bool


class PositionReportingLineDetailRead(BaseModel):
  id: UUID
  user: PositionAssigneeUserSummaryRead
  manager_user_id: UUID
  manager_label: str | None
  department_id: UUID | None
  department_name: str | None
  line_type: ReportingLineType
  is_primary: bool
  starts_at: date
  ends_at: date | None
  is_effective: bool


class PositionEffectiveRangeRead(BaseModel):
  earliest_starts_at: date | None
  latest_ends_at: date | None
  open_ended_assignment_count: int


class PositionWorkbenchDetailRead(BaseModel):
  position: PositionRead
  impact: PositionImpactCountsRead
  assignments: list[PositionAssignmentDetailRead]
  reporting_lines: list[PositionReportingLineDetailRead]
  effective_range: PositionEffectiveRangeRead
  as_of: date
