from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models import Department, Profile, ProfilePosition, User
from app.services.access_control import (
  ensure_active_user,
  ensure_management_role,
  get_effective_managed_department_ids,
  get_effective_report_user_ids,
  is_management_role,
)
from app.services.delegation_service import DelegationService
from app.services.hr_lifecycle_service import HRLifecycleService
from app.services.organization_relation_service import OrganizationRelationService
from app.services.profile_field_policy_service import ProfileFieldPolicyService


class ProfileService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session
    self._organization_relation_service = OrganizationRelationService(session)
    self._delegation_service = DelegationService(session)
    self._lifecycle_service = HRLifecycleService(session)
    self._field_policy_service = ProfileFieldPolicyService(session)

  async def list_profiles(self, *, actor: User) -> list[Profile]:
    ensure_active_user(actor)

    statement = (
      select(Profile)
      .options(selectinload(Profile.user), selectinload(Profile.department))
      .order_by(Profile.created_at.desc())
    )

    if not is_management_role(actor):
      managed_department_ids = await get_effective_managed_department_ids(self._session, actor.id)
      report_user_ids = await get_effective_report_user_ids(self._session, actor.id)

      filters = [Profile.user_id == actor.id]
      if managed_department_ids:
        filters.append(Profile.department_id.in_(managed_department_ids))
      if report_user_ids:
        filters.append(Profile.user_id.in_(report_user_ids))
      statement = statement.where(or_(*filters))

    result = await self._session.scalars(statement)
    return list(result)

  async def list_profile_views(self, *, actor: User) -> list[dict[str, Any]]:
    profiles = await self.list_profiles(actor=actor)
    return [await self._build_profile_view(actor=actor, profile=profile, include_related=False) for profile in profiles]

  async def get_profile(self, *, actor: User, user_id: UUID) -> Profile:
    profiles = await self.list_profiles(actor=actor)
    for profile in profiles:
      if profile.user_id == user_id:
        return profile
    raise NotFoundError("档案不存在。")

  async def get_profile_view(self, *, actor: User, user_id: UUID) -> dict[str, Any]:
    profile = await self.get_profile(actor=actor, user_id=user_id)
    return await self._build_profile_view(actor=actor, profile=profile, include_related=True)

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
    await self._field_policy_service.ensure_default_definitions()
    await self._field_policy_service.ensure_custom_field_definitions(profile.custom_fields)
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
    ensure_active_user(actor)

    profile = await self.get_profile(actor=actor, user_id=user_id)
    await self._field_policy_service.ensure_default_definitions()
    await self._field_policy_service.ensure_custom_field_definitions(profile.custom_fields)
    if custom_fields is not None:
      await self._field_policy_service.ensure_custom_field_definitions(custom_fields)
    field_access = await self._field_policy_service.get_field_access_map(
      actor=actor,
      profile=profile,
      include_custom_keys=set(custom_fields.keys()) if custom_fields is not None else None,
    )

    def ensure_editable(field_key: str) -> None:
      resolved = field_access.get(field_key)
      if resolved is None or not resolved.can_edit:
        raise AuthorizationError(f"当前账号不能编辑字段：{field_key}")

    if employee_no is not None and employee_no != profile.employee_no:
      ensure_editable("employee_no")
      existing_profile = await self._session.scalar(
        select(Profile).where(Profile.employee_no == employee_no, Profile.user_id != user_id)
      )
      if existing_profile is not None:
        raise ConflictError("员工编号已存在。")
      profile.employee_no = employee_no

    if real_name is not None:
      ensure_editable("real_name")
      profile.real_name = real_name

    if department_id is not None:
      ensure_editable("department_id")
      await self._ensure_primary_assignment_is_absent(user_id=user_id)
      department = await self._session.get(Department, department_id)
      if department is None:
        raise NotFoundError("部门不存在。")
      profile.department_id = department_id

    if job_title is not None:
      ensure_editable("job_title")
      await self._ensure_primary_assignment_is_absent(user_id=user_id)
      profile.job_title = job_title

    if phone is not None:
      ensure_editable("phone")
      profile.phone = phone

    if hire_date is not None:
      ensure_editable("hire_date")
      profile.hire_date = hire_date

    if custom_fields is not None:
      merged_custom_fields = dict(profile.custom_fields)
      for field_key, value in custom_fields.items():
        resolved = field_access.get(field_key)
        if resolved is None or not resolved.can_edit:
          raise AuthorizationError(f"当前账号不能编辑字段：{field_key}")
        merged_custom_fields[field_key] = value
      profile.custom_fields = merged_custom_fields

    await self._session.commit()
    await self._session.refresh(profile)
    return profile

  async def _build_profile_view(
    self,
    *,
    actor: User,
    profile: Profile,
    include_related: bool,
  ) -> dict[str, Any]:
    resolved_fields = await self._field_policy_service.resolve_profile_fields(actor=actor, profile=profile)
    visible_fields = [field for field in resolved_fields if field.can_view]

    core_values = {field.field_key: field.value for field in visible_fields if field.storage_target == "core"}
    custom_values = {
      field.field_key: field.value
      for field in visible_fields
      if field.storage_target == "custom"
    }

    positions = await self._organization_relation_service.list_profile_positions(user_id=profile.user_id) if include_related else []
    reporting_lines = (
      await self._organization_relation_service.list_reporting_lines(user_id=profile.user_id)
      if include_related
      else []
    )
    employment_events = (
      await self._lifecycle_service.list_events(user_id=profile.user_id)
      if include_related
      else []
    )
    delegations = (
      await self._delegation_service.list_profile_delegations(user_id=profile.user_id)
      if include_related
      else []
    )

    return {
      "user_id": profile.user_id,
      "user_email": profile.user.email if profile.user is not None else None,
      "user_status": profile.user.status if profile.user is not None else None,
      "employee_no": core_values.get("employee_no"),
      "real_name": core_values.get("real_name"),
      "department_id": core_values.get("department_id"),
      "job_title": core_values.get("job_title"),
      "phone": core_values.get("phone"),
      "hire_date": core_values.get("hire_date"),
      "custom_fields": custom_values,
      "created_at": profile.created_at,
      "updated_at": profile.updated_at,
      "visible_fields": [
        {
          "field_key": field.field_key,
          "label": field.label,
          "field_type": field.field_type,
          "storage_target": field.storage_target,
          "is_sensitive": field.is_sensitive,
          "value": field.value,
          "can_view": field.can_view,
          "can_edit": field.can_edit,
        }
        for field in visible_fields
      ],
      "positions": positions,
      "reporting_lines": reporting_lines,
      "employment_events": employment_events,
      "delegations": delegations,
    }

  async def _ensure_primary_assignment_is_absent(self, *, user_id: UUID) -> None:
    active_primary_assignment = await self._session.scalar(
      select(ProfilePosition).where(
        ProfilePosition.user_id == user_id,
        ProfilePosition.is_primary.is_(True),
        ProfilePosition.ends_at.is_(None),
      )
    )
    if active_primary_assignment is not None:
      raise ConflictError("请通过任职关系或生命周期事件调整主部门和岗位。")
