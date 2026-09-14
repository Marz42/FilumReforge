from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import UserStatus
from app.core.exceptions import NotFoundError
from app.models import Department, Position, Profile, ProfilePosition, ReportingLine, User
from app.schemas.position_workbench import (
  PositionAssigneeUserSummaryRead,
  PositionAssignmentDetailRead,
  PositionEffectiveRangeRead,
  PositionImpactCountsRead,
  PositionReportingLineDetailRead,
  PositionWorkbenchCatalogItemRead,
  PositionWorkbenchCatalogRead,
  PositionWorkbenchDetailRead,
  PositionWorkbenchSummaryRead,
)
from app.schemas.profiles import PositionRead
from app.services.access_control import ensure_management_role


def _is_active_on(*, starts_at: date, ends_at: date | None, as_of: date) -> bool:
  if starts_at > as_of:
    return False
  if ends_at is not None and ends_at < as_of:
    return False
  return True


def _user_label(user: User | None, profile: Profile | None) -> str | None:
  if profile is not None and profile.real_name:
    return f"{profile.real_name} <{user.email}>" if user is not None else profile.real_name
  if user is not None:
    return user.email
  return None


class PositionWorkbenchService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def get_catalog(self, *, actor: User, as_of: date | None = None) -> PositionWorkbenchCatalogRead:
    ensure_management_role(actor)
    effective_as_of = as_of or date.today()
    positions = list(
      await self._session.scalars(
        select(Position).order_by(Position.is_active.desc(), Position.name.asc())
      )
    )
    assignments = list(await self._session.scalars(select(ProfilePosition)))
    reporting_lines = list(await self._session.scalars(select(ReportingLine)))

    assignments_by_position: dict[UUID, list[ProfilePosition]] = {}
    for assignment in assignments:
      assignments_by_position.setdefault(assignment.position_id, []).append(assignment)

    catalog_items: list[PositionWorkbenchCatalogItemRead] = []
    all_assignee_ids: set[UUID] = set()
    for position in positions:
      position_assignments = assignments_by_position.get(position.id, [])
      impact = self._build_impact(
        assignments=position_assignments,
        reporting_lines=reporting_lines,
        as_of=effective_as_of,
      )
      active_assignees = {
        item.user_id
        for item in position_assignments
        if _is_active_on(starts_at=item.starts_at, ends_at=item.ends_at, as_of=effective_as_of)
      }
      all_assignee_ids.update(active_assignees)
      catalog_items.append(
        PositionWorkbenchCatalogItemRead(
          id=position.id,
          code=position.code,
          name=position.name,
          level=position.level,
          extra_metadata=position.extra_metadata or {},
          is_active=position.is_active,
          created_at=position.created_at,
          updated_at=position.updated_at,
          impact=impact,
        )
      )

    return PositionWorkbenchCatalogRead(
      summary=PositionWorkbenchSummaryRead(
        total_positions=len(positions),
        active_positions=sum(1 for item in positions if item.is_active),
        total_assignees=len(all_assignee_ids),
      ),
      positions=catalog_items,
      as_of=effective_as_of,
    )

  async def get_detail(
    self,
    *,
    actor: User,
    position_id: UUID,
    as_of: date | None = None,
  ) -> PositionWorkbenchDetailRead:
    ensure_management_role(actor)
    effective_as_of = as_of or date.today()
    position = await self._session.get(Position, position_id)
    if position is None:
      raise NotFoundError("岗位不存在。")

    assignments = list(
      await self._session.scalars(
        select(ProfilePosition)
        .options(
          selectinload(ProfilePosition.department),
          selectinload(ProfilePosition.user),
        )
        .where(ProfilePosition.position_id == position_id)
        .order_by(ProfilePosition.starts_at.desc(), ProfilePosition.created_at.desc())
      )
    )
    assignee_ids = {item.user_id for item in assignments}
    profiles = {
      profile.user_id: profile
      for profile in await self._session.scalars(
        select(Profile).where(Profile.user_id.in_(assignee_ids))
      )
    } if assignee_ids else {}
    departments = {
      department.id: department
      for department in await self._session.scalars(select(Department))
    }

    reporting_lines: list[ReportingLine] = []
    if assignee_ids:
      reporting_lines = list(
        await self._session.scalars(
          select(ReportingLine)
          .options(
            selectinload(ReportingLine.manager),
            selectinload(ReportingLine.department),
          )
          .where(ReportingLine.user_id.in_(assignee_ids))
          .order_by(ReportingLine.starts_at.desc(), ReportingLine.created_at.desc())
        )
      )

    manager_ids = {line.manager_user_id for line in reporting_lines}
    manager_profiles = {
      profile.user_id: profile
      for profile in await self._session.scalars(
        select(Profile).where(Profile.user_id.in_(manager_ids))
      )
    } if manager_ids else {}

    def build_user_summary(user: User | None, user_id: UUID) -> PositionAssigneeUserSummaryRead:
      profile = profiles.get(user_id)
      department_id = profile.department_id if profile is not None else None
      department = departments.get(department_id) if department_id is not None else None
      return PositionAssigneeUserSummaryRead(
        user_id=user_id,
        email=user.email if user is not None else f"{user_id}@unknown.local",
        real_name=profile.real_name if profile is not None else None,
        employee_no=profile.employee_no if profile is not None else None,
        status=user.status if user is not None else UserStatus.INACTIVE,
        department_id=department_id,
        department_name=department.name if department is not None else None,
      )

    assignment_details = [
      PositionAssignmentDetailRead(
        id=assignment.id,
        user=build_user_summary(assignment.user, assignment.user_id),
        department_id=assignment.department_id,
        department_name=assignment.department.name if assignment.department is not None else None,
        assignment_type=assignment.assignment_type,
        is_primary=assignment.is_primary,
        starts_at=assignment.starts_at,
        ends_at=assignment.ends_at,
        is_effective=_is_active_on(
          starts_at=assignment.starts_at,
          ends_at=assignment.ends_at,
          as_of=effective_as_of,
        ),
      )
      for assignment in assignments
    ]
    user_summary_by_id = {item.user.user_id: item.user for item in assignment_details}

    reporting_details = [
      PositionReportingLineDetailRead(
        id=line.id,
        user=user_summary_by_id.get(line.user_id)
        or build_user_summary(None, line.user_id),
        manager_user_id=line.manager_user_id,
        manager_label=_user_label(line.manager, manager_profiles.get(line.manager_user_id)),
        department_id=line.department_id,
        department_name=line.department.name if line.department is not None else None,
        line_type=line.line_type,
        is_primary=line.is_primary,
        starts_at=line.starts_at,
        ends_at=line.ends_at,
        is_effective=_is_active_on(
          starts_at=line.starts_at,
          ends_at=line.ends_at,
          as_of=effective_as_of,
        ),
      )
      for line in reporting_lines
    ]

    open_ended = sum(1 for item in assignments if item.ends_at is None)
    starts = [item.starts_at for item in assignments]
    ends = [item.ends_at for item in assignments if item.ends_at is not None]

    return PositionWorkbenchDetailRead(
      position=PositionRead.model_validate(position),
      impact=self._build_impact(
        assignments=assignments,
        reporting_lines=reporting_lines,
        as_of=effective_as_of,
      ),
      assignments=assignment_details,
      reporting_lines=reporting_details,
      effective_range=PositionEffectiveRangeRead(
        earliest_starts_at=min(starts) if starts else None,
        latest_ends_at=None if open_ended > 0 or not ends else max(ends),
        open_ended_assignment_count=open_ended,
      ),
      as_of=effective_as_of,
    )

  def _build_impact(
    self,
    *,
    assignments: list[ProfilePosition],
    reporting_lines: list[ReportingLine],
    as_of: date,
  ) -> PositionImpactCountsRead:
    active_assignments = [
      item
      for item in assignments
      if _is_active_on(starts_at=item.starts_at, ends_at=item.ends_at, as_of=as_of)
    ]
    assignee_ids = {item.user_id for item in active_assignments}
    active_reporting = [
      line
      for line in reporting_lines
      if line.user_id in assignee_ids
      and _is_active_on(starts_at=line.starts_at, ends_at=line.ends_at, as_of=as_of)
    ]
    return PositionImpactCountsRead(
      assignee_count=len(assignee_ids),
      primary_count=sum(1 for item in active_assignments if item.is_primary),
      secondary_count=sum(1 for item in active_assignments if not item.is_primary),
      department_count=len({item.department_id for item in active_assignments}),
      active_reporting_line_count=len(active_reporting),
    )
