from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

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


class AuthSessionRead(BaseModel):
  access_token: str
  token_type: str
  user: UserRead


class BootstrapStatusRead(BaseModel):
  bootstrap_required: bool
