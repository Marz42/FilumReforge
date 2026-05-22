"""Video workflow v1 graph template instantiation (W3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.enums import (
  TaskPriority,
  TaskSourceType,
  TaskStatus,
  WorkflowGraphInstanceStatus,
  WorkflowGraphTemplateStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.core.workflow_video_policy import use_graph_template_instantiation
from app.models import (
  Task,
  User,
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateEdge,
  WorkflowGraphTemplateNode,
  WorkflowNodeInstance,
)
from app.schemas.workflow_video import (
  ApprovedTopic,
  CreateGraphTemplateRunResponse,
  ParticipantsSnapshotEntry,
  validate_launch_schema,
  validate_node_config,
  validate_run_context,
)
from app.services.access_control import can_publish_org_tasks, ensure_active_user
from app.services.participant_resolution_service import resolve_assignee_from_rule
from app.services.task_service import TaskService
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_run_event_service import WorkflowRunEventService


@dataclass(slots=True)
class GraphTemplateRunResult:
  instance: WorkflowGraphInstance
  root_task: Task
  node_instances: list[WorkflowNodeInstance]
  activated_tasks: list[Task]


class WorkflowVideoInstantiationService:
  def __init__(
    self,
    session: AsyncSession,
    *,
    task_service: TaskService | None = None,
    settings: Settings | None = None,
  ) -> None:
    self._session = session
    self._task_service = task_service
    self._settings = settings or get_settings()
    self._workflow_graph_service = WorkflowGraphService(session)

  def _require_engine_enabled(self) -> None:
    if not use_graph_template_instantiation(self._settings):
      raise ConflictError(
        "图模板实例化引擎未启用。请设置 WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED=true。"
      )

  async def _load_template_graph(
    self,
    *,
    template_id: UUID,
  ) -> tuple[WorkflowGraphTemplate, list[WorkflowGraphTemplateNode], list[WorkflowGraphTemplateEdge]]:
    template = await self._session.get(WorkflowGraphTemplate, template_id)
    if template is None:
      raise NotFoundError("图模板不存在。")
    if template.status != WorkflowGraphTemplateStatus.ACTIVE:
      raise ConflictError("仅可实例化已发布的图模板。")

    nodes = list(
      await self._session.scalars(
        select(WorkflowGraphTemplateNode)
        .where(WorkflowGraphTemplateNode.template_id == template_id)
        .order_by(WorkflowGraphTemplateNode.sort_order)
      )
    )
    if not nodes:
      raise ConflictError("图模板没有节点，无法实例化。")

    edges = list(
      await self._session.scalars(
        select(WorkflowGraphTemplateEdge).where(WorkflowGraphTemplateEdge.template_id == template_id)
      )
    )
    return template, nodes, edges

  @staticmethod
  def _build_schema_snapshot(
    *,
    template: WorkflowGraphTemplate,
    nodes: list[WorkflowGraphTemplateNode],
  ) -> dict[str, Any]:
    template_config = template.config if isinstance(template.config, dict) else {}
    launch_schema = template_config.get("launch_schema")
    node_snapshots: dict[str, dict[str, Any]] = {}
    for node in nodes:
      node_config = node.config if isinstance(node.config, dict) else {}
      entry: dict[str, Any] = {"kind": node_config.get("kind", "single")}
      for key in ("capture_schema", "aggregate_schema", "expand_from", "participant_policy_ref"):
        if key in node_config:
          entry[key] = node_config[key]
      node_snapshots[node.node_key] = entry

    snapshot: dict[str, Any] = {
      "template_code": template.code,
      "template_version": template.version,
      "nodes": node_snapshots,
    }
    if launch_schema is not None:
      snapshot["launch_schema"] = launch_schema
    return snapshot

  @staticmethod
  def _validate_launch_inputs(
    *,
    template: WorkflowGraphTemplate,
    inputs: dict[str, Any],
  ) -> dict[str, Any]:
    template_config = template.config if isinstance(template.config, dict) else {}
    raw_launch = template_config.get("launch_schema")
    if not raw_launch:
      return dict(inputs)

    launch_schema = validate_launch_schema(raw_launch)
    normalized: dict[str, Any] = {}
    for field in launch_schema.fields:
      raw_value = inputs.get(field.key)
      if field.required and (raw_value is None or raw_value == ""):
        raise ConflictError(f"缺少必填字段：{field.label}")
      if raw_value is not None and raw_value != "":
        normalized[field.key] = raw_value
    return normalized

  @staticmethod
  def _normalize_participants_snapshot(
    payload: dict[str, ParticipantsSnapshotEntry],
  ) -> dict[str, dict[str, Any]]:
    if not payload:
      raise ConflictError("participants_snapshot 不能为空。")
    return {
      key: entry.model_dump(mode="json")
      for key, entry in payload.items()
    }

  @staticmethod
  def _parse_department_pools(template: WorkflowGraphTemplate) -> dict[str, UUID]:
    config = template.config if isinstance(template.config, dict) else {}
    pools = config.get("department_pools")
    if not isinstance(pools, dict):
      return {}
    parsed: dict[str, UUID] = {}
    for key, value in pools.items():
      if value is None:
        continue
      parsed[str(key)] = UUID(str(value))
    return parsed

  async def _resolve_node_assignee(
    self,
    *,
    actor: User,
    template: WorkflowGraphTemplate,
    node: WorkflowGraphTemplateNode,
    node_config: dict[str, Any],
    context: dict[str, Any],
    department_id: UUID | None,
  ) -> UUID:
    assignee_rule = node.assignee_rule if isinstance(node.assignee_rule, dict) and node.assignee_rule else None
    assignee_ref = node_config.get("assignee_ref")
    if isinstance(assignee_ref, dict):
      assignee_rule = assignee_ref

    if not assignee_rule:
      return actor.id

    users = await resolve_assignee_from_rule(
      self._session,
      actor=actor,
      assignee_rule=assignee_rule,
      department_id=department_id,
      allow_multiple=False,
      context=context,
      department_pools=self._parse_department_pools(template),
    )
    if not users:
      raise ConflictError(f"节点 {node.node_key} 无法解析受理人。")
    return users[0].id

  async def _create_projection_task(
    self,
    *,
    actor: User,
    template: WorkflowGraphTemplate,
    instance: WorkflowGraphInstance,
    node_instance: WorkflowNodeInstance,
    department_id: UUID | None,
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

    if self._task_service is not None:
      task, _assignee = await self._task_service.create_task_record(
        actor=actor,
        title=title,
        assignee_id=node_instance.assignee_user_id or actor.id,
        department_id=department_id,
        source_type=TaskSourceType.TEMPLATE,
        extra_metadata=metadata,
        commit=False,
        skip_assignee_permission=True,
        skip_publish_permission=True,
      )
      if task.status != TaskStatus.DOING:
        task.status = TaskStatus.DOING
      return task

    task = Task(
      title=title,
      creator_id=actor.id,
      assignee_id=node_instance.assignee_user_id or actor.id,
      department_id=department_id,
      status=TaskStatus.DOING,
      priority=TaskPriority.MEDIUM,
      source_type=TaskSourceType.TEMPLATE,
      extra_metadata=metadata,
    )
    self._session.add(task)
    await self._session.flush()
    return task

  async def instantiate_graph_template(
    self,
    *,
    actor: User,
    template_id: UUID,
    inputs: dict[str, Any] | None = None,
    participants_snapshot: dict[str, ParticipantsSnapshotEntry],
    department_id: UUID | None = None,
    run_label: str | None = None,
  ) -> GraphTemplateRunResult:
    """Instantiate a graph template run with multi_instance expansion and ROOT task."""
    self._require_engine_enabled()
    ensure_active_user(actor)
    if not await can_publish_org_tasks(self._session, actor):
      raise AuthorizationError("当前账号不能发布组织任务。")

    template, nodes, edges = await self._load_template_graph(template_id=template_id)
    normalized_inputs = self._validate_launch_inputs(template=template, inputs=dict(inputs or {}))
    snapshot_payload = self._normalize_participants_snapshot(participants_snapshot)

    template_config = template.config if isinstance(template.config, dict) else {}
    run_kind = str(template_config.get("run_kind") or "batch")
    schema_snapshot = self._build_schema_snapshot(template=template, nodes=nodes)

    resolved_run_label = run_label or normalized_inputs.get("theme") or template.name
    context: dict[str, Any] = {
      "run_kind": run_kind,
      "run_label": resolved_run_label,
      "inputs": normalized_inputs,
      "participants_snapshot": snapshot_payload,
      "schema_snapshot": schema_snapshot,
      "template_version": template.version,
      "fork_status": None,
      "approved_topics": [],
      "forked_child_instance_ids": [],
    }
    for key, value in normalized_inputs.items():
      context[key] = value
    validate_run_context(context)

    in_degree: dict[UUID, int] = {node.id: 0 for node in nodes}
    for edge in edges:
      if edge.to_node_id in in_degree:
        in_degree[edge.to_node_id] += 1

    now = datetime.now(UTC)
    instance = WorkflowGraphInstance(
      template_id=template.id,
      initiator_user_id=actor.id,
      department_id=department_id,
      source_type="template",
      status=WorkflowGraphInstanceStatus.ACTIVE,
      run_label=str(resolved_run_label),
      context=context,
      context_version=1,
      max_iterations=5,
    )
    self._session.add(instance)
    await self._session.flush()

    node_instances: list[WorkflowNodeInstance] = []
    activated_node_keys: list[str] = []

    for node in nodes:
      raw_config = node.config if isinstance(node.config, dict) else {}
      node_config = validate_node_config(raw_config).model_dump(mode="json")
      is_start = in_degree[node.id] == 0
      engine_state = WorkflowNodeEngineState.ACTIVATED if is_start else WorkflowNodeEngineState.PENDING
      business_state = (
        WorkflowNodeBusinessState.DOING if is_start else WorkflowNodeBusinessState.ASSIGNED
      )

      if node_config.get("kind") == "multi_instance":
        expand_from = str(node_config.get("expand_from") or "")
        snapshot_entry = snapshot_payload.get(expand_from)
        if not snapshot_entry:
          raise ConflictError(f"participants_snapshot 缺少展开键：{expand_from}")
        user_ids = snapshot_entry.get("user_ids") or []
        if not user_ids:
          raise ConflictError(f"策略 {expand_from} 未包含任何参与人。")

        for raw_user_id in user_ids:
          assignee_id = UUID(str(raw_user_id))
          ni = WorkflowNodeInstance(
            instance_id=instance.id,
            template_node_id=node.id,
            node_key=node.node_key,
            instance_key=str(assignee_id),
            title=node.title,
            node_type=node.node_type,
            engine_state=engine_state,
            business_state=business_state,
            assignee_user_id=assignee_id,
            iteration=1,
            node_instance_version=1,
            config=node_config,
            activated_at=now if is_start else None,
          )
          self._session.add(ni)
          node_instances.append(ni)
          if is_start:
            activated_node_keys.append(node.node_key)
      else:
        assignee_id = await self._resolve_node_assignee(
          actor=actor,
          template=template,
          node=node,
          node_config=node_config,
          context=context,
          department_id=department_id,
        )
        ni = WorkflowNodeInstance(
          instance_id=instance.id,
          template_node_id=node.id,
          node_key=node.node_key,
          instance_key="singleton",
          title=node.title,
          node_type=node.node_type,
          engine_state=engine_state,
          business_state=business_state,
          assignee_user_id=assignee_id,
          iteration=1,
          node_instance_version=1,
          config=node_config,
          activated_at=now if is_start else None,
        )
        self._session.add(ni)
        node_instances.append(ni)
        if is_start:
          activated_node_keys.append(node.node_key)

    instance.current_node_key = activated_node_keys[0] if activated_node_keys else None
    await self._session.flush()

    root_assignee_id = await self._resolve_root_assignee(
      actor=actor,
      template=template,
      context=context,
      department_id=department_id,
    )
    root_task = await self._create_root_task(
      actor=actor,
      template=template,
      instance=instance,
      assignee_id=root_assignee_id,
      department_id=department_id,
      run_label=str(resolved_run_label),
      run_kind=run_kind,
    )

    instance.source_id = root_task.id
    instance.context = {
      **dict(instance.context or {}),
      "root_task_id": str(root_task.id),
    }
    instance.context_version = 2
    validate_run_context(instance.context)

    activated_tasks: list[Task] = []
    for node_instance in node_instances:
      if node_instance.engine_state != WorkflowNodeEngineState.ACTIVATED:
        continue
      task = await self._create_projection_task(
        actor=actor,
        template=template,
        instance=instance,
        node_instance=node_instance,
        department_id=department_id,
      )
      node_instance.config = {
        **dict(node_instance.config or {}),
        "task_id": str(task.id),
      }
      activated_tasks.append(task)

    activated_nodes = [ni for ni in node_instances if ni.engine_state == WorkflowNodeEngineState.ACTIVATED]
    await self._workflow_graph_service.enqueue_node_activated_notifications(
      instance=instance,
      node_instances=activated_nodes,
    )
    await WorkflowRunEventService(self._session).append(
      instance_id=instance.id,
      event_type="run_instantiated",
      actor_user_id=actor.id,
      payload={
        "template_id": str(template.id),
        "template_code": template.code,
        "run_kind": run_kind,
        "root_task_id": str(root_task.id),
        "activated_task_count": len(activated_tasks),
      },
    )
    await self._session.flush()
    return GraphTemplateRunResult(
      instance=instance,
      root_task=root_task,
      node_instances=node_instances,
      activated_tasks=activated_tasks,
    )

  async def _resolve_root_assignee(
    self,
    *,
    actor: User,
    template: WorkflowGraphTemplate,
    context: dict[str, Any],
    department_id: UUID | None,
  ) -> UUID:
    config = template.config if isinstance(template.config, dict) else {}
    root_var = config.get("root_assignee_var")
    if isinstance(root_var, str) and root_var.strip():
      raw = context.get(root_var.strip())
      if raw is not None:
        return UUID(str(raw))

    root_rule = config.get("root_assignee_rule")
    if isinstance(root_rule, dict):
      users = await resolve_assignee_from_rule(
        self._session,
        actor=actor,
        assignee_rule=root_rule,
        department_id=department_id,
        allow_multiple=False,
        context=context,
        department_pools=self._parse_department_pools(template),
      )
      if users:
        return users[0].id
    return actor.id

  async def _create_root_task(
    self,
    *,
    actor: User,
    template: WorkflowGraphTemplate,
    instance: WorkflowGraphInstance,
    assignee_id: UUID,
    department_id: UUID | None,
    run_label: str,
    run_kind: str,
    parent_task_id: UUID | None = None,
    extra_metadata: dict[str, object] | None = None,
  ) -> Task:
    title = f"{template.name} / {run_label}"
    metadata: dict[str, object] = {
      "workflow_graph_instance_id": str(instance.id),
      "workflow_graph_root_task": True,
      "template_id": str(template.id),
      "template_code": template.code,
      "run_kind": run_kind,
    }
    if extra_metadata:
      metadata.update(extra_metadata)

    if self._task_service is not None:
      task, _assignee = await self._task_service.create_task_record(
        actor=actor,
        title=title,
        assignee_id=assignee_id,
        department_id=department_id,
        source_type=TaskSourceType.TEMPLATE,
        extra_metadata=metadata,
        commit=False,
        skip_assignee_permission=True,
        skip_publish_permission=True,
      )
      if parent_task_id is not None:
        task.parent_task_id = parent_task_id
      return task

    task = Task(
      title=title,
      creator_id=actor.id,
      assignee_id=assignee_id,
      department_id=department_id,
      parent_task_id=parent_task_id,
      status=TaskStatus.DOING,
      priority=TaskPriority.MEDIUM,
      source_type=TaskSourceType.TEMPLATE,
      extra_metadata=metadata,
    )
    self._session.add(task)
    await self._session.flush()
    return task

  async def instantiate_production_child_run(
    self,
    *,
    actor: User,
    template: WorkflowGraphTemplate,
    parent_instance: WorkflowGraphInstance,
    topic: ApprovedTopic,
    parent_task_id: UUID | None = None,
  ) -> GraphTemplateRunResult:
    """Instantiate a per-topic production child Run linked to a batch parent (WFK)."""
    self._require_engine_enabled()
    ensure_active_user(actor)

    _template, nodes, edges = await self._load_template_graph(template_id=template.id)
    schema_snapshot = self._build_schema_snapshot(template=_template, nodes=nodes)

    context: dict[str, Any] = {
      "run_kind": "production",
      "run_label": topic.title,
      "parent_instance_id": str(parent_instance.id),
      "topic_id": str(topic.topic_id),
      "topic_title": topic.title,
      "script_author_id": str(topic.script_author_id),
      "inputs": {},
      "participants_snapshot": {},
      "schema_snapshot": schema_snapshot,
      "template_version": _template.version,
      "fork_status": None,
      "approved_topics": [],
      "forked_child_instance_ids": [],
    }
    if topic.content:
      context["topic_content"] = topic.content
    validate_run_context(context)

    in_degree: dict[UUID, int] = {node.id: 0 for node in nodes}
    for edge in edges:
      if edge.to_node_id in in_degree:
        in_degree[edge.to_node_id] += 1

    now = datetime.now(UTC)
    instance = WorkflowGraphInstance(
      template_id=_template.id,
      initiator_user_id=actor.id,
      department_id=parent_instance.department_id,
      parent_instance_id=parent_instance.id,
      source_type="template",
      status=WorkflowGraphInstanceStatus.ACTIVE,
      run_label=topic.title,
      context=context,
      context_version=1,
      max_iterations=5,
    )
    self._session.add(instance)
    await self._session.flush()

    node_instances: list[WorkflowNodeInstance] = []
    activated_node_keys: list[str] = []

    for node in nodes:
      raw_config = node.config if isinstance(node.config, dict) else {}
      node_config = validate_node_config(raw_config).model_dump(mode="json")
      is_start = in_degree[node.id] == 0
      engine_state = WorkflowNodeEngineState.ACTIVATED if is_start else WorkflowNodeEngineState.PENDING
      business_state = (
        WorkflowNodeBusinessState.DOING if is_start else WorkflowNodeBusinessState.ASSIGNED
      )

      assignee_id = await self._resolve_node_assignee(
        actor=actor,
        template=_template,
        node=node,
        node_config=node_config,
        context=context,
        department_id=parent_instance.department_id,
      )
      if node.node_key == "N3_SCRIPT_WRITE":
        assignee_id = topic.script_author_id

      ni = WorkflowNodeInstance(
        instance_id=instance.id,
        template_node_id=node.id,
        node_key=node.node_key,
        instance_key="singleton",
        title=node.title,
        node_type=node.node_type,
        engine_state=engine_state,
        business_state=business_state,
        assignee_user_id=assignee_id,
        iteration=1,
        node_instance_version=1,
        config=node_config,
        activated_at=now if is_start else None,
      )
      self._session.add(ni)
      node_instances.append(ni)
      if is_start:
        activated_node_keys.append(node.node_key)

    instance.current_node_key = activated_node_keys[0] if activated_node_keys else None
    await self._session.flush()

    root_task = await self._create_root_task(
      actor=actor,
      template=_template,
      instance=instance,
      assignee_id=topic.script_author_id,
      department_id=parent_instance.department_id,
      run_label=topic.title,
      run_kind="production",
      parent_task_id=parent_task_id,
      extra_metadata={
        "topic_id": str(topic.topic_id),
        "parent_instance_id": str(parent_instance.id),
      },
    )

    instance.source_id = root_task.id
    instance.context = {
      **dict(instance.context or {}),
      "root_task_id": str(root_task.id),
    }
    instance.context_version = 2
    validate_run_context(instance.context)

    activated_tasks: list[Task] = []
    for node_instance in node_instances:
      if node_instance.engine_state != WorkflowNodeEngineState.ACTIVATED:
        continue
      task = await self._create_projection_task(
        actor=actor,
        template=_template,
        instance=instance,
        node_instance=node_instance,
        department_id=parent_instance.department_id,
      )
      node_instance.config = {
        **dict(node_instance.config or {}),
        "task_id": str(task.id),
      }
      activated_tasks.append(task)

    activated_nodes = [ni for ni in node_instances if ni.engine_state == WorkflowNodeEngineState.ACTIVATED]
    await self._workflow_graph_service.enqueue_node_activated_notifications(
      instance=instance,
      node_instances=activated_nodes,
    )
    await WorkflowRunEventService(self._session).append(
      instance_id=instance.id,
      event_type="run_instantiated",
      actor_user_id=actor.id,
      payload={
        "template_id": str(_template.id),
        "template_code": _template.code,
        "run_kind": "production",
        "parent_instance_id": str(parent_instance.id),
        "topic_id": str(topic.topic_id),
        "root_task_id": str(root_task.id),
      },
    )
    await self._session.flush()
    return GraphTemplateRunResult(
      instance=instance,
      root_task=root_task,
      node_instances=node_instances,
      activated_tasks=activated_tasks,
    )

  def to_response(self, result: GraphTemplateRunResult) -> CreateGraphTemplateRunResponse:
    run_kind = str((result.instance.context or {}).get("run_kind") or "batch")
    return CreateGraphTemplateRunResponse(
      instance_id=result.instance.id,
      root_task_id=result.root_task.id,
      run_kind=run_kind,
      activated_task_count=len(result.activated_tasks),
      node_instance_count=len(result.node_instances),
      current_node_key=result.instance.current_node_key,
    )
