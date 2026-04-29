from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.enums import UserRole
from app.core.password_policy import validate_password_strength
from app.schemas.users import UserRead


class BootstrapAdminRequest(BaseModel):
  email: EmailStr
  password: str = Field(min_length=8, max_length=128)
  real_name: str = Field(min_length=1, max_length=120)
  employee_no: str = Field(min_length=1, max_length=64)

  @field_validator("password")
  @classmethod
  def _validate_password_strength(cls, value: str) -> str:
    return validate_password_strength(value)


class LoginRequest(BaseModel):
  email: EmailStr
  password: str = Field(min_length=8, max_length=128)


class InvitationCreateRequest(BaseModel):
  email: EmailStr
  role: UserRole = UserRole.EMPLOYEE


class InvitationRead(BaseModel):
  user: UserRead
  invite_url: str
  expires_at: datetime


class InvitationPreviewRead(BaseModel):
  user_id: UUID
  email: EmailStr
  role: UserRole
  expires_at: datetime


class InvitationAcceptRequest(BaseModel):
  token: str = Field(min_length=16, max_length=256)
  password: str = Field(min_length=8, max_length=128)

  @field_validator("password")
  @classmethod
  def _validate_password_strength(cls, value: str) -> str:
    return validate_password_strength(value)


class AuthSessionRead(BaseModel):
  access_token: str
  token_type: str
  user: UserRead


class BootstrapStatusRead(BaseModel):
  bootstrap_required: bool
