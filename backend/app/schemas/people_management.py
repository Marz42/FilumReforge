from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.core.enums import UserRole, UserStatus
from app.schemas.profiles import EmploymentEventRead, ProfileRead
from app.schemas.users import UserRead


class PeopleManagementSummaryRead(BaseModel):
  total_people: int
  profiled_people: int
  unprofiled_people: int
  inactive_people: int


class PeopleManagementPersonRead(BaseModel):
  user_id: UUID
  email: EmailStr
  role: UserRole
  status: UserStatus
  last_login_at: datetime | None
  has_profile: bool
  profile_completion_state: str
  employee_no: str | None
  real_name: str | None
  department_id: UUID | None
  department_name: str | None
  job_title: str | None
  hire_date: date | None
  updated_at: datetime


class PeopleManagementActionsRead(BaseModel):
  can_edit_user: bool
  can_delete_user: bool
  can_create_profile: bool
  can_edit_profile: bool
  can_manage_relations: bool
  can_manage_lifecycle: bool
  can_manage_delegations: bool


class PeopleManagementRead(BaseModel):
  summary: PeopleManagementSummaryRead
  people: list[PeopleManagementPersonRead]


class PeopleManagementDetailRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  summary: PeopleManagementPersonRead
  account: UserRead
  profile: ProfileRead | None
  actions: PeopleManagementActionsRead
  primary_manager_user_id: UUID | None
  primary_manager_label: str | None
  latest_employment_event: EmploymentEventRead | None
