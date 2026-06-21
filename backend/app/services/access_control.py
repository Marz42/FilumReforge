from __future__ import annotations

from collections import defaultdict, deque
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
  DepartmentCapability,
  DelegationScopeType,
  DelegationStatus,
  ReportingLineType,
  UserRole,
  UserStatus,
)
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.models import Delegation, Department, Profile, ReportingLine, User

MANAGEMENT_ROLES = {UserRole.ADMIN, UserRole.HR}
DATA_ACCESS_SCOPE_TYPES = {DelegationScopeType.DATA_ACCESS, DelegationScopeType.ALL}
TASK_SCOPE_TYPES = {DelegationScopeType.TASK, DelegationScopeType.ALL}


def ensure_active_user(actor: User) -> None:
  if actor.status != UserStatus.ACTIVE:
    raise AuthenticationError("当前账号不可用。")


def ensure_management_role(actor: User) -> None:
  ensure_active_user(actor)
  if actor.role not in MANAGEMENT_ROLES:
    raise AuthorizationError("当前账号没有管理权限。")


def is_management_role(actor: User) -> bool:
  return actor.role in MANAGEMENT_ROLES


async def get_actor_department_id(session: AsyncSession, actor_id: UUID) -> UUID | None:
  return await session.scalar(select(Profile.department_id).where(Profile.user_id == actor_id))


async def get_actor_department(session: AsyncSession, actor_id: UUID) -> Department | None:
  actor_department_id = await get_actor_department_id(session, actor_id)
  if actor_department_id is None:
    return None
  return await session.get(Department, actor_department_id)


async def get_actor_department_path_ids(session: AsyncSession, actor_id: UUID) -> list[UUID]:
  actor_department_id = await get_actor_department_id(session, actor_id)
  if actor_department_id is None:
    return []

  departments = await _list_departments(session)
  department_map = {department.id: department for department in departments}
  path_ids: list[UUID] = []
  current_id: UUID | None = actor_department_id
  while current_id is not None:
    department = department_map.get(current_id)
    if department is None:
      break
    path_ids.append(department.id)
    current_id = department.parent_id

  path_ids.reverse()
  return path_ids


async def _list_departments(session: AsyncSession) -> list[Department]:
  return list(await session.scalars(select(Department)))


def _expand_department_ids(
  departments: list[Department],
  *,
  root_ids: set[UUID],
) -> set[UUID]:
  if not root_ids:
    return set()

  children_map: dict[UUID | None, list[UUID]] = defaultdict(list)
  for department in departments:
    children_map[department.parent_id].append(department.id)

  result = set(root_ids)
  queue = deque(root_ids)
  while queue:
    department_id = queue.popleft()
    for child_id in children_map.get(department_id, []):
      if child_id not in result:
        result.add(child_id)
        queue.append(child_id)
  return result


async def expand_department_ids(session: AsyncSession, root_ids: set[UUID]) -> set[UUID]:
  departments = await _list_departments(session)
  return _expand_department_ids(departments, root_ids=root_ids)


async def get_managed_department_ids(session: AsyncSession, actor_id: UUID) -> set[UUID]:
  departments = await _list_departments(session)
  managed_roots = {department.id for department in departments if department.manager_id == actor_id}
  return _expand_department_ids(departments, root_ids=managed_roots)


def _utc_now() -> datetime:
  return datetime.now(timezone.utc)


def _normalize_datetime(value: datetime) -> datetime:
  if value.tzinfo is None:
    return value.replace(tzinfo=timezone.utc)
  return value.astimezone(timezone.utc)


def _is_delegation_effective(*, delegation: Delegation, now: datetime) -> bool:
  return (
    delegation.status in {DelegationStatus.PENDING, DelegationStatus.ACTIVE}
    and _normalize_datetime(delegation.starts_at) <= now < _normalize_datetime(delegation.ends_at)
  )


def _is_reporting_line_effective(*, reporting_line: ReportingLine, target_date: date) -> bool:
  return reporting_line.starts_at <= target_date and (
    reporting_line.ends_at is None or reporting_line.ends_at >= target_date
  )


async def list_effective_delegations_for_delegate(
  session: AsyncSession,
  *,
  delegate_user_id: UUID,
  scope_types: set[DelegationScopeType] | None = None,
  now: datetime | None = None,
) -> list[Delegation]:
  moment = now or _utc_now()
  statement = select(Delegation).where(Delegation.delegate_user_id == delegate_user_id)
  if scope_types:
    statement = statement.where(Delegation.scope_type.in_(scope_types))

  delegations = list(await session.scalars(statement))
  return [
    delegation
    for delegation in delegations
    if _is_delegation_effective(delegation=delegation, now=moment)
  ]


async def get_effective_managed_department_ids(
  session: AsyncSession,
  actor_id: UUID,
  *,
  scope_types: set[DelegationScopeType] | None = None,
) -> set[UUID]:
  effective_ids = await get_managed_department_ids(session, actor_id)
  delegations = await list_effective_delegations_for_delegate(
    session,
    delegate_user_id=actor_id,
    scope_types=scope_types or DATA_ACCESS_SCOPE_TYPES,
  )
  if not delegations:
    return effective_ids

  departments = await _list_departments(session)
  for delegation in delegations:
    delegated_ids = await get_managed_department_ids(session, delegation.delegator_user_id)
    if delegation.scope_department_id is None:
      effective_ids.update(delegated_ids)
      continue

    scoped_ids = _expand_department_ids(departments, root_ids={delegation.scope_department_id})
    effective_ids.update(delegated_ids & scoped_ids)
  return effective_ids


