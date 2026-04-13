from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole, UserStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models import User
from app.services.access_control import ensure_active_user, ensure_management_role


class UserService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def list_users(self, *, actor: User) -> list[User]:
    ensure_management_role(actor)
    result = await self._session.scalars(select(User).order_by(User.created_at.desc()))
    return list(result)

  async def create_user(
    self,
    *,
    actor: User,
    email: str,
    password: str,
    role: UserRole,
    status: UserStatus = UserStatus.ACTIVE,
  ) -> User:
    ensure_management_role(actor)

    existing_user = await self._session.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if existing_user is not None:
      raise ConflictError("邮箱已被占用。")

    user = User(
      email=email.lower(),
      password_hash=hash_password(password),
      role=role,
      status=status,
    )
    self._session.add(user)
    await self._session.commit()
    await self._session.refresh(user)
    return user

  async def get_user(self, *, actor: User, user_id: UUID) -> User:
    ensure_active_user(actor)
    if actor.role not in {UserRole.ADMIN, UserRole.HR} and actor.id != user_id:
      raise NotFoundError("用户不存在。")

    user = await self._session.get(User, user_id)
    if user is None:
      raise NotFoundError("用户不存在。")
    return user

  async def update_user(
    self,
    *,
    actor: User,
    user_id: UUID,
    email: str | None = None,
    password: str | None = None,
    role: UserRole | None = None,
    status: UserStatus | None = None,
  ) -> User:
    ensure_management_role(actor)

    user = await self._session.get(User, user_id)
    if user is None:
      raise NotFoundError("用户不存在。")

    if email is not None and email.lower() != user.email:
      existing_user = await self._session.scalar(select(User).where(func.lower(User.email) == email.lower()))
      if existing_user is not None:
        raise ConflictError("邮箱已被占用。")
      user.email = email.lower()

    if password is not None:
      user.password_hash = hash_password(password)
    if role is not None:
      user.role = role
    if status is not None:
      user.status = status

    await self._session.commit()
    await self._session.refresh(user)
    return user
