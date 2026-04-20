from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DepartmentCapability
from app.core.exceptions import ConflictError, NotFoundError
from app.models import Department, User
from app.services.access_control import ensure_active_user, ensure_management_role, get_visible_department_ids


class DepartmentService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def list_departments(self, *, actor: User) -> list[Department]:
    ensure_active_user(actor)
    visible_department_ids = await get_visible_department_ids(self._session, actor)
    statement = select(Department).order_by(Department.sort_order.asc(), Department.name.asc())
    if visible_department_ids is not None:
      if not visible_department_ids:
        return []
      statement = statement.where(Department.id.in_(visible_department_ids))
    result = await self._session.scalars(statement)
    return list(result)

  async def get_department(self, *, actor: User, department_id: UUID) -> Department:
    departments = await self.list_departments(actor=actor)
    for department in departments:
      if department.id == department_id:
        return department
    raise NotFoundError("部门不存在。")

  async def create_department(
    self,
    *,
    actor: User,
    name: str,
    code: str,
    parent_id: UUID | None = None,
    manager_id: UUID | None = None,
    sort_order: int = 0,
    capabilities: list[DepartmentCapability] | None = None,
  ) -> Department:
    ensure_management_role(actor)

    existing_department = await self._session.scalar(select(Department).where(Department.code == code))
    if existing_department is not None:
      raise ConflictError("部门编码已存在。")

    if parent_id is not None and await self._session.get(Department, parent_id) is None:
      raise NotFoundError("父级部门不存在。")
    if manager_id is not None and await self._session.get(User, manager_id) is None:
      raise NotFoundError("部门负责人不存在。")

    department = Department(
      name=name,
      code=code,
      parent_id=parent_id,
      manager_id=manager_id,
      sort_order=sort_order,
      capabilities=[capability.value for capability in capabilities or []],
    )
    self._session.add(department)
    await self._session.commit()
    await self._session.refresh(department)
    return department

  async def update_department(
    self,
    *,
    actor: User,
    department_id: UUID,
    name: str | None = None,
    code: str | None = None,
    parent_id: UUID | None = None,
    manager_id: UUID | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
    capabilities: list[DepartmentCapability] | None = None,
  ) -> Department:
    ensure_management_role(actor)
    department = await self._session.get(Department, department_id)
    if department is None:
      raise NotFoundError("部门不存在。")

    if code is not None and code != department.code:
      existing_department = await self._session.scalar(select(Department).where(Department.code == code))
      if existing_department is not None:
        raise ConflictError("部门编码已存在。")
      department.code = code

    if parent_id is not None:
      if await self._session.get(Department, parent_id) is None:
        raise NotFoundError("父级部门不存在。")
      department.parent_id = parent_id
    if manager_id is not None:
      if await self._session.get(User, manager_id) is None:
        raise NotFoundError("部门负责人不存在。")
      department.manager_id = manager_id
    if name is not None:
      department.name = name
    if sort_order is not None:
      department.sort_order = sort_order
    if is_active is not None:
      department.is_active = is_active
    if capabilities is not None:
      department.capabilities = [capability.value for capability in capabilities]

    await self._session.commit()
    await self._session.refresh(department)
    return department

  @staticmethod
  def build_tree(departments: list[Department]) -> list[dict[str, Any]]:
    children_map: dict[UUID | None, list[Department]] = defaultdict(list)
    for department in departments:
      children_map[department.parent_id].append(department)

    def serialize(node: Department) -> dict[str, Any]:
      return {
        "id": str(node.id),
        "name": node.name,
        "code": node.code,
        "parent_id": str(node.parent_id) if node.parent_id else None,
        "manager_id": str(node.manager_id) if node.manager_id else None,
        "sort_order": node.sort_order,
        "is_active": node.is_active,
        "capabilities": list(node.capabilities),
        "children": [serialize(child) for child in children_map.get(node.id, [])],
      }

    roots = sorted(children_map.get(None, []), key=lambda item: (item.sort_order, item.name))
    return [serialize(root) for root in roots]
