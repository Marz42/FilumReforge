"""Video workflow v1 orchestration hooks (W4)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
  TaskDetailUiProfile,
  TaskPriority,
  TaskSourceType,
  TaskStatus,
  WorkflowGraphInstanceStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.models import (
  Profile,
  Task,
  User,
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateNode,
  WorkflowNodeInstance,
)
from app.schemas.workflow_video import validate_node_config
from app.services.task_service import TaskService
from app.services.workflow_assignee_resolver import resolve_node_assignee_id
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_node_config_helpers import resolve_completion_policy
from app.services.workflow_projection_department import resolve_projection_department_id


DEFAULT_AGGREGATE_NODE_KEY = "N2_AGGREGATE"


class WorkflowOrchestrationService:
  def __init__(
    self,
    session: AsyncSession,
    *,
    workflow_graph_service: WorkflowGraphService | None = None,
    task_service: TaskService | None = None,
  ) -> None:
    self._session = session
    self._workflow_graph_service = workflow_graph_service or WorkflowGraphService(session)
    self._task_service = task_service

  @staticmethod
  def _task_id_from_node_config(node_instance: WorkflowNodeInstance) -> UUID | None:
    config = node_instance.config if isinstance(node_instance.config, dict) else {}
    raw_task_id = config.get("task_id")
    if raw_task_id is None:
      return None
    return UUID(str(raw_task_id))

  async def _load_template(self, *, instance: WorkflowGraphInstance) -> WorkflowGraphTemplate | None:
    if instance.template_id is None:
      return None
    return await self._session.get(WorkflowGraphTemplate, instance.template_id)

  async def _load_template_node(
    self,
    *,
    node_instance: WorkflowNodeInstance,
  ) -> WorkflowGraphTemplateNode | None:
    if node_instance.template_node_id is None:
      return None
    return await self._session.get(WorkflowGraphTemplateNode, node_instance.template_node_id)

  async def _apply_review_projection_state(
    self,
    *,
    instance: WorkflowGraphInstance,
    node_instance: WorkflowNodeInstance,
    task: Task,
    template_node: WorkflowGraphTemplateNode | None,
  ) -> None:
    """Review nodes activated after upstream deliverable should enter REVIEW immediately."""
    if resolve_completion_policy(node_instance=node_instance, template_node=template_node) != "on_review_approved":
      return

    now = datetime.now(UTC)
    task.status = TaskStatus.REVIEW
    task.completed_at = None
    task.updated_at = now
    node_instance.engine_state = WorkflowNodeEngineState.ACKNOWLEDGED
    node_instance.business_state = WorkflowNodeBusinessState.PENDING_REVIEW
    node_instance.acknowledged_at = node_instance.acknowledged_at or now
    node_instance.completed_at = None

    if instance.source_id is None:
      return
    root_task = await self._session.get(Task, instance.source_id)
    if root_task is None:
      return
    root_task.status = TaskStatus.REVIEW
    root_task.completed_at = None
    root_task.updated_at = now

  async def _create_projection_task(
    self,
    *,
    actor: User,
    template: WorkflowGraphTemplate,
    instance: WorkflowGraphInstance,
    node_instance: WorkflowNodeInstance,
  ) -> Task:
    title = f"{template.name} / {node_instance.title}"
    metadata: dict[str, object] = {
      "workflow_graph_instance_id": str(instance.id),
      "workflow_node_instance_id": str(node_instance.id),
      "template_id": str(template.id),
      "template_code": template.code,
      "template_node_key": node_instance.node_key,
      "template_node_instance_key": node_instance.instance_key,
      "run_kind": (instance.context or {}).get("run_kind"),
    }
    node_config = node_instance.config if isinstance(node_instance.config, dict) else {}
    raw_profile = node_config.get("ui_profile")
    if not isinstance(raw_profile, str) or not raw_profile.strip():
      if node_instance.template_node_id is not None:
        template_node = await self._session.get(
          WorkflowGraphTemplateNode,
          node_instance.template_node_id,
        )
        if template_node is not None and isinstance(template_node.config, dict):
          raw_profile = template_node.config.get("ui_profile")
    if isinstance(raw_profile, str) and raw_profile.strip():
      try:
        metadata["ui_profile"] = TaskDetailUiProfile(raw_profile.strip()).value
      except ValueError:
        pass
    if node_config.get("handshake_required"):
      metadata["workflow_handshake_state"] = "assigned"
      metadata["latest_handshake_action"] = "assigned"

    assignee_id = node_instance.assignee_user_id or actor.id
    projection_department_id = instance.department_id
    if self._task_service is not None:
      task, _assignee = await self._task_service.create_task_record(
        actor=actor,
        title=title,
        assignee_id=assignee_id,
        department_id=await resolve_projection_department_id(
          self._session,
          instance=instance,
          assignee_id=assignee_id,
        ),
        source_type=TaskSourceType.TEMPLATE,
        extra_metadata=metadata,
        commit=False,
        skip_assignee_permission=True,
        skip_publish_permission=True,
      )
      if task.status != TaskStatus.DOING:
        task.status = TaskStatus.DOING
      template_node = await self._load_template_node(node_instance=node_instance)
      await self._apply_review_projection_state(
        instance=instance,
        node_instance=node_instance,
        task=task,
        template_node=template_node,
      )
      return task

    resolved_department_id = await self._session.scalar(
      select(Profile.department_id).where(Profile.user_id == assignee_id)
    )
    task = Task(
      title=title,
      creator_id=actor.id,
      assignee_id=assignee_id,
      department_id=resolved_department_id,
      status=TaskStatus.TODO if node_config.get("handshake_required") else TaskStatus.DOING,
      priority=TaskPriority.MEDIUM,
      source_type=TaskSourceType.TEMPLATE,
      extra_metadata=metadata,
    )
    self._session.add(task)
    await self._session.flush()
    template_node = await self._load_template_node(node_instance=node_instance)
    await self._apply_review_projection_state(
      instance=instance,
      node_instance=node_instance,
      task=task,
      template_node=template_node,
    )
    await self._session.flush()
    return task

  async def ensure_projection_tasks(
    self,
    *,
    actor: User,
    instance: WorkflowGraphInstance,
    node_instances: list[WorkflowNodeInstance],
  ) -> list[Task]:
    template = await self._load_template(instance=instance)
    if template is None:
      return []

    created: list[Task] = []
    for node_instance in node_instances:
      if node_instance.engine_state != WorkflowNodeEngineState.ACTIVATED:
        continue
      if self._task_id_from_node_config(node_instance) is not None:
        continue
      await self.resolve_and_bind_assignee(
        actor=actor,
        template=template,
        instance=instance,
        node_instance=node_instance,
      )
      task = await self._create_projection_task(
        actor=actor,
        template=template,
        instance=instance,
        node_instance=node_instance,
      )
      node_instance.config = {
        **dict(node_instance.config or {}),
        "task_id": str(task.id),
      }
      if node_instance.business_state == WorkflowNodeBusinessState.ASSIGNED:
        node_instance.business_state = WorkflowNodeBusinessState.DOING
      created.append(task)
    if created:
      await self._workflow_graph_service.enqueue_node_activated_notifications(
        instance=instance,
        node_instances=node_instances,
      )
    await self._session.flush()
    return created

  async def resolve_and_bind_assignee(
    self,
    *,
    actor: User,
    template: WorkflowGraphTemplate,
    instance: WorkflowGraphInstance,
    node_instance: WorkflowNodeInstance,
  ) -> None:
    if node_instance.assignee_user_id is not None:
      return
    template_node = None
    if node_instance.template_node_id is not None:
      template_node = await self._session.get(
        WorkflowGraphTemplateNode,
        node_instance.template_node_id,
      )
    if template_node is None:
      return
    context = instance.context if isinstance(instance.context, dict) else {}
    node_instance.assignee_user_id = await resolve_node_assignee_id(
      self._session,
      actor=actor,
      template=template,
      template_node=template_node,
      node_instance=node_instance,
      context=context,
      department_id=instance.department_id,
    )
    await self._session.flush()

  async def after_node_completed(
    self,
    *,
    actor: User,
    task: Task,
    instance: WorkflowGraphInstance,
    node_instance: WorkflowNodeInstance,
  ) -> list[Task]:
    """Advance downstream nodes after a template graph node reaches COMPLETED."""
    newly_activated = await self._workflow_graph_service.progress_from_completed_node(
      node_instance_id=node_instance.id,
    )
    if newly_activated:
      template = await self._load_template(instance=instance)
      if template is not None:
        for activated in newly_activated:
          await self.resolve_and_bind_assignee(
            actor=actor,
            template=template,
            instance=instance,
            node_instance=activated,
          )
      instance.current_node_key = newly_activated[0].node_key
    return await self.ensure_projection_tasks(
      actor=actor,
      instance=instance,
      node_instances=newly_activated,
    )

  async def after_capture_submitted(
    self,
    *,
    actor: User,
    task: Task,
    instance: WorkflowGraphInstance,
    node_instance: WorkflowNodeInstance,
  ) -> list[Task]:
    """on_capture_submitted: complete gate + all-of activation + projection tasks."""
    return await self.after_node_completed(
      actor=actor,
      task=task,
      instance=instance,
      node_instance=node_instance,
    )

  async def after_aggregate_confirmed(
    self,
    *,
    actor: User,
    instance: WorkflowGraphInstance,
    aggregate_node_key: str = DEFAULT_AGGREGATE_NODE_KEY,
  ) -> None:
    """on_aggregate_confirmed: sync aggregate tasks; WFK fork deferred to WFK phase."""
    aggregate_nodes = list(
      await self._session.scalars(
        select(WorkflowNodeInstance).where(
          WorkflowNodeInstance.instance_id == instance.id,
          WorkflowNodeInstance.node_key == aggregate_node_key,
        )
      )
    )
    now = datetime.now(UTC)
    for node_instance in aggregate_nodes:
      if node_instance.engine_state != WorkflowNodeEngineState.COMPLETED:
        node_instance.engine_state = WorkflowNodeEngineState.COMPLETED
        node_instance.business_state = WorkflowNodeBusinessState.DONE
        node_instance.completed_at = now

      task_id = self._task_id_from_node_config(node_instance)
      if task_id is None:
        continue
      aggregate_task = await self._session.get(Task, task_id)
      if aggregate_task is None:
        continue
      aggregate_task.status = TaskStatus.DONE
      aggregate_task.completed_at = now
      aggregate_task.updated_at = now
      metadata = dict(aggregate_task.extra_metadata or {})
      metadata["aggregate_confirmed_at"] = now.isoformat()
      aggregate_task.extra_metadata = metadata

    if instance.status == WorkflowGraphInstanceStatus.ACTIVE:
      downstream_pending = await self._session.scalar(
        select(WorkflowNodeInstance.id)
        .where(
          WorkflowNodeInstance.instance_id == instance.id,
          WorkflowNodeInstance.engine_state.in_(
            [
              WorkflowNodeEngineState.PENDING,
              WorkflowNodeEngineState.ACTIVATED,
              WorkflowNodeEngineState.ACKNOWLEDGED,
            ]
          ),
        )
        .limit(1)
      )
      if downstream_pending is None:
        instance.status = WorkflowGraphInstanceStatus.COMPLETED
        instance.completed_at = now

    await self._session.flush()

  async def on_task_accepted(self, *, actor: User, task: Task) -> None:
    """Handshake acceptance for template graph projection tasks (W4-3)."""
    metadata = dict(task.extra_metadata or {})
    node_id = metadata.get("workflow_node_instance_id")
    if node_id is None:
      return

    node_instance = await self._session.get(WorkflowNodeInstance, UUID(str(node_id)))
    if node_instance is None:
      return

    node_config_raw = node_instance.config if isinstance(node_instance.config, dict) else {}
    try:
      node_config = validate_node_config(node_config_raw)
    except Exception:
      return
    if not node_config.handshake_required:
      return

    now = datetime.now(UTC)
    node_instance.business_state = WorkflowNodeBusinessState.ACCEPTED
    node_instance.acknowledged_at = now
    metadata.update(
      {
        "workflow_handshake_state": "accepted",
        "latest_handshake_action": "accepted",
        "latest_handshake_actor_user_id": str(actor.id),
        "latest_handshake_at": now.isoformat(),
      }
    )
    task.extra_metadata = metadata
    if task.status == TaskStatus.TODO:
      task.status = TaskStatus.DOING
      task.started_at = now
    task.updated_at = now
    await self._session.flush()

  @staticmethod
  def is_template_graph_projection(task: Task) -> bool:
    if task.source_type != TaskSourceType.TEMPLATE:
      return False
    metadata = task.extra_metadata if isinstance(task.extra_metadata, dict) else {}
    return bool(metadata.get("workflow_graph_instance_id") and metadata.get("workflow_node_instance_id"))
