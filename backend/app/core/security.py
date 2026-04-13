from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.enums import UserRole

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
  return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
  return password_hasher.verify(password, password_hash)


def _build_token_payload(
  *,
  user_id: UUID,
  role: UserRole,
  token_type: str,
  expires_delta: timedelta,
  token_id: str | None = None,
) -> dict[str, Any]:
  now = datetime.now(UTC)
  payload: dict[str, Any] = {
    "sub": str(user_id),
    "role": role.value,
    "type": token_type,
    "iat": now,
    "exp": now + expires_delta,
  }
  if token_id is not None:
    payload["jti"] = token_id
  return payload


def create_access_token(*, settings: Settings, user_id: UUID, role: UserRole) -> str:
  payload = _build_token_payload(
    user_id=user_id,
    role=role,
    token_type="access",
    expires_delta=timedelta(minutes=settings.jwt_access_token_minutes),
    token_id=uuid4().hex,
  )
  return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(
  *,
  settings: Settings,
  user_id: UUID,
  role: UserRole,
  token_id: str | None = None,
) -> tuple[str, str]:
  refresh_token_id = token_id or uuid4().hex
  payload = _build_token_payload(
    user_id=user_id,
    role=role,
    token_type="refresh",
    expires_delta=timedelta(days=settings.jwt_refresh_token_days),
    token_id=refresh_token_id,
  )
  token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
  return token, refresh_token_id


def decode_token(*, settings: Settings, token: str, expected_type: str) -> dict[str, Any]:
  try:
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
  except jwt.InvalidTokenError as exc:
    raise AuthenticationError("无效的令牌。") from exc

  if payload.get("type") != expected_type:
    raise AuthenticationError("令牌类型不匹配。")

  return payload
