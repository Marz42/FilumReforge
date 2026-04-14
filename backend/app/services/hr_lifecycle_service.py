from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
  EmploymentEventType,
  PositionAssignmentType,
  ReportingLineType,
  UserStatus,
)
from app.core.exceptions import NotFoundError
from app.models import EmploymentEvent, Profile, ProfilePosition, ReportingLine, User
from app.services.access_control import ensure_management_role
from app.services.organization_relation_service import OrganizationRelationService


class HRLifecycleService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session
    self._organization_relation_service = OrganizationRelationService(session)

  async def list_events(self, *, user_id: UUID) -> list[EmploymentEvent]:
    statement = (
      select(EmploymentEvent)
      .where(EmploymentEvent.user_id == user_id)
      .order_by(EmploymentEvent.effective_date.desc(), EmploymentEvent.created_at.desc())
    )
    return list(await self._session.scalars(statement))

  async def create_event(
    self,
    *,
    actor: User,
    user_id: UUID,
    event_type: EmploymentEventType,
    effective_date: date,
    title: str,
    summary: str | None = None,
    payload: dict[str, Any] | None = None,
  ) -> EmploymentEvent:
    ensure_management_role(actor)

    user = await self._session.get(User, user_id)
    if user is None:
      raise NotFoundError("用户不存在。")
    profile = await self._session.get(Profile, user_id)
    if profile is None:
      raise NotFoundError("档案不存在。")

    event_payload = payload or {}
    await self._apply_event_side_effects(
      profile=profile,
      user=user,
      actor=actor,
      event_type=event_type,
      effective_date=effective_date,
      payload=event_payload,
    )

    event = EmploymentEvent(
      user_id=user_id,
      event_type=event_type,
      effective_date=effective_date,
      title=title,
      summary=summary,
      payload=event_payload,
      created_by=actor.id,
    )
    self._session.add(event)
    await self._session.commit()
    await self._session.refresh(event)
    return event

  async def _apply_event_side_effects(
    self,
    *,
    profile: Profile,
    user: User,
    actor: User,
    event_type: EmploymentEventType,
    effective_date: date,
    payload: dict[str, Any],
  ) -> None:
    if event_type in {EmploymentEventType.ONBOARD, EmploymentEventType.REHIRE}:
      user.status = UserStatus.ACTIVE
      profile.hire_date = effective_date

    if event_type == EmploymentEventType.OFFBOARD:
      user.status = UserStatus.OFFBOARDED
      await self._close_open_positions(user_id=user.id, effective_date=effective_date)
      await self._close_open_reporting_lines(user_id=user.id, effective_date=effective_date)

    if event_type in {
      EmploymentEventType.ONBOARD,
      EmploymentEventType.REHIRE,
      EmploymentEventType.TRANSFER,
      EmploymentEventType.PROMOTION,
    }:
      await self._apply_position_payload(
        actor=actor,
        user_id=user.id,
        effective_date=effective_date,
        payload=payload,
      )
      await self._apply_reporting_payload(
        user_id=user.id,
        effective_date=effective_date,
        payload=payload,
      )

    if event_type == EmploymentEventType.TRANSFER and payload.get("department_id") is not None:
      profile.department_id = UUID(str(payload["department_id"]))
    if payload.get("job_title") is not None:
      profile.job_title = str(payload["job_title"])

  async def _apply_position_payload(
    self,
    *,
    actor: User,
    user_id: UUID,
    effective_date: date,
    payload: dict[str, Any],
  ) -> None:
    if payload.get("position_id") is None or payload.get("department_id") is None:
      return

    assignment_type = PositionAssignmentType(payload.get("assignment_type", PositionAssignmentType.PRIMARY.value))
    await self._organization_relation_service._assign_position_record(
      user_id=user_id,
      position_id=UUID(str(payload["position_id"])),
      department_id=UUID(str(payload["department_id"])),
      assignment_type=assignment_type,
      is_primary=bool(payload.get("is_primary", True)),
      starts_at=effective_date,
      ends_at=None,
    )

  async def _apply_reporting_payload(
    self,
    *,
    user_id: UUID,
    effective_date: date,
    payload: dict[str, Any],
  ) -> None:
    manager_user_id = payload.get("manager_user_id")
    if manager_user_id is not None:
      await self._organization_relation_service._create_reporting_line_record(
        user_id=user_id,
        manager_user_id=UUID(str(manager_user_id)),
        line_type=ReportingLineType.SOLID,
        starts_at=effective_date,
        department_id=UUID(str(payload["department_id"])) if payload.get("department_id") is not None else None,
        is_primary=True,
        ends_at=None,
      )

    for dotted_manager_id in payload.get("dotted_manager_ids", []):
      await self._organization_relation_service._create_reporting_line_record(
        user_id=user_id,
        manager_user_id=UUID(str(dotted_manager_id)),
        line_type=ReportingLineType.DOTTED,
        starts_at=effective_date,
        department_id=UUID(str(payload["department_id"])) if payload.get("department_id") is not None else None,
        is_primary=False,
        ends_at=None,
      )

  async def _close_open_positions(self, *, user_id: UUID, effective_date: date) -> None:
    assignments = list(
      await self._session.scalars(
        select(ProfilePosition).where(
          ProfilePosition.user_id == user_id,
          or_(ProfilePosition.ends_at.is_(None), ProfilePosition.ends_at >= effective_date),
        )
      )
    )
    for assignment in assignments:
      assignment.ends_at = effective_date
      assignment.is_primary = False

  async def _close_open_reporting_lines(self, *, user_id: UUID, effective_date: date) -> None:
    reporting_lines = list(
      await self._session.scalars(
        select(ReportingLine).where(
          ReportingLine.user_id == user_id,
          or_(ReportingLine.ends_at.is_(None), ReportingLine.ends_at >= effective_date),
        )
      )
    )
    for reporting_line in reporting_lines:
      reporting_line.ends_at = effective_date
      reporting_line.is_primary = False
