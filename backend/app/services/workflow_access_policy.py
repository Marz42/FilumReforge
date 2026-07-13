from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
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
  can_manage_task_templates,
  ensure_active_user,
  get_effective_managed_department_ids,
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
    if is_management_role(actor):
      return
    if not await can_manage_task_templates(self._session, actor):
      raise NotFoundError("工作流图模板不存在。")
    if template_id is None:
      return

    template = await self._session.get(WorkflowGraphTemplate, template_id)
    if template is None:
      raise NotFoundError("工作流图模板不存在。")
    if template.scope_mode == "departments":
      managed_department_ids = await get_effective_managed_department_ids(
        self._session,
        actor.id,
      )
      managed = {str(item) for item in managed_department_ids}
      scoped = {str(item) for item in (template.scope_department_ids or [])}
      if scoped and scoped.issubset(managed):
        return
    # Template designer/stats/run-list are management resources. Use 404 for reads.
    raise NotFoundError("工作流图模板不存在。")

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
