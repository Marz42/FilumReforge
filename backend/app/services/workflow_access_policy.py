from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DepartmentCapability, WorkflowGraphTemplateStatus
from app.core.exceptions import AuthorizationError, NotFoundError
from app.models import (
  Task,
  TaskWatcher,
  User,
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowNodeInstance,
  WorkflowRunEvent,
)
from app.services.access_control import (
  TASK_SCOPE_TYPES,
  can_manage_task_templates,
  ensure_active_user,
  get_actor_department_id,
  get_effective_managed_department_ids,
  get_effective_report_user_ids,
  has_department_capability,
  is_management_role,
)


class WorkflowAccessPolicy:
  """Central object-level read policy for workflow graph resources."""

  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def ensure_can_read_instance(
    self,
    *,
    actor: User,
    instance_id: UUID,
  ) -> WorkflowGraphInstance:
    ensure_active_user(actor)
    instance = await self._session.get(WorkflowGraphInstance, instance_id)
    if instance is None:
      raise NotFoundError("工作流图实例不存在。")

    if await self._can_read_instance(actor=actor, instance=instance):
      return instance
    # Object reads deliberately conceal whether the instance exists.
    raise NotFoundError("工作流图实例不存在。")

  async def ensure_can_manage_templates(
    self,
    *,
    actor: User,
    template_id: UUID | None = None,
  ) -> None:
    ensure_active_user(actor)
    if template_id is None:
      if is_management_role(actor) or await can_manage_task_templates(self._session, actor):
        return
      raise NotFoundError("工作流图模板不存在。")

    template = await self._session.get(WorkflowGraphTemplate, template_id)
    if template is not None and await self._can_manage_template(actor=actor, template=template):
      return

    # Template designer/stats/run-list are management resources. Use 404 for reads.
    raise NotFoundError("工作流图模板不存在。")

  async def ensure_can_read_template(
    self,
    *,
    actor: User,
    template_id: UUID,
  ) -> WorkflowGraphTemplate:
    ensure_active_user(actor)
    template = await self._session.get(WorkflowGraphTemplate, template_id)
    if template is None:
      raise NotFoundError("工作流图模板不存在。")
    if is_management_role(actor):
      return template
    if template.status != WorkflowGraphTemplateStatus.ACTIVE:
      if await self._can_manage_template(actor=actor, template=template):
        return template
      raise NotFoundError("工作流图模板不存在。")
    if template.scope_mode != "departments":
      return template

    accessible = await self._template_read_department_ids(actor=actor)
    scoped = {str(item) for item in (template.scope_department_ids or [])}
    if scoped and scoped.intersection(accessible):
      return template
    raise NotFoundError("工作流图模板不存在。")

  async def filter_readable_templates(
    self,
    *,
    actor: User,
    templates: list[WorkflowGraphTemplate],
  ) -> list[WorkflowGraphTemplate]:
    ensure_active_user(actor)
    if is_management_role(actor):
      return templates
    accessible = await self._template_read_department_ids(actor=actor)
    return [
      template
      for template in templates
      if template.scope_mode != "departments"
      or bool({str(item) for item in (template.scope_department_ids or [])}.intersection(accessible))
    ]

  async def filter_manageable_templates(
    self,
    *,
    actor: User,
    templates: list[WorkflowGraphTemplate],
  ) -> list[WorkflowGraphTemplate]:
    ensure_active_user(actor)
    if is_management_role(actor):
      return templates
    return [
      template
      for template in templates
      if await self._can_manage_template(actor=actor, template=template)
    ]

  async def ensure_can_assign_template_scope(
    self,
    *,
    actor: User,
    scope_mode: str,
    scope_department_ids: list[str],
  ) -> None:
    ensure_active_user(actor)
    if is_management_role(actor):
      return
    if not await can_manage_task_templates(self._session, actor):
      raise AuthorizationError("当前账号无权维护图模板。")
    if scope_mode != "departments":
      raise AuthorizationError("只有全局管理角色可以将模板设为全公司可用。")
    managed = await self._template_manage_department_ids(actor=actor)
    scoped = {str(item) for item in scope_department_ids}
    if not scoped or not scoped.issubset(managed):
      raise AuthorizationError("模板可用部门必须全部位于当前账号的有效管理范围内。")

  async def default_template_scope(self, *, actor: User) -> tuple[str, list[str]]:
    ensure_active_user(actor)
    if is_management_role(actor):
      return "global", []
    if not await can_manage_task_templates(self._session, actor):
      raise AuthorizationError("当前账号无权维护图模板。")
    managed = sorted(await self._template_manage_department_ids(actor=actor))
    if not managed:
      raise AuthorizationError("当前账号没有可用于创建模板的有效管理部门。")
    return "departments", managed

  async def ensure_can_compute_notice_candidates(
    self,
    *,
    actor: User,
    initiator_user_id: UUID,
    target_user_id: UUID,
  ) -> None:
    ensure_active_user(actor)
    # The payload initiator is business input, not an authorization claim.
    _ = initiator_user_id
    if is_management_role(actor) or actor.id == target_user_id:
      return
    target_department_id = await get_actor_department_id(self._session, target_user_id)
    managed = await get_effective_managed_department_ids(self._session, actor.id)
    if target_department_id is not None and target_department_id in managed:
      return
    report_user_ids = await get_effective_report_user_ids(self._session, actor.id)
    if target_user_id in report_user_ids:
      return
    raise NotFoundError("无法计算通知候选人。")

  async def _can_manage_template(
    self,
    *,
    actor: User,
    template: WorkflowGraphTemplate,
  ) -> bool:
    if is_management_role(actor):
      return True
    if not await can_manage_task_templates(self._session, actor):
      return False
    if template.scope_mode != "departments":
      return False
    managed = await self._template_manage_department_ids(actor=actor)
    scoped = {str(item) for item in (template.scope_department_ids or [])}
    return bool(scoped) and scoped.issubset(managed)

  async def _template_read_department_ids(self, *, actor: User) -> set[str]:
    department_ids = {
      str(item)
      for item in await get_effective_managed_department_ids(self._session, actor.id)
    }
    actor_department_id = await get_actor_department_id(self._session, actor.id)
    if actor_department_id is not None:
      department_ids.add(str(actor_department_id))
    return department_ids

  async def _template_manage_department_ids(self, *, actor: User) -> set[str]:
    department_ids = {
      str(item)
      for item in await get_effective_managed_department_ids(
        self._session,
        actor.id,
        scope_types=TASK_SCOPE_TYPES,
      )
    }
    if await has_department_capability(
      self._session,
      actor_id=actor.id,
      capability=DepartmentCapability.MANAGE_TEMPLATES,
    ):
      actor_department_id = await get_actor_department_id(self._session, actor.id)
      if actor_department_id is not None:
        department_ids.add(str(actor_department_id))
    return department_ids

  async def _can_read_instance(
    self,
    *,
    actor: User,
    instance: WorkflowGraphInstance,
  ) -> bool:
    if is_management_role(actor):
      return True
    if instance.initiator_user_id == actor.id:
      return True

    participant_exists = await self._session.scalar(
      select(WorkflowNodeInstance.id)
      .where(
        WorkflowNodeInstance.instance_id == instance.id,
        WorkflowNodeInstance.assignee_user_id == actor.id,
      )
      .limit(1)
    )
    if participant_exists is not None:
      return True

    historical_actor_exists = await self._session.scalar(
      select(WorkflowRunEvent.id)
      .where(
        WorkflowRunEvent.instance_id == instance.id,
        WorkflowRunEvent.actor_user_id == actor.id,
      )
      .limit(1)
    )
    if historical_actor_exists is not None:
      return True

    if instance.department_id is not None:
      managed_department_ids = await get_effective_managed_department_ids(
        self._session,
        actor.id,
      )
      if instance.department_id in managed_department_ids:
        return True

    return await self._is_formal_watcher(actor_id=actor.id, instance=instance)

  async def _is_formal_watcher(
    self,
    *,
    actor_id: UUID,
    instance: WorkflowGraphInstance,
  ) -> bool:
    task_conditions = [
      Task.extra_metadata["workflow_graph_instance_id"].as_string() == str(instance.id),
    ]
    if instance.source_id is not None:
      task_conditions.append(Task.id == instance.source_id)

    watcher_exists = await self._session.scalar(
      select(TaskWatcher.id)
      .join(Task, Task.id == TaskWatcher.task_id)
      .where(
        TaskWatcher.user_id == actor_id,
        or_(*task_conditions),
      )
      .limit(1)
    )
    return watcher_exists is not None
