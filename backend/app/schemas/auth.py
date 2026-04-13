from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.schemas.users import UserRead


class BootstrapAdminRequest(BaseModel):
  email: EmailStr
  password: str = Field(min_length=8, max_length=128)
  real_name: str = Field(min_length=1, max_length=120)
  employee_no: str = Field(min_length=1, max_length=64)


class LoginRequest(BaseModel):
  email: EmailStr
  password: str = Field(min_length=8, max_length=128)


class RefreshTokenRequest(BaseModel):
  refresh_token: str = Field(min_length=1)


class AuthSessionRead(BaseModel):
  access_token: str
  refresh_token: str
  token_type: str
  user: UserRead
