from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.enums import UserRole, UserStatus
from app.core.password_policy import validate_password_strength


class UserRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  email: EmailStr
  role: UserRole
  status: UserStatus
  last_login_at: datetime | None
  created_at: datetime
  updated_at: datetime


class UserCreateRequest(BaseModel):
  email: EmailStr
  password: str = Field(min_length=8, max_length=128)
  role: UserRole
  status: UserStatus = UserStatus.ACTIVE

  @field_validator("password")
  @classmethod
  def _validate_password_strength(cls, value: str) -> str:
    return validate_password_strength(value)


class UserUpdateRequest(BaseModel):
  email: EmailStr | None = None
  password: str | None = Field(default=None, min_length=8, max_length=128)
  role: UserRole | None = None
  status: UserStatus | None = None

  @field_validator("password")
  @classmethod
  def _validate_password_strength(cls, value: str | None) -> str | None:
    if value is None:
      return None
    return validate_password_strength(value)
