from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DepartmentCapability
from app.core.exceptions import ConflictError, NotFoundError
from app.models import Delegation, Department, Profile, ProfilePosition, ReportingLine, Task, User
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
    fields_set: set[str] | None = None,
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

    updated_fields = fields_set or {
      field_name
      for field_name, value in {
        "name": name,
        "code": code,
        "parent_id": parent_id,
        "manager_id": manager_id,
        "sort_order": sort_order,
        "is_active": is_active,
        "capabilities": capabilities,
      }.items()
      if value is not None
    }
    is_root_department = department.code == "root"

    if "name" in updated_fields:
      if name is None:
        raise ConflictError("部门名称不能为空。")
      department.name = name

    if "code" in updated_fields:
      if code is None:
        raise ConflictError("部门编码不能为空。")
      if is_root_department and code != department.code:
        raise ConflictError("公司根节点编码不允许修改。")
      if code != department.code:
        existing_department = await self._session.scalar(select(Department).where(Department.code == code))
        if existing_department is not None:
          raise ConflictError("部门编码已存在。")
        department.code = code

    if "parent_id" in updated_fields:
      if is_root_department and parent_id is not None:
        raise ConflictError("公司根节点不能设置上级部门。")
      if parent_id == department.id:
        raise ConflictError("部门不能设置自己为上级部门。")
      if parent_id is not None:
        parent_department = await self._session.get(Department, parent_id)
        if parent_department is None:
          raise NotFoundError("父级部门不存在。")
        current_parent = parent_department
        while current_parent is not None:
          if current_parent.id == department.id:
            raise ConflictError("不能把部门移动到自己的下级部门下。")
          if current_parent.parent_id is None:
            break
          current_parent = await self._session.get(Department, current_parent.parent_id)
      department.parent_id = parent_id

    if "manager_id" in updated_fields:
      if manager_id is not None and await self._session.get(User, manager_id) is None:
        raise NotFoundError("部门负责人不存在。")
      department.manager_id = manager_id

    if "sort_order" in updated_fields and sort_order is not None:
      department.sort_order = sort_order

    if "is_active" in updated_fields:
      if is_active is None:
        raise ConflictError("部门状态不能为空。")
      if is_root_department and not is_active:
        raise ConflictError("公司根节点不允许停用。")
      department.is_active = is_active

    if "capabilities" in updated_fields:
      department.capabilities = [capability.value for capability in capabilities or []]

    await self._session.commit()
    await self._session.refresh(department)
    return department

  async def delete_department(self, *, actor: User, department_id: UUID) -> None:
    ensure_management_role(actor)
    department = await self._session.get(Department, department_id)
    if department is None:
      raise NotFoundError("部门不存在。")
    if department.code == "root":
      raise ConflictError("公司根节点不允许删除。")

    child_count = await self._session.scalar(
      select(func.count()).select_from(Department).where(Department.parent_id == department_id)
    )
    if child_count:
      raise ConflictError("部门下仍存在子部门，无法删除。")

    blocking_relations = (
      (Profile, Profile.department_id, "部门下仍有关联档案，无法删除。"),
      (ProfilePosition, ProfilePosition.department_id, "部门下仍有关联任职记录，无法删除。"),
      (ReportingLine, ReportingLine.department_id, "部门下仍有关联汇报线，无法删除。"),
      (Delegation, Delegation.scope_department_id, "部门下仍有关联授权范围，无法删除。"),
      (Task, Task.department_id, "部门下仍有关联任务，无法删除。"),
    )
    for model, column, message in blocking_relations:
      relation_count = await self._session.scalar(
        select(func.count()).select_from(model).where(column == department_id)
      )
      if relation_count:
        raise ConflictError(message)

    await self._session.delete(department)
    await self._session.commit()

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
