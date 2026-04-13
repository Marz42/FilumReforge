from __future__ import annotations

from collections import defaultdict, deque
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole, UserStatus
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.models import Department, Profile, User

MANAGEMENT_ROLES = {UserRole.ADMIN, UserRole.HR}


def ensure_active_user(actor: User) -> None:
  if actor.status != UserStatus.ACTIVE:
    raise AuthenticationError("当前账号不可用。")


def ensure_management_role(actor: User) -> None:
  ensure_active_user(actor)
  if actor.role not in MANAGEMENT_ROLES:
    raise AuthorizationError("当前账号没有管理权限。")


async def get_actor_department_id(session: AsyncSession, actor_id: UUID) -> UUID | None:
  return await session.scalar(select(Profile.department_id).where(Profile.user_id == actor_id))


async def get_managed_department_ids(session: AsyncSession, actor_id: UUID) -> set[UUID]:
  departments = list(await session.scalars(select(Department)))
  managed_roots = {department.id for department in departments if department.manager_id == actor_id}
  if not managed_roots:
    return set()

  children_map: dict[UUID | None, list[UUID]] = defaultdict(list)
  for department in departments:
    children_map[department.parent_id].append(department.id)

  result = set(managed_roots)
  queue = deque(managed_roots)
  while queue:
    department_id = queue.popleft()
    for child_id in children_map.get(department_id, []):
      if child_id not in result:
        result.add(child_id)
        queue.append(child_id)
  return result


async def get_visible_department_ids(session: AsyncSession, actor: User) -> set[UUID] | None:
  ensure_active_user(actor)
  if actor.role in MANAGEMENT_ROLES:
    return None

  visible = await get_managed_department_ids(session, actor.id)
  actor_department_id = await get_actor_department_id(session, actor.id)
  if actor_department_id is not None:
    visible.add(actor_department_id)
  return visible


async def can_manage_assignee(session: AsyncSession, actor: User, assignee_id: UUID) -> bool:
  if actor.role in MANAGEMENT_ROLES:
    return True
  if actor.id == assignee_id:
    return True

  managed_department_ids = await get_managed_department_ids(session, actor.id)
  if not managed_department_ids:
    return False

  assignee_department_id = await get_actor_department_id(session, assignee_id)
  return assignee_department_id in managed_department_ids
