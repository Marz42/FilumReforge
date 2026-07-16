"""Video workflow v1 orchestration hooks (W4)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
  AttachmentTargetType,
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
  AttachmentLink,
  Profile,
  Task,
  TaskWatcher,
  User,
  WorkflowDeliverable,
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateEdge,
  WorkflowGraphTemplateNode,
  WorkflowNodeInstance,
)
from app.schemas.workflow_video import validate_node_config
from app.services.cross_department_routing_service import resolve_cross_department_boundary_cc_user_ids
from app.services.task_service import TaskService
from app.services.human_task_coordinator import HumanTaskCoordinator
from app.services.workflow_assignee_resolver import resolve_node_assignee_id
from app.services.workflow_definition_snapshot import (
  RuntimeDefinitionNode,
  RuntimeDefinitionTemplate,
  SNAPSHOT_EXECUTOR_KIND,
  runtime_edges,
  runtime_nodes,
  runtime_template,
)
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_node_config_helpers import (
  is_streaming_aggregate_node,
  resolve_completion_policy,
)
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
    self._human_task_coordinator = HumanTaskCoordinator(session)

  @staticmethod
  def _task_id_from_node_config(node_instance: WorkflowNodeInstance) -> UUID | None:
    config = node_instance.config if isinstance(node_instance.config, dict) else {}
    raw_task_id = config.get("task_id")
    if raw_task_id is None:
      return None
    return UUID(str(raw_task_id))

  async def _load_template(
    self,
    *,
    instance: WorkflowGraphInstance,
  ) -> WorkflowGraphTemplate | RuntimeDefinitionTemplate | None:
    if instance.executor_kind == SNAPSHOT_EXECUTOR_KIND:
      return runtime_template(instance.definition_snapshot)
    if instance.template_id is None:
      return None
    return await self._session.get(WorkflowGraphTemplate, instance.template_id)

  async def _load_template_node(
    self,
    *,
    instance: WorkflowGraphInstance,
    node_instance: WorkflowNodeInstance,
  ) -> WorkflowGraphTemplateNode | RuntimeDefinitionNode | None:
    if instance.executor_kind == SNAPSHOT_EXECUTOR_KIND:
      return next(
        (
          node
          for node in runtime_nodes(instance.definition_snapshot)
          if node.node_key == node_instance.node_key
        ),
        None,
      )
    if node_instance.template_node_id is None:
      return None
    return await self._session.get(WorkflowGraphTemplateNode, node_instance.template_node_id)

  async def _apply_review_projection_state(
    self,
    *,
    instance: WorkflowGraphInstance,
    node_instance: WorkflowNodeInstance,
    task: Task,
    template_node: WorkflowGraphTemplateNode | RuntimeDefinitionNode | None,
  ) -> None:
    """Review nodes activated after upstream deliverable should enter REVIEW immediately."""
    if resolve_completion_policy(node_instance=node_instance, template_node=template_node) != "on_review_approved":
      return

    root_task = (
      await self._session.get(Task, instance.source_id)
      if instance.source_id is not None
      else None
    )
    await self._human_task_coordinator.apply_review_projection_state(
      task=task,
      node_instance=node_instance,
      root_task=root_task,
      reference_time=datetime.now(UTC),
    )

  async def _create_projection_task(
    self,
    *,
    actor: User,
    template: WorkflowGraphTemplate | RuntimeDefinitionTemplate,
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
        await self._human_task_coordinator.coordinate_mutations(
          task=task,
          task_changes={"status": TaskStatus.DOING},
        )
      template_node = await self._load_template_node(
        instance=instance,
        node_instance=node_instance,
      )
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
    task = self._human_task_coordinator.create_work_item(
      title=title,
      creator_id=actor.id,
      assignee_id=assignee_id,
      department_id=resolved_department_id,
      status=TaskStatus.TODO if node_config.get("handshake_required") else TaskStatus.DOING,
      priority=TaskPriority.MEDIUM,
      source_type=TaskSourceType.TEMPLATE,
      extra_metadata=metadata,
    )
    await self._session.flush()
    template_node = await self._load_template_node(
      instance=instance,
      node_instance=node_instance,
    )
    await self._apply_review_projection_state(
      instance=instance,
      node_instance=node_instance,
      task=task,
      template_node=template_node,
    )
    await self._session.flush()
    return task

  async def _inherit_upstream_deliverable_attachments(
    self,
    *,
    instance: WorkflowGraphInstance,
    node_instance: WorkflowNodeInstance,
    target_task: Task,
  ) -> None:
    """Copy upstream node's deliverable attachments to the downstream task (async-safe)."""
    if instance.executor_kind == SNAPSHOT_EXECUTOR_KIND:
      edge = next(
        (
          item
          for item in runtime_edges(instance.definition_snapshot)
          if item.to_node_key == node_instance.node_key and not item.is_reject_path
        ),
        None,
      )
      upstream_node_key = edge.from_node_key if edge is not None else None
    else:
      template_id = instance.template_id
      if template_id is None:
        return
      to_node_sub = (
        select(WorkflowGraphTemplateNode.id)
        .where(
          WorkflowGraphTemplateNode.template_id == template_id,
          WorkflowGraphTemplateNode.node_key == node_instance.node_key,
        )
        .scalar_subquery()
      )
      edge = await self._session.scalar(
        select(WorkflowGraphTemplateEdge).where(
          WorkflowGraphTemplateEdge.template_id == template_id,
          WorkflowGraphTemplateEdge.to_node_id == to_node_sub,
          WorkflowGraphTemplateEdge.is_reject_path.is_(False),
        )
      )
      if edge is None:
        return
      from_template_node = await self._session.get(WorkflowGraphTemplateNode, edge.from_node_id)
      upstream_node_key = from_template_node.node_key if from_template_node is not None else None
    if upstream_node_key is None:
      return

    # Find the completed upstream node instance via explicit query
    upstream_ni = await self._session.scalar(
      select(WorkflowNodeInstance).where(
        WorkflowNodeInstance.instance_id == instance.id,
        WorkflowNodeInstance.node_key == upstream_node_key,
        WorkflowNodeInstance.engine_state == WorkflowNodeEngineState.COMPLETED,
      )
    )
    if upstream_ni is None:
      return

    # Load the upstream deliverable
    upstream_deliverable = await self._session.scalar(
      select(WorkflowDeliverable).where(WorkflowDeliverable.node_instance_id == upstream_ni.id)
    )
    if upstream_deliverable is None or not isinstance(upstream_deliverable.payload, dict):
      return

    submission = upstream_deliverable.payload.get("latest_submission") or {}
    attachment_ids = submission.get("attachment_ids")
    if not isinstance(attachment_ids, list) or not attachment_ids:
      return

    existing_attachment_ids = set(
      await self._session.scalars(
        select(AttachmentLink.attachment_id).where(
          AttachmentLink.target_type == AttachmentTargetType.TASK,
          AttachmentLink.target_id == target_task.id,
          AttachmentLink.relation == "inherited_deliverable",
        )
      )
    )
    for att_id_str in attachment_ids:
      try:
        att_uuid = UUID(str(att_id_str))
        if att_uuid in existing_attachment_ids:
          continue
        self._session.add(
          AttachmentLink(
            attachment_id=att_uuid,
            target_type=AttachmentTargetType.TASK,
            target_id=target_task.id,
            relation="inherited_deliverable",
            created_by=target_task.creator_id,
          )
        )
        existing_attachment_ids.add(att_uuid)
      except (ValueError, AttributeError):
        continue

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
      template_node = await self._load_template_node(
        instance=instance,
        node_instance=node_instance,
      )
      if is_streaming_aggregate_node(
        instance=instance,
        node_instance=node_instance,
        template_node=template_node,
      ):
        await self._engine_skip_streaming_aggregate_node(
          actor=actor,
          instance=instance,
          node_instance=node_instance,
        )
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
      await self._inherit_upstream_deliverable_attachments(
        instance=instance,
        node_instance=node_instance,
        target_task=task,
      )
      await self._maybe_add_boundary_cc_watchers(
        actor=actor,
        instance=instance,
        task=task,
        assignee_id=node_instance.assignee_user_id or actor.id,
      )
      await self._human_task_coordinator.bind_projection_task(
        task=task,
        node_instance=node_instance,
        source="runtime",
        mark_doing=True,
      )
      created.append(task)
    if created:
      await self._workflow_graph_service.enqueue_node_activated_notifications(
        instance=instance,
        node_instances=node_instances,
      )
    await self._session.flush()
    return created

  async def _engine_skip_streaming_aggregate_node(
    self,
    *,
    actor: User,
    instance: WorkflowGraphInstance,
    node_instance: WorkflowNodeInstance,
  ) -> None:
    """W-08: auto-complete aggregate node without creating an inbox shell task."""
    now = datetime.now(UTC)
    await self._human_task_coordinator.coordinate_mutations(
      node_instance=node_instance,
      node_changes={
        "engine_state": WorkflowNodeEngineState.COMPLETED,
        "business_state": WorkflowNodeBusinessState.DONE,
        "completed_at": now,
      },
      node_config_patch={
        "engine_skipped": True,
        "skip_reason": "streaming_aggregate",
      },
    )
    await self._session.flush()

    downstream = await self._workflow_graph_service.progress_from_completed_node(
      node_instance_id=node_instance.id,
    )
    if downstream:
      await self.ensure_projection_tasks(
        actor=actor,
        instance=instance,
        node_instances=downstream,
      )

  async def _maybe_add_boundary_cc_watchers(
    self,
    *,
    actor: User,
    instance: WorkflowGraphInstance,
    task: Task,
    assignee_id: UUID,
  ) -> None:
    """F-27: CC org-tree managers when projection crosses department boundary."""
    if self._task_service is None or instance.department_id is None:
      return

    assignee_department_id = await self._session.scalar(
      select(Profile.department_id).where(Profile.user_id == assignee_id)
    )
    cc_user_ids = await resolve_cross_department_boundary_cc_user_ids(
      self._session,
      origin_department_id=instance.department_id,
      target_department_id=assignee_department_id,
      exclude_user_ids={actor.id, assignee_id},
    )
    if not cc_user_ids:
      return
    for user_id in cc_user_ids:
      self._session.add(
        TaskWatcher(
          task_id=task.id,
          user_id=user_id,
          relation="boundary_cc",
          created_by=actor.id,
        )
      )
    await self._session.flush()

  async def resolve_and_bind_assignee(
    self,
    *,
    actor: User,
    template: WorkflowGraphTemplate | RuntimeDefinitionTemplate,
    instance: WorkflowGraphInstance,
    node_instance: WorkflowNodeInstance,
  ) -> None:
    if node_instance.assignee_user_id is not None:
      return
    template_node = await self._load_template_node(
      instance=instance,
      node_instance=node_instance,
    )
    if template_node is None:
      return
    context = instance.context if isinstance(instance.context, dict) else {}
    assignee_user_id = await resolve_node_assignee_id(
      self._session,
      actor=actor,
      template=template,
      template_node=template_node,
      node_instance=node_instance,
      context=context,
      department_id=instance.department_id,
    )
    await self._human_task_coordinator.coordinate_mutations(
      node_instance=node_instance,
      node_changes={"assignee_user_id": assignee_user_id},
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
    completed_nodes: list[WorkflowNodeInstance] = []
    for node_instance in aggregate_nodes:
      completed_nodes.append(node_instance)

      task_id = self._task_id_from_node_config(node_instance)
      aggregate_task = await self._session.get(Task, task_id) if task_id is not None else None
      await self._human_task_coordinator.apply_aggregate_confirmation(
        node_instance=node_instance,
        task=aggregate_task,
        reference_time=now,
      )

    await self._session.flush()
    for node_instance in completed_nodes:
      await self._workflow_graph_service.progress_from_completed_node(
        node_instance_id=node_instance.id,
      )

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

    await self._human_task_coordinator.apply_handshake_acceptance(
      task=task,
      node_instance=node_instance,
      actor_id=actor.id,
      reference_time=datetime.now(UTC),
    )
    await self._session.flush()

  @staticmethod
  def is_template_graph_projection(task: Task) -> bool:
    if task.source_type != TaskSourceType.TEMPLATE:
      return False
    metadata = task.extra_metadata if isinstance(task.extra_metadata, dict) else {}
    return bool(metadata.get("workflow_graph_instance_id") and metadata.get("workflow_node_instance_id"))
