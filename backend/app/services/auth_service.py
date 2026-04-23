from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.enums import UserRole, UserStatus
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.security import (
  create_access_token,
  create_refresh_token,
  decode_token,
  hash_password,
  verify_password,
)
from app.models import Department, Profile, RefreshToken, User
from app.services.access_control import ensure_active_user


@dataclass(slots=True)
class AuthSession:
  access_token: str
  refresh_token: str
  token_type: str
  user: User


class AuthService:
  def __init__(self, session: AsyncSession, settings: Settings) -> None:
    self._session = session
    self._settings = settings

  async def bootstrap_admin(
    self,
    *,
    email: str,
    password: str,
    real_name: str,
    employee_no: str,
  ) -> User:
    existing_users = await self._session.scalar(select(func.count()).select_from(User))
    if existing_users:
      raise ConflictError("系统已初始化管理员账号。")

    admin = User(
      email=email.lower(),
      password_hash=hash_password(password),
      role=UserRole.ADMIN,
      status=UserStatus.ACTIVE,
    )
    root_department = Department(
      name="总部",
      code="root",
      manager=admin,
    )
    admin.profile = Profile(
      employee_no=employee_no,
      real_name=real_name,
      department=root_department,
    )

    self._session.add_all([admin, root_department])
    await self._session.commit()
    await self._session.refresh(admin)
    return admin

  async def is_bootstrap_required(self) -> bool:
    existing_users = await self._session.scalar(select(func.count()).select_from(User))
    return not bool(existing_users)

  async def authenticate(self, *, email: str, password: str) -> AuthSession:
    user = await self._session.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None or not verify_password(password, user.password_hash):
      raise AuthenticationError("邮箱或密码错误。")

    ensure_active_user(user)

    refresh_token_value, refresh_token_id = create_refresh_token(
      settings=self._settings,
      user_id=user.id,
      role=user.role,
    )
    access_token_value = create_access_token(
      settings=self._settings,
      user_id=user.id,
      role=user.role,
    )

    user.last_login_at = datetime.now(UTC)
    self._session.add(
      RefreshToken(
        user_id=user.id,
        token_id=refresh_token_id,
        expires_at=datetime.now(UTC) + timedelta(days=self._settings.jwt_refresh_token_days),
      )
    )
    await self._session.commit()
    await self._session.refresh(user)

    return AuthSession(
      access_token=access_token_value,
      refresh_token=refresh_token_value,
      token_type="bearer",
      user=user,
    )

  async def refresh(self, *, refresh_token: str) -> AuthSession:
    payload = decode_token(
      settings=self._settings,
      token=refresh_token,
      expected_type="refresh",
    )
    token_id = payload.get("jti")
    user_id = payload.get("sub")
    if token_id is None or user_id is None:
      raise AuthenticationError("刷新令牌缺少必要字段。")

    token_record = await self._session.scalar(
      select(RefreshToken).where(
        RefreshToken.token_id == token_id,
        RefreshToken.user_id == UUID(user_id),
      )
    )
    expires_at = token_record.expires_at if token_record is not None else None
    if expires_at is not None and expires_at.tzinfo is None:
      expires_at = expires_at.replace(tzinfo=UTC)

    if token_record is None or token_record.revoked_at is not None or expires_at <= datetime.now(UTC):
      raise AuthenticationError("刷新令牌已失效。")

    user = await self._session.get(User, UUID(user_id))
    if user is None:
      raise NotFoundError("用户不存在。")
    ensure_active_user(user)

    token_record.revoked_at = datetime.now(UTC)
    next_refresh_token, next_refresh_token_id = create_refresh_token(
      settings=self._settings,
      user_id=user.id,
      role=user.role,
    )
    next_access_token = create_access_token(
      settings=self._settings,
      user_id=user.id,
      role=user.role,
    )
    self._session.add(
      RefreshToken(
        user_id=user.id,
        token_id=next_refresh_token_id,
        expires_at=datetime.now(UTC) + timedelta(days=self._settings.jwt_refresh_token_days),
      )
    )
    await self._session.commit()

    return AuthSession(
      access_token=next_access_token,
      refresh_token=next_refresh_token,
      token_type="bearer",
      user=user,
    )

  async def get_user_from_access_token(self, token: str) -> User:
    payload = decode_token(
      settings=self._settings,
      token=token,
      expected_type="access",
    )
    user_id = payload.get("sub")
    if user_id is None:
      raise AuthenticationError("访问令牌缺少用户标识。")

    user = await self._session.get(User, UUID(user_id))
    if user is None:
      raise NotFoundError("用户不存在。")
    ensure_active_user(user)
    return user
