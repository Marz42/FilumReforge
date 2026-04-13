from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProfileRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  user_id: UUID
  employee_no: str
  real_name: str
  department_id: UUID
  job_title: str | None
  phone: str | None
  hire_date: date | None
  custom_fields: dict[str, Any]
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
