from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models import Department, Profile, User
from app.services.access_control import ensure_active_user


def parse_uuid_value(value: str | UUID | None, *, field_name: str) -> UUID:
  if isinstance(value, UUID):
    return value
  if value is None:
    raise ConflictError(f"{field_name} 不能为空。")
  try:
    return UUID(str(value))
  except ValueError as exc:  # pragma: no cover - defensive branch
    raise ConflictError(f"{field_name} 不是合法的 UUID。") from exc


async def resolve_actor_department_id(
  session: AsyncSession,
  *,
  actor_id: UUID,
  requested_department_id: UUID | None = None,
) -> UUID | None:
  if requested_department_id is not None:
    if await session.get(Department, requested_department_id) is None:
      raise NotFoundError("所属部门不存在。")
    return requested_department_id

  return await session.scalar(select(Profile.department_id).where(Profile.user_id == actor_id))


async def _load_users(
  session: AsyncSession,
  *,
  user_ids: list[UUID],
) -> list[User]:
  unique_ids = list(dict.fromkeys(user_ids))
  if not unique_ids:
    raise ConflictError("步骤负责人不能为空。")

  users = list(await session.scalars(select(User).where(User.id.in_(unique_ids))))
  if len(users) != len(unique_ids):
    raise NotFoundError("步骤负责人不存在。")

  user_map = {user.id: user for user in users}
  ordered_users: list[User] = []
  for user_id in unique_ids:
    user = user_map[user_id]
    ensure_active_user(user)
    ordered_users.append(user)
  return ordered_users


async def resolve_user_targets_from_rule(
  session: AsyncSession,
  *,
  actor: User,
  assignee_rule: dict[str, object] | None,
  department_id: UUID | None = None,
  allow_multiple: bool = False,
  context: dict[str, Any] | None = None,
  department_pools: dict[str, UUID] | None = None,
) -> list[User]:
  if not assignee_rule:
    return [actor]

  rule_type = str(assignee_rule.get("type") or "initiator")
  user_ids: list[UUID]

  if rule_type == "initiator":
    return [actor]

  if rule_type == "user":
    user_ids = [parse_uuid_value(assignee_rule.get("user_id"), field_name="user_id")]
  elif rule_type == "user_ids":
    raw_user_ids = assignee_rule.get("user_ids")
    if not isinstance(raw_user_ids, list) or not raw_user_ids:
      raise ConflictError("user_ids 规则至少要包含一个用户。")
    user_ids = [parse_uuid_value(raw_user_id, field_name="user_ids") for raw_user_id in raw_user_ids]
  elif rule_type == "department_manager":
    target_department_id = assignee_rule.get("department_id")
    resolved_department_id = (
      parse_uuid_value(target_department_id, field_name="department_id")
      if target_department_id is not None
      else department_id
    )
    if resolved_department_id is None:
      raise ConflictError("department_manager 规则需要明确部门。")
    department = await session.get(Department, resolved_department_id)
    if department is None or department.manager_id is None:
      raise ConflictError("目标部门尚未配置负责人。")
    user_ids = [department.manager_id]
  elif rule_type == "department_members":
    target_department_id = assignee_rule.get("department_id")
    resolved_department_id = (
      parse_uuid_value(target_department_id, field_name="department_id")
      if target_department_id is not None
      else department_id
    )
    if resolved_department_id is None:
      raise ConflictError("department_members 规则需要明确部门。")
    member_user_ids = list(await session.scalars(
      select(Profile.user_id).where(Profile.department_id == resolved_department_id)
    ))
    if not member_user_ids:
      raise ConflictError("目标部门没有成员。")
    return await _load_users(session, user_ids=member_user_ids)
  elif rule_type == "context_var":
    if context is None:
      raise ConflictError("context_var 规则需要运行上下文。")
    var_name = str(assignee_rule.get("var") or "").strip()
    if not var_name:
      raise ConflictError("context_var 规则必须指定 var。")
    raw_value = context.get(var_name)
    if raw_value is None:
      raise ConflictError(f"运行上下文中缺少变量：{var_name}")
    user_ids = [parse_uuid_value(raw_value, field_name=var_name)]
  elif rule_type == "department_pool":
    pool_key = str(assignee_rule.get("pool_key") or "").strip()
    inline_department_id = assignee_rule.get("department_id")
    resolved_department_id: UUID | None
    if inline_department_id is not None:
      resolved_department_id = parse_uuid_value(inline_department_id, field_name="department_id")
    elif pool_key and department_pools and pool_key in department_pools:
      resolved_department_id = department_pools[pool_key]
    else:
      raise ConflictError("department_pool 规则需要 department_id 或已注册的 pool_key。")
    assignee_role = str(assignee_rule.get("assignee_role") or "manager")
    if assignee_role == "manager":
      return await resolve_user_targets_from_rule(
        session,
        actor=actor,
        assignee_rule={"type": "department_manager", "department_id": str(resolved_department_id)},
        department_id=resolved_department_id,
        allow_multiple=False,
        context=context,
        department_pools=department_pools,
      )
    if assignee_role in {"member", "members"}:
      members = await resolve_user_targets_from_rule(
        session,
        actor=actor,
        assignee_rule={"type": "department_members", "department_id": str(resolved_department_id)},
        department_id=resolved_department_id,
        allow_multiple=True,
        context=context,
        department_pools=department_pools,
      )
      if assignee_role == "member":
        if not members:
          raise ConflictError("目标部门没有成员。")
        return [members[0]]
      return members
    raise ConflictError(f"暂不支持的 department_pool assignee_role：{assignee_role}")
  else:
    raise ConflictError(f"暂不支持的步骤负责人规则：{rule_type}")

  if not allow_multiple and len(user_ids) != 1:
    raise ConflictError("当前场景只允许单一负责人。")
  return await _load_users(session, user_ids=user_ids)
