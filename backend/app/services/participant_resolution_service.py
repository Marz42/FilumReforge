"""Resolve participant policies for video workflow v1 (W2)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import UserStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.models import Profile, User, WorkflowGraphInstance, WorkflowGraphTemplate
from app.schemas.workflow_video import ParticipantPolicyDefinition, ParticipantsSnapshotEntry
from app.services.access_control import (
  ensure_active_user,
  expand_department_ids,
  get_actor_department_id,
  get_effective_managed_department_ids,
)
from app.services.workflow_rule_resolver import (
  _load_users,
  parse_uuid_value,
  resolve_actor_department_id,
  resolve_user_targets_from_rule,
)


class ParticipantResolutionService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def get_template_or_raise(self, template_id: UUID) -> WorkflowGraphTemplate:
    template = await self._session.get(WorkflowGraphTemplate, template_id)
    if template is None:
      raise NotFoundError("图模板不存在。")
    return template

  async def _load_users_with_profiles(self, *, user_ids: list[UUID]) -> list[User]:
    if not user_ids:
      return []
    users = list(
      await self._session.scalars(
        select(User)
        .options(selectinload(User.profile))
        .where(User.id.in_(user_ids))
      )
    )
    user_map = {user.id: user for user in users}
    return [user_map[user_id] for user_id in user_ids if user_id in user_map]

  @staticmethod
  def _policy_from_template(template: WorkflowGraphTemplate, policy_ref: str) -> ParticipantPolicyDefinition:
    config = template.config or {}
    policies = config.get("participant_policies")
    if not isinstance(policies, dict):
      raise NotFoundError(f"模板未配置参与者策略：{policy_ref}")
    raw_policy = policies.get(policy_ref)
    if not isinstance(raw_policy, dict):
      raise NotFoundError(f"模板未配置参与者策略：{policy_ref}")
    return ParticipantPolicyDefinition.model_validate(raw_policy)

  async def resolve_policy(
    self,
    *,
    actor: User,
    policy: ParticipantPolicyDefinition,
    policy_ref: str,
    department_id: UUID | None = None,
    mode: str = "all",
    selected_user_ids: list[UUID] | None = None,
  ) -> list[User]:
    ensure_active_user(actor)
    normalized_mode = mode if mode in {"all", "subset"} else "all"

    if policy.type != "department_members":
      raise ConflictError(f"暂不支持的参与者策略类型：{policy.type}")

    if policy.scope == "template_department":
      resolved_department_id = policy.department_id or department_id
    else:
      resolved_department_id = department_id or policy.department_id
    if resolved_department_id is None:
      resolved_department_id = await resolve_actor_department_id(
        self._session,
        actor_id=actor.id,
        requested_department_id=None,
      )
    if resolved_department_id is None:
      raise ConflictError(f"策略 {policy_ref} 需要明确部门。")

    candidates = await resolve_user_targets_from_rule(
      self._session,
      actor=actor,
      assignee_rule={
        "type": "department_members",
        "department_id": str(resolved_department_id),
      },
      department_id=resolved_department_id,
      allow_multiple=True,
    )
    candidate_ids = {user.id for user in candidates}

    if normalized_mode == "all":
      return candidates

    if not selected_user_ids:
      raise ConflictError("subset 模式必须提供至少一名参与人。")

    filtered_ids = [user_id for user_id in selected_user_ids if user_id in candidate_ids]
    if not filtered_ids:
      raise ConflictError("所选参与人不在该策略允许的部门成员范围内。")
    return await _load_users(self._session, user_ids=filtered_ids)

  async def resolve_policy_for_template(
    self,
    *,
    actor: User,
    template: WorkflowGraphTemplate,
    policy_ref: str,
    department_id: UUID | None = None,
    mode: str = "all",
    selected_user_ids: list[UUID] | None = None,
  ) -> list[User]:
    policy = self._policy_from_template(template, policy_ref)
    return await self.resolve_policy(
      actor=actor,
      policy=policy,
      policy_ref=policy_ref,
      department_id=department_id,
      mode=mode,
      selected_user_ids=selected_user_ids,
    )

  @staticmethod
  def build_snapshot_entry(
    *,
    users: list[User],
    mode: str,
  ) -> ParticipantsSnapshotEntry:
    normalized_mode = "subset" if mode == "subset" else "all"
    return ParticipantsSnapshotEntry(
      mode=normalized_mode,
      user_ids=[user.id for user in users],
    )

  async def list_managed_department_member_options(self, *, actor: User) -> list[User]:
    """Active users in managed departments and the actor's own department subtree (launch manager picker)."""
    ensure_active_user(actor)
    department_ids = set(await get_effective_managed_department_ids(self._session, actor.id))
    actor_department_id = await get_actor_department_id(self._session, actor.id)
    if actor_department_id is not None:
      department_ids |= await expand_department_ids(self._session, {actor_department_id})
    if not department_ids:
      return []

    users = list(
      await self._session.scalars(
        select(User)
        .join(Profile, Profile.user_id == User.id)
        .options(selectinload(User.profile))
        .where(
          User.status == UserStatus.ACTIVE,
          Profile.department_id.in_(department_ids),
        )
        .order_by(Profile.real_name.asc().nulls_last(), User.email.asc())
      )
    )
    return users

  async def list_department_pool_member_options(
    self,
    *,
    actor: User,
    template: WorkflowGraphTemplate,
    pool_key: str,
    instance: WorkflowGraphInstance | None = None,
  ) -> list[User]:
    """Active members of a template department pool (capture user pickers)."""
    from app.services.workflow_assignee_resolver import resolve_department_pools

    ensure_active_user(actor)
    context = instance.context if instance is not None and isinstance(instance.context, dict) else None
    pools = resolve_department_pools(template, context)
    normalized_key = pool_key.strip()
    if normalized_key not in pools:
      raise NotFoundError(f"模板未配置部门池：{normalized_key}")

    members = await resolve_user_targets_from_rule(
      self._session,
      actor=actor,
      assignee_rule={"type": "department_members", "department_id": str(pools[normalized_key])},
      department_id=pools[normalized_key],
      allow_multiple=True,
    )
    return await self._load_users_with_profiles(user_ids=[user.id for user in members])

  async def preview_for_template(
    self,
    *,
    actor: User,
    template: WorkflowGraphTemplate,
    policy_ref: str,
    department_id: UUID | None = None,
    mode: str = "all",
    selected_user_ids: list[UUID] | None = None,
  ) -> tuple[ParticipantsSnapshotEntry, list[User]]:
    users = await self.resolve_policy_for_template(
      actor=actor,
      template=template,
      policy_ref=policy_ref,
      department_id=department_id,
      mode=mode,
      selected_user_ids=selected_user_ids,
    )
    users = await self._load_users_with_profiles(user_ids=[user.id for user in users])
    entry = self.build_snapshot_entry(users=users, mode=mode)
    return entry, users


async def resolve_assignee_from_rule(
  session: AsyncSession,
  *,
  actor: User,
  assignee_rule: dict[str, object] | None,
  department_id: UUID | None = None,
  allow_multiple: bool = False,
  context: dict[str, Any] | None = None,
  department_pools: dict[str, UUID] | None = None,
) -> list[User]:
  """Wrapper used by graph orchestration; delegates to workflow_rule_resolver."""
  return await resolve_user_targets_from_rule(
    session,
    actor=actor,
    assignee_rule=assignee_rule,
    department_id=department_id,
    allow_multiple=allow_multiple,
    context=context,
    department_pools=department_pools,
  )
