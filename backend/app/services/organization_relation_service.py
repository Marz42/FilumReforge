from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import PositionAssignmentType, ReportingLineType
from app.core.exceptions import ConflictError, NotFoundError
from app.models import Department, Position, Profile, ProfilePosition, ReportingLine, User
from app.services.access_control import ensure_management_role


class OrganizationRelationService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def list_positions(self) -> list[Position]:
    statement = select(Position).order_by(Position.is_active.desc(), Position.name.asc())
    return list(await self._session.scalars(statement))

  async def create_position(
    self,
    *,
    actor: User,
    code: str,
    name: str,
    level: str | None = None,
    extra_metadata: dict[str, object] | None = None,
    is_active: bool = True,
  ) -> Position:
    ensure_management_role(actor)

    existing = await self._session.scalar(select(Position).where(Position.code == code))
    if existing is not None:
      raise ConflictError("岗位编码已存在。")

    position = Position(
      code=code,
      name=name,
      level=level,
      extra_metadata=extra_metadata or {},
      is_active=is_active,
    )
    self._session.add(position)
    await self._session.commit()
    await self._session.refresh(position)
    return position

  async def list_profile_positions(self, *, user_id: UUID) -> list[ProfilePosition]:
    statement = (
      select(ProfilePosition)
      .options(
        selectinload(ProfilePosition.position),
        selectinload(ProfilePosition.department),
      )
      .where(ProfilePosition.user_id == user_id)
      .order_by(ProfilePosition.starts_at.desc(), ProfilePosition.created_at.desc())
    )
    return list(await self._session.scalars(statement))

  async def list_reporting_lines(self, *, user_id: UUID) -> list[ReportingLine]:
    statement = (
      select(ReportingLine)
      .options(
        selectinload(ReportingLine.manager),
        selectinload(ReportingLine.department),
      )
      .where(ReportingLine.user_id == user_id)
      .order_by(ReportingLine.starts_at.desc(), ReportingLine.created_at.desc())
    )
    return list(await self._session.scalars(statement))

  async def assign_position(
    self,
    *,
    actor: User,
    user_id: UUID,
    position_id: UUID,
    department_id: UUID,
    assignment_type: PositionAssignmentType = PositionAssignmentType.PRIMARY,
    is_primary: bool = False,
    starts_at: date,
    ends_at: date | None = None,
  ) -> ProfilePosition:
    ensure_management_role(actor)

    assignment = await self._assign_position_record(
      user_id=user_id,
      position_id=position_id,
      department_id=department_id,
      assignment_type=assignment_type,
      is_primary=is_primary,
      starts_at=starts_at,
      ends_at=ends_at,
    )
    await self._session.commit()
    await self._session.refresh(assignment)
    return assignment

  async def create_reporting_line(
    self,
    *,
    actor: User,
    user_id: UUID,
    manager_user_id: UUID,
    line_type: ReportingLineType,
    starts_at: date,
    department_id: UUID | None = None,
    is_primary: bool = False,
    ends_at: date | None = None,
  ) -> ReportingLine:
    ensure_management_role(actor)

    reporting_line = await self._create_reporting_line_record(
      user_id=user_id,
      manager_user_id=manager_user_id,
      line_type=line_type,
      starts_at=starts_at,
      department_id=department_id,
      is_primary=is_primary,
      ends_at=ends_at,
    )
    await self._session.commit()
    await self._session.refresh(reporting_line)
    return reporting_line

  async def _assign_position_record(
    self,
    *,
    user_id: UUID,
    position_id: UUID,
    department_id: UUID,
    assignment_type: PositionAssignmentType,
    is_primary: bool,
    starts_at: date,
    ends_at: date | None,
  ) -> ProfilePosition:
    user = await self._session.get(User, user_id)
    if user is None:
      raise NotFoundError("用户不存在。")

    profile = await self._session.get(Profile, user_id)
    if profile is None:
      raise NotFoundError("档案不存在。")

    position = await self._session.get(Position, position_id)
    if position is None:
      raise NotFoundError("岗位不存在。")

    department = await self._session.get(Department, department_id)
    if department is None:
      raise NotFoundError("部门不存在。")

    if is_primary:
      await self._close_open_primary_positions(user_id=user_id, effective_start=starts_at)

    assignment = ProfilePosition(
      user_id=user_id,
      position_id=position_id,
      department_id=department_id,
      assignment_type=assignment_type,
      is_primary=is_primary,
      starts_at=starts_at,
      ends_at=ends_at,
    )
    self._session.add(assignment)
    await self._session.flush()

    if is_primary:
      profile.department_id = department_id
      profile.job_title = position.name

    return assignment

  async def _create_reporting_line_record(
    self,
    *,
    user_id: UUID,
    manager_user_id: UUID,
    line_type: ReportingLineType,
    starts_at: date,
    department_id: UUID | None,
    is_primary: bool,
    ends_at: date | None,
  ) -> ReportingLine:
    user = await self._session.get(User, user_id)
    if user is None:
      raise NotFoundError("员工不存在。")
    manager = await self._session.get(User, manager_user_id)
    if manager is None:
      raise NotFoundError("上级不存在。")
    if user_id == manager_user_id:
      raise ConflictError("汇报上级不能是本人。")

    if department_id is not None and await self._session.get(Department, department_id) is None:
      raise NotFoundError("部门不存在。")

    if is_primary and line_type == ReportingLineType.SOLID:
      await self._close_open_primary_reporting_lines(user_id=user_id, effective_start=starts_at)

    reporting_line = ReportingLine(
      user_id=user_id,
      manager_user_id=manager_user_id,
      department_id=department_id,
      line_type=line_type,
      is_primary=is_primary,
      starts_at=starts_at,
      ends_at=ends_at,
    )
    self._session.add(reporting_line)
    await self._session.flush()
    return reporting_line

  async def _close_open_primary_positions(
    self,
    *,
    user_id: UUID,
    effective_start: date,
  ) -> None:
    existing_assignments = list(
      await self._session.scalars(
        select(ProfilePosition).where(
          ProfilePosition.user_id == user_id,
          ProfilePosition.is_primary.is_(True),
          or_(ProfilePosition.ends_at.is_(None), ProfilePosition.ends_at >= effective_start),
        )
      )
    )
    for assignment in existing_assignments:
      if assignment.starts_at > effective_start:
        raise ConflictError("存在未来生效的主任职，请先调整已有任职记录。")
      assignment.ends_at = effective_start
      assignment.is_primary = False

  async def _close_open_primary_reporting_lines(
    self,
    *,
    user_id: UUID,
    effective_start: date,
  ) -> None:
    existing_lines = list(
      await self._session.scalars(
        select(ReportingLine).where(
          ReportingLine.user_id == user_id,
          ReportingLine.line_type == ReportingLineType.SOLID,
          ReportingLine.is_primary.is_(True),
          or_(ReportingLine.ends_at.is_(None), ReportingLine.ends_at >= effective_start),
        )
      )
    )
    for reporting_line in existing_lines:
      if reporting_line.starts_at > effective_start:
        raise ConflictError("存在未来生效的主要汇报线，请先调整已有汇报记录。")
      reporting_line.ends_at = effective_start
      reporting_line.is_primary = False