async def has_department_capability(
  session: AsyncSession,
  *,
  actor_id: UUID,
  capability: DepartmentCapability,
) -> bool:
  department = await get_actor_department(session, actor_id)
  if department is None:
    return False
  return capability.value in set(department.capabilities)


async def can_manage_task_templates(session: AsyncSession, actor: User) -> bool:
  ensure_active_user(actor)
  if is_management_role(actor):
    return True
  managed_department_ids = await get_effective_managed_department_ids(
    session,
    actor.id,
    scope_types=TASK_SCOPE_TYPES,
  )
  if managed_department_ids:
    return True
  return await has_department_capability(
    session,
    actor_id=actor.id,
    capability=DepartmentCapability.MANAGE_TEMPLATES,
  )


async def can_publish_org_tasks(session: AsyncSession, actor: User) -> bool:
  ensure_active_user(actor)
  if is_management_role(actor):
    return True
  managed_department_ids = await get_effective_managed_department_ids(
    session,
    actor.id,
    scope_types=TASK_SCOPE_TYPES,
  )
  if managed_department_ids:
    return True
  return await has_department_capability(
    session,
    actor_id=actor.id,
    capability=DepartmentCapability.PUBLISH_ORG_TASK,
  )


async def get_effective_report_user_ids(
  session: AsyncSession,
  actor_id: UUID,
  *,
  scope_types: set[DelegationScopeType] | None = None,
  target_date: date | None = None,
) -> set[UUID]:
  effective_date = target_date or date.today()
  reporting_lines = list(await session.scalars(select(ReportingLine)))
  result = {
    reporting_line.user_id
    for reporting_line in reporting_lines
    if reporting_line.manager_user_id == actor_id
    and _is_reporting_line_effective(reporting_line=reporting_line, target_date=effective_date)
  }

  delegations = await list_effective_delegations_for_delegate(
    session,
    delegate_user_id=actor_id,
    scope_types=scope_types or DATA_ACCESS_SCOPE_TYPES,
  )
  if not delegations:
    return result

  departments = await _list_departments(session)
  for delegation in delegations:
    scoped_ids = None
    if delegation.scope_department_id is not None:
      scoped_ids = _expand_department_ids(departments, root_ids={delegation.scope_department_id})

    for reporting_line in reporting_lines:
      if reporting_line.manager_user_id != delegation.delegator_user_id:
        continue
      if not _is_reporting_line_effective(reporting_line=reporting_line, target_date=effective_date):
        continue
      if scoped_ids is not None and reporting_line.department_id not in scoped_ids:
        continue
      result.add(reporting_line.user_id)
  return result


async def get_effective_reporting_line_types(
  session: AsyncSession,
  *,
  actor_id: UUID,
  user_id: UUID,
  scope_types: set[DelegationScopeType] | None = None,
  target_date: date | None = None,
) -> set[ReportingLineType]:
  effective_date = target_date or date.today()
  reporting_lines = list(await session.scalars(select(ReportingLine).where(ReportingLine.user_id == user_id)))
  line_types = {
    reporting_line.line_type
    for reporting_line in reporting_lines
    if reporting_line.manager_user_id == actor_id
    and _is_reporting_line_effective(reporting_line=reporting_line, target_date=effective_date)
  }

  delegations = await list_effective_delegations_for_delegate(
    session,
    delegate_user_id=actor_id,
    scope_types=scope_types or DATA_ACCESS_SCOPE_TYPES,
  )
  if not delegations:
    return line_types

  departments = await _list_departments(session)
  for delegation in delegations:
    scoped_ids = None
    if delegation.scope_department_id is not None:
      scoped_ids = _expand_department_ids(departments, root_ids={delegation.scope_department_id})

    for reporting_line in reporting_lines:
      if reporting_line.manager_user_id != delegation.delegator_user_id:
        continue
      if not _is_reporting_line_effective(reporting_line=reporting_line, target_date=effective_date):
        continue
      if scoped_ids is not None and reporting_line.department_id not in scoped_ids:
        continue
      line_types.add(reporting_line.line_type)
  return line_types


async def get_visible_department_ids(session: AsyncSession, actor: User) -> set[UUID] | None:
  ensure_active_user(actor)
  if is_management_role(actor):
    return None

  visible = await get_effective_managed_department_ids(session, actor.id)
  actor_department_id = await get_actor_department_id(session, actor.id)
  if actor_department_id is not None:
    visible.add(actor_department_id)
  return visible


async def ensure_department_stats_access(
  session: AsyncSession,
  actor: User,
  department_id: UUID,
) -> None:
  ensure_active_user(actor)
  if is_management_role(actor):
    return

  visible = await get_visible_department_ids(session, actor)
  if visible is not None and department_id not in visible:
    raise AuthorizationError("无权查看该部门统计。")


async def can_manage_assignee(session: AsyncSession, actor: User, assignee_id: UUID) -> bool:
  if is_management_role(actor):
    return True
  if actor.id == assignee_id:
    return True

  managed_department_ids = await get_effective_managed_department_ids(
    session,
    actor.id,
    scope_types=TASK_SCOPE_TYPES,
  )
  if not managed_department_ids:
    return False

  assignee_department_id = await get_actor_department_id(session, assignee_id)
  return assignee_department_id in managed_department_ids
