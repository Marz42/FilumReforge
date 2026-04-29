from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import UserStatus
from app.core.exceptions import NotFoundError
from app.models import Department, Profile, User
from app.schemas.profiles import EmploymentEventRead
from app.services.access_control import ensure_management_role
from app.services.profile_service import ProfileService
from app.services.user_service import UserService


@dataclass(slots=True)
class PeopleManagementSnapshot:
  summary: dict[str, int]
  people: list[dict[str, Any]]


@dataclass(slots=True)
class PeopleManagementDetailSnapshot:
  summary: dict[str, Any]
  account: User
  profile: dict[str, Any] | None
  actions: dict[str, bool]
  primary_manager_user_id: UUID | None
  primary_manager_label: str | None
  latest_employment_event: EmploymentEventRead | None


class PeopleManagementService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session
    self._user_service = UserService(session)
    self._profile_service = ProfileService(session)

  async def list_people(self, *, actor: User) -> PeopleManagementSnapshot:
    ensure_management_role(actor)

    users = await self._user_service.list_users(actor=actor)
    profile_views = await self._profile_service.list_profile_views(actor=actor)
    department_name_map = await self._load_department_name_map()
    profile_view_map = {
      profile_view["user_id"]: profile_view
      for profile_view in profile_views
    }

    people = [
      self._build_person_summary(
        user=user,
        profile_view=profile_view_map.get(user.id),
        department_name_map=department_name_map,
      )
      for user in users
    ]
    people.sort(key=lambda item: ((item["real_name"] or item["email"]).lower(), item["email"].lower()))

    summary = {
      "total_people": len(people),
      "profiled_people": sum(1 for item in people if item["has_profile"]),
      "unprofiled_people": sum(1 for item in people if not item["has_profile"]),
      "inactive_people": sum(1 for item in people if item["status"] != UserStatus.ACTIVE),
    }
    return PeopleManagementSnapshot(summary=summary, people=people)

  async def get_person_detail(
    self,
    *,
    actor: User,
    user_id: UUID,
  ) -> PeopleManagementDetailSnapshot:
    ensure_management_role(actor)

    account = await self._user_service.get_user(actor=actor, user_id=user_id)
    profile_view = await self._get_profile_view_if_exists(actor=actor, user_id=user_id)
    department_name_map = await self._load_department_name_map()
    summary = self._build_person_summary(
      user=account,
      profile_view=profile_view,
      department_name_map=department_name_map,
    )

    primary_manager_user_id: UUID | None = None
    primary_manager_label: str | None = None
    latest_employment_event: EmploymentEventRead | None = None

    if profile_view is not None:
      primary_reporting_line = next(
        (
          line
          for line in profile_view["reporting_lines"]
          if line.is_primary
        ),
        None,
      )
      if primary_reporting_line is None and profile_view["reporting_lines"]:
        primary_reporting_line = profile_view["reporting_lines"][0]

      if primary_reporting_line is not None:
        primary_manager_user_id = primary_reporting_line.manager_user_id
        primary_manager_label = await self._resolve_user_label(primary_manager_user_id)

      if profile_view["employment_events"]:
        latest_employment_event = max(
          (
            EmploymentEventRead.model_validate(event)
            for event in profile_view["employment_events"]
          ),
          key=lambda item: (item.effective_date, item.created_at),
        )

    actions = {
      "can_edit_user": True,
      "can_delete_user": profile_view is None,
      "can_create_profile": profile_view is None,
      "can_edit_profile": profile_view is not None,
      "can_manage_relations": profile_view is not None,
      "can_manage_lifecycle": profile_view is not None,
      "can_manage_delegations": profile_view is not None,
    }
    return PeopleManagementDetailSnapshot(
      summary=summary,
      account=account,
      profile=profile_view,
      actions=actions,
      primary_manager_user_id=primary_manager_user_id,
      primary_manager_label=primary_manager_label,
      latest_employment_event=latest_employment_event,
    )

  async def _load_department_name_map(self) -> dict[UUID, str]:
    departments = await self._session.scalars(select(Department))
    return {department.id: department.name for department in departments}

  async def _get_profile_view_if_exists(
    self,
    *,
    actor: User,
    user_id: UUID,
  ) -> dict[str, Any] | None:
    profile = await self._session.get(Profile, user_id)
    if profile is None:
      return None

    try:
      return await self._profile_service.get_profile_view(actor=actor, user_id=user_id)
    except NotFoundError:
      return None

  async def _resolve_user_label(self, user_id: UUID) -> str | None:
    statement = select(User).options(selectinload(User.profile)).where(User.id == user_id)
    user = await self._session.scalar(statement)
    if user is None:
      return None
    if user.profile is not None and user.profile.real_name:
      return user.profile.real_name
    return user.email

  def _build_person_summary(
    self,
    *,
    user: User,
    profile_view: dict[str, Any] | None,
    department_name_map: dict[UUID, str],
  ) -> dict[str, Any]:
    department_id = profile_view["department_id"] if profile_view is not None else None
    return {
      "user_id": user.id,
      "email": user.email,
      "role": user.role,
      "status": user.status,
      "last_login_at": user.last_login_at,
      "has_profile": profile_view is not None,
      "profile_completion_state": "complete" if profile_view is not None else "missing_profile",
      "employee_no": profile_view["employee_no"] if profile_view is not None else None,
      "real_name": profile_view["real_name"] if profile_view is not None else None,
      "department_id": department_id,
      "department_name": department_name_map.get(department_id) if department_id is not None else None,
      "job_title": profile_view["job_title"] if profile_view is not None else None,
      "hire_date": profile_view["hire_date"] if profile_view is not None else None,
      "updated_at": profile_view["updated_at"] if profile_view is not None else user.updated_at,
    }
