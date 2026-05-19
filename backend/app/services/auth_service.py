from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
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
from app.services.access_control import ensure_active_user, ensure_management_role


@dataclass(slots=True)
class AuthSession:
  access_token: str
  refresh_token: str
  token_type: str
  user: User


@dataclass(slots=True)
class InvitationIssue:
  user: User
  invite_url: str
  expires_at: datetime


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

  @staticmethod
  def _normalize_expires_at(token_record: RefreshToken | None) -> datetime | None:
    if token_record is None:
      return None
    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
      return expires_at.replace(tzinfo=UTC)
    return expires_at

  @staticmethod
  def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
      return None
    if value.tzinfo is None:
      return value.replace(tzinfo=UTC)
    return value

  @staticmethod
  def _hash_invitation_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()

  def _build_invitation_url(self, *, token: str) -> str:
    return f"{self._settings.frontend_app_url}/login?invite={token}"

  async def _get_user_by_invitation_token(self, *, token: str) -> User:
    invitation_token_hash = self._hash_invitation_token(token)
    user = await self._session.scalar(
      select(User).where(User.invitation_token_hash == invitation_token_hash)
    )
    if user is None:
      raise NotFoundError("邀请链接不存在或已失效。")
    invitation_expires_at = self._normalize_datetime(user.invitation_expires_at)
    if user.invitation_revoked_at is not None:
      raise ConflictError("该邀请已被撤销。")
    if user.invitation_accepted_at is not None:
      raise ConflictError("该邀请已完成注册。")
    if invitation_expires_at is None or invitation_expires_at <= datetime.now(UTC):
      raise ConflictError("该邀请已过期。")
    return user

  async def create_invitation(
    self,
    *,
    actor: User,
    email: str,
    role: UserRole,
  ) -> InvitationIssue:
    ensure_management_role(actor)

    normalized_email = email.lower()
    existing_user = await self._session.scalar(
      select(User).where(func.lower(User.email) == normalized_email)
    )
    if existing_user is not None:
      raise ConflictError("邮箱已被占用。")

    raw_token = token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(hours=self._settings.auth_invitation_expiry_hours)
    user = User(
      email=normalized_email,
      password_hash=hash_password(token_urlsafe(32)),
      role=role,
      status=UserStatus.INACTIVE,
      invited_by=actor.id,
      invitation_token_hash=self._hash_invitation_token(raw_token),
      invitation_sent_at=datetime.now(UTC),
      invitation_expires_at=expires_at,
    )
    self._session.add(user)
    await self._session.commit()
    await self._session.refresh(user)
    return InvitationIssue(
      user=user,
      invite_url=self._build_invitation_url(token=raw_token),
      expires_at=expires_at,
    )

  async def get_invitation_preview(self, *, token: str) -> User:
    return await self._get_user_by_invitation_token(token=token)

  async def accept_invitation(self, *, token: str, password: str) -> AuthSession:
    user = await self._get_user_by_invitation_token(token=token)
    user.password_hash = hash_password(password)
    user.status = UserStatus.ACTIVE
    user.invitation_token_hash = None
    user.invitation_accepted_at = datetime.now(UTC)
    user.last_login_at = datetime.now(UTC)

    auth_session = await self._issue_session_for_user(user=user)
    await self._session.commit()
    await self._session.refresh(user)
    auth_session.user = user
    return auth_session

  async def revoke_invitation(self, *, actor: User, user_id: UUID) -> User:
    ensure_management_role(actor)
    user = await self._session.get(User, user_id)
    if user is None:
      raise NotFoundError("用户不存在。")
    if user.invitation_accepted_at is not None:
      raise ConflictError("该邀请已完成注册，无法撤销。")
    if user.invitation_revoked_at is not None:
      raise ConflictError("该邀请已撤销。")
    if user.invitation_token_hash is None:
      raise ConflictError("当前账号没有待处理邀请。")

    user.invitation_revoked_at = datetime.now(UTC)
    await self._session.commit()
    await self._session.refresh(user)
    return user

  async def _issue_session_for_user(self, *, user: User) -> AuthSession:
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
    self._session.add(
      RefreshToken(
        user_id=user.id,
        token_id=refresh_token_id,
        expires_at=datetime.now(UTC) + timedelta(days=self._settings.jwt_refresh_token_days),
      )
    )
    return AuthSession(
      access_token=access_token_value,
      refresh_token=refresh_token_value,
      token_type="bearer",
      user=user,
    )

  async def _get_active_refresh_token_record(self, *, refresh_token: str) -> tuple[RefreshToken, UUID]:
    payload = decode_token(
      settings=self._settings,
      token=refresh_token,
      expected_type="refresh",
    )
    token_id = payload.get("jti")
    user_id = payload.get("sub")
    if token_id is None or user_id is None:
      raise AuthenticationError("刷新令牌缺少必要字段。")

    user_uuid = UUID(user_id)
    token_record = await self._session.scalar(
      select(RefreshToken).where(
        RefreshToken.token_id == token_id,
        RefreshToken.user_id == user_uuid,
      )
    )
    expires_at = self._normalize_expires_at(token_record)
    if token_record is None or token_record.revoked_at is not None or expires_at is None or expires_at <= datetime.now(UTC):
      raise AuthenticationError("刷新令牌已失效。")
    return token_record, user_uuid

  async def authenticate(self, *, email: str, password: str) -> AuthSession:
    user = await self._session.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None or not verify_password(password, user.password_hash):
      raise AuthenticationError("邮箱或密码错误。")

    ensure_active_user(user)

    user.last_login_at = datetime.now(UTC)
    auth_session = await self._issue_session_for_user(user=user)
    await self._session.commit()
    await self._session.refresh(user)
    auth_session.user = user
    return auth_session

  async def refresh(self, *, refresh_token: str) -> AuthSession:
    token_record, user_id = await self._get_active_refresh_token_record(refresh_token=refresh_token)

    user = await self._session.get(User, user_id)
    if user is None:
      raise NotFoundError("用户不存在。")
    ensure_active_user(user)

    token_record.revoked_at = datetime.now(UTC)
    auth_session = await self._issue_session_for_user(user=user)
    await self._session.commit()
    return auth_session

  async def revoke_refresh_token(self, *, refresh_token: str) -> bool:
    try:
      token_record, _ = await self._get_active_refresh_token_record(refresh_token=refresh_token)
    except (AuthenticationError, NotFoundError, ValueError):
      return False

    token_record.revoked_at = datetime.now(UTC)
    await self._session.commit()
    return True

  async def change_password(
    self,
    *,
    user: User,
    current_password: str,
    new_password: str,
  ) -> None:
    if not verify_password(current_password, user.password_hash):
      raise AuthenticationError("当前密码不正确。")

    user.password_hash = hash_password(new_password)
    await self._session.commit()

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
