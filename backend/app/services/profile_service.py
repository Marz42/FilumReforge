from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import UserRole
from app.core.exceptions import ConflictError, NotFoundError
from app.models import Department, Profile, User
from app.services.access_control import ensure_active_user, ensure_management_role, get_managed_department_ids


class ProfileService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def list_profiles(self, *, actor: User) -> list[Profile]:
    ensure_active_user(actor)

    statement = (
      select(Profile)
      .options(selectinload(Profile.user), selectinload(Profile.department))
      .order_by(Profile.created_at.desc())
    )

    if actor.role not in {UserRole.ADMIN, UserRole.HR}:
      managed_department_ids = await get_managed_department_ids(self._session, actor.id)
      if managed_department_ids:
        statement = statement.where(
          or_(Profile.user_id == actor.id, Profile.department_id.in_(managed_department_ids))
        )
      else:
        statement = statement.where(Profile.user_id == actor.id)

    result = await self._session.scalars(statement)
    return list(result)

  async def get_profile(self, *, actor: User, user_id: UUID) -> Profile:
    profiles = await self.list_profiles(actor=actor)
    for profile in profiles:
      if profile.user_id == user_id:
        return profile
    raise NotFoundError("档案不存在。")

  async def create_profile(
    self,
    *,
    actor: User,
    user_id: UUID,
    employee_no: str,
    real_name: str,
    department_id: UUID,
    job_title: str | None = None,
    phone: str | None = None,
    hire_date: date | None = None,
    custom_fields: dict[str, Any] | None = None,
  ) -> Profile:
    ensure_management_role(actor)

    user = await self._session.get(User, user_id)
    if user is None:
      raise NotFoundError("用户不存在。")
    department = await self._session.get(Department, department_id)
    if department is None:
      raise NotFoundError("部门不存在。")

    existing_employee_no = await self._session.scalar(
      select(Profile).where(Profile.employee_no == employee_no)
    )
    if existing_employee_no is not None:
      raise ConflictError("员工编号已存在。")

    existing_profile = await self._session.get(Profile, user_id)
    if existing_profile is not None:
      raise ConflictError("该用户已有档案。")

    profile = Profile(
      user_id=user_id,
      employee_no=employee_no,
      real_name=real_name,
      department_id=department_id,
      job_title=job_title,
      phone=phone,
      hire_date=hire_date,
      custom_fields=custom_fields or {},
    )
    self._session.add(profile)
    await self._session.commit()
    await self._session.refresh(profile)
    return profile

  async def update_profile(
    self,
    *,
    actor: User,
    user_id: UUID,
    employee_no: str | None = None,
    real_name: str | None = None,
    department_id: UUID | None = None,
    job_title: str | None = None,
    phone: str | None = None,
    hire_date: date | None = None,
    custom_fields: dict[str, Any] | None = None,
  ) -> Profile:
    ensure_management_role(actor)

    profile = await self._session.get(Profile, user_id)
    if profile is None:
      raise NotFoundError("档案不存在。")

    if employee_no is not None and employee_no != profile.employee_no:
      existing_profile = await self._session.scalar(
        select(Profile).where(Profile.employee_no == employee_no, Profile.user_id != user_id)
      )
      if existing_profile is not None:
        raise ConflictError("员工编号已存在。")
      profile.employee_no = employee_no

    if department_id is not None:
      department = await self._session.get(Department, department_id)
      if department is None:
        raise NotFoundError("部门不存在。")
      profile.department_id = department_id
    if real_name is not None:
      profile.real_name = real_name
    if job_title is not None:
      profile.job_title = job_title
    if phone is not None:
      profile.phone = phone
    if hire_date is not None:
      profile.hire_date = hire_date
    if custom_fields is not None:
      profile.custom_fields = custom_fields

    await self._session.commit()
    await self._session.refresh(profile)
    return profile
