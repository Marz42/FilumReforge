"""Org-tree boundary CC for cross-department task routing (F-21 / F-27)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Department


async def _load_department_map(session: AsyncSession) -> dict[UUID, Department]:
  departments = list(await session.scalars(select(Department)))
  return {department.id: department for department in departments}


async def get_department_path_ids(session: AsyncSession, department_id: UUID) -> list[UUID]:
  """Root-to-leaf path for a department in the org tree."""
  department_map = await _load_department_map(session)
  path_ids: list[UUID] = []
  current_id: UUID | None = department_id
  while current_id is not None:
    department = department_map.get(current_id)
    if department is None:
      break
    path_ids.append(department.id)
    current_id = department.parent_id
  path_ids.reverse()
  return path_ids


def resolve_boundary_manager_cc_user_ids(
  *,
  departments: dict[UUID, Department],
  origin_path: list[UUID],
  target_path: list[UUID],
  exclude_user_ids: set[UUID] | None = None,
) -> list[UUID]:
  """Collect manager_id from departments on both branches below the LCA."""
  if not origin_path or not target_path:
    return []
  if origin_path[-1] == target_path[-1]:
    return []

  exclude = exclude_user_ids or set()
  lca_len = 0
  for origin_id, target_id in zip(origin_path, target_path, strict=False):
    if origin_id == target_id:
      lca_len += 1
    else:
      break

  cc_ids: list[UUID] = []
  seen: set[UUID] = set()

  def add_manager(department_id: UUID) -> None:
    department = departments.get(department_id)
    if department is None or department.manager_id is None:
      return
    manager_id = department.manager_id
    if manager_id in exclude or manager_id in seen:
      return
    seen.add(manager_id)
    cc_ids.append(manager_id)

  if lca_len > 0:
    add_manager(origin_path[lca_len - 1])
  for department_id in origin_path[lca_len:]:
    add_manager(department_id)
  for department_id in target_path[lca_len:]:
    add_manager(department_id)

  return cc_ids


async def resolve_cross_department_boundary_cc_user_ids(
  session: AsyncSession,
  *,
  origin_department_id: UUID | None,
  target_department_id: UUID | None,
  exclude_user_ids: set[UUID] | None = None,
) -> list[UUID]:
  if origin_department_id is None or target_department_id is None:
    return []
  if origin_department_id == target_department_id:
    return []

  department_map = await _load_department_map(session)
  origin_path = await get_department_path_ids(session, origin_department_id)
  target_path = await get_department_path_ids(session, target_department_id)
  return resolve_boundary_manager_cc_user_ids(
    departments=department_map,
    origin_path=origin_path,
    target_path=target_path,
    exclude_user_ids=exclude_user_ids,
  )
