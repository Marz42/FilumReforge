from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import DelegationScopeType, DelegationStatus
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models import Delegation, Department, User
from app.services.access_control import ensure_active_user, is_management_role


def _utc_now() -> datetime:
  return datetime.now(timezone.utc)


def _normalize_datetime(value: datetime) -> datetime:
  if value.tzinfo is None:
    return value.replace(tzinfo=timezone.utc)
  return value.astimezone(timezone.utc)


def _resolve_status(
  *,
  starts_at: datetime,
  ends_at: datetime,
  now: datetime,
  current_status: DelegationStatus | None = None,
) -> DelegationStatus:
  if current_status == DelegationStatus.REVOKED:
    return DelegationStatus.REVOKED
  normalized_start = _normalize_datetime(starts_at)
  normalized_end = _normalize_datetime(ends_at)
  if normalized_end <= now:
    return DelegationStatus.EXPIRED
  if normalized_start <= now < normalized_end:
    return DelegationStatus.ACTIVE
  return DelegationStatus.PENDING


class DelegationService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def list_profile_delegations(self, *, user_id: UUID) -> list[Delegation]:
    statement = (
      select(Delegation)
      .options(
        selectinload(Delegation.delegator),
        selectinload(Delegation.delegate),
        selectinload(Delegation.scope_department),
      )
      .where(
        or_(
          Delegation.delegator_user_id == user_id,
          Delegation.delegate_user_id == user_id,
        )
      )
      .order_by(Delegation.starts_at.desc(), Delegation.created_at.desc())
    )
    delegations = list(await self._session.scalars(statement))
    await self._refresh_statuses(delegations)
    return delegations

  async def create_delegation(
    self,
    *,
    actor: User,
    delegator_user_id: UUID,
    delegate_user_id: UUID,
    scope_type: DelegationScopeType,
    starts_at: datetime,
    ends_at: datetime,
    scope_department_id: UUID | None = None,
    scope_filters: dict[str, object] | None = None,
  ) -> Delegation:
    ensure_active_user(actor)
    if actor.id != delegator_user_id and not is_management_role(actor):
      raise AuthorizationError("当前账号不能创建该授权。")
    if delegator_user_id == delegate_user_id:
      raise ConflictError("委托人和被委托人不能相同。")
    if ends_at <= starts_at:
      raise ConflictError("授权时间范围无效。")
    if ends_at <= _utc_now():
      raise ConflictError("授权结束时间必须晚于当前时间。")

    delegator = await self._session.get(User, delegator_user_id)
    if delegator is None:
      raise NotFoundError("委托人不存在。")
    delegate = await self._session.get(User, delegate_user_id)
    if delegate is None:
      raise NotFoundError("被委托人不存在。")
    if scope_department_id is not None and await self._session.get(Department, scope_department_id) is None:
      raise NotFoundError("授权范围部门不存在。")

    delegation = Delegation(
      delegator_user_id=delegator_user_id,
      delegate_user_id=delegate_user_id,
      scope_type=scope_type,
      scope_department_id=scope_department_id,
      scope_filters=scope_filters or {},
      status=_resolve_status(
        starts_at=starts_at,
        ends_at=ends_at,
        now=_utc_now(),
      ),
      starts_at=starts_at,
      ends_at=ends_at,
      created_by=actor.id,
    )
    self._session.add(delegation)
    await self._session.commit()
    await self._session.refresh(delegation)
    return delegation

  async def update_delegation(
    self,
    *,
    actor: User,
    delegation_id: UUID,
    status: DelegationStatus | None = None,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    scope_department_id: UUID | None = None,
    scope_filters: dict[str, object] | None = None,
  ) -> Delegation:
    delegation = await self._session.get(Delegation, delegation_id)
    if delegation is None:
      raise NotFoundError("授权不存在。")
    if actor.id != delegation.delegator_user_id and not is_management_role(actor):
      raise AuthorizationError("当前账号不能修改该授权。")

    if scope_department_id is not None and await self._session.get(Department, scope_department_id) is None:
      raise NotFoundError("授权范围部门不存在。")

    if starts_at is not None:
      delegation.starts_at = starts_at
    if ends_at is not None:
      delegation.ends_at = ends_at
    if delegation.ends_at <= delegation.starts_at:
      raise ConflictError("授权时间范围无效。")
    if scope_department_id is not None:
      delegation.scope_department_id = scope_department_id
    if scope_filters is not None:
      delegation.scope_filters = scope_filters

    if status == DelegationStatus.REVOKED:
      delegation.status = DelegationStatus.REVOKED
    else:
      delegation.status = _resolve_status(
        starts_at=delegation.starts_at,
        ends_at=delegation.ends_at,
        now=_utc_now(),
        current_status=delegation.status,
      )

    await self._session.commit()
    await self._session.refresh(delegation)
    return delegation

  async def _refresh_statuses(self, delegations: list[Delegation]) -> None:
    now = _utc_now()
    changed = False
    for delegation in delegations:
      next_status = _resolve_status(
        starts_at=delegation.starts_at,
        ends_at=delegation.ends_at,
        now=now,
        current_status=delegation.status,
      )
      if delegation.status != next_status:
        delegation.status = next_status
        changed = True
    if changed:
      await self._session.commit()
