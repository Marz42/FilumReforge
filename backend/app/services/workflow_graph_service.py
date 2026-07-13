from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
  TaskPriority,
  TaskSourceType,
  UserRole,
  UserStatus,
  WorkflowGraphInstanceStatus,
  WorkflowGraphNodeType,
  WorkflowGraphTemplateStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
  WorkflowOutboxEventStatus,
)
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.services.access_control import ensure_active_user
from app.services.condition_evaluator import (
  evaluate_condition,
  evaluate_routing_rules,
  is_else_condition,
)
from app.services.notification_service import NotificationService
from app.services.workflow_assignee_resolver import resolve_node_assignee_id
from app.services.workflow_definition_snapshot import (
  SNAPSHOT_ENGINE_VERSION,
  SNAPSHOT_EXECUTOR_KIND,
  RuntimeDefinitionEdge,
  RuntimeDefinitionNode,
  build_definition_snapshot,
  definition_snapshot_hash,
  ensure_template_scope_allows_department,
  runtime_edges,
  runtime_nodes,
  runtime_template,
)
from app.services.workflow_run_event_service import WorkflowRunEventService
from app.models import (
  Task,
  User,
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateEdge,
  WorkflowGraphTemplateNode,
  WorkflowNodeInstance,
  WorkflowRunEvent,
)
from app.models.workflow_graph import WorkflowOutboxEvent


@dataclass(slots=True)
class DepartmentRunSummary:
  instance_id: UUID
  run_label: str | None
  status: WorkflowGraphInstanceStatus
  created_at: datetime
  event_count: int
  department_id: UUID | None


@dataclass(slots=True)
class SingleNodeWorkflowSeed:
  title: str
  creator_id: UUID
  assignee_id: UUID
  department_id: UUID | None
  description: str | None
  due_date: datetime | None
  priority: TaskPriority


@dataclass(slots=True)
class MultiNodeWorkflowResult:
  instance: WorkflowGraphInstance
  node_instances: list[WorkflowNodeInstance]


class WorkflowGraphService:
  def __init__(
    self,
    session: AsyncSession,
    notification_service: NotificationService | None = None,
  ) -> None:
    self._session = session
    self._notification_service = notification_service

  @staticmethod
  def _ensure_snapshot_integrity(graph_instance: WorkflowGraphInstance) -> None:
    if graph_instance.executor_kind != SNAPSHOT_EXECUTOR_KIND:
      return
    snapshot = graph_instance.definition_snapshot
    expected_hash = graph_instance.definition_hash
    if not isinstance(snapshot, dict) or not expected_hash:
      raise ConflictError("当前 Run 缺少有效的定义快照，已停止执行。")
    if definition_snapshot_hash(snapshot) != expected_hash:
      raise ConflictError("当前 Run 的定义快照校验失败，已停止执行。")

  async def _write_outbox_event(
    self,
    *,
    instance_id: UUID,
    node_instance_id: UUID | None,
    event_type: str,
    payload: dict[str, Any],
  ) -> None:
    """在当前事务内写入 WorkflowOutboxEvent（PENDING），供 ARQ worker 异步投递。"""
    event = WorkflowOutboxEvent(
      instance_id=instance_id,
      node_instance_id=node_instance_id,
      event_type=event_type,
      status=WorkflowOutboxEventStatus.PENDING,
      attempt_count=0,
      payload=payload,
    )
    self._session.add(event)
    await self._session.flush()

  async def enqueue_node_activated_notifications(
    self,
    *,
    instance: WorkflowGraphInstance,
    node_instances: list[WorkflowNodeInstance],
  ) -> None:
    """W9-1: queue async notifications when template graph nodes become active."""
    context = instance.context if isinstance(instance.context, dict) else {}
    if not context.get("run_kind"):
      return

    run_label = instance.run_label or str(instance.id)[:8]
    for node_instance in node_instances:
      if node_instance.engine_state != WorkflowNodeEngineState.ACTIVATED:
        continue
      assignee_id = node_instance.assignee_user_id
      if assignee_id is None:
        continue
      assignee = await self._session.get(User, assignee_id)
      if assignee is None or assignee.status != UserStatus.ACTIVE:
        continue

      await self._write_outbox_event(
        instance_id=instance.id,
        node_instance_id=node_instance.id,
        event_type="workflow_node_activated",
        payload={
          "recipient_user_id": str(assignee.id),
          "recipient_email": assignee.email,
          "title": f"新任务：{node_instance.title}",
          "body_text": (
            f"运行「{run_label}」的节点「{node_instance.title}」已激活，请在任务中心处理。"
          ),
          "node_key": node_instance.node_key,
          "node_instance_id": str(node_instance.id),
          "workflow_graph_instance_id": str(instance.id),
        },
      )

  async def _sync_manual_task_projection_after_takeover(
    self,
    *,
    graph_instance: WorkflowGraphInstance,
    new_assignee_id: UUID,
    reason: str,
    actor_id: UUID,
  ) -> None:
    """手动图任务：管理员接管节点后同步兼容读模型上的 assignee 与握手元数据。"""
    if graph_instance.source_id is None:
      return
    # 与 TaskService._create_single_node_workflow_projection 对齐：source_type 存枚举 value（如 manual）
    if graph_instance.source_type not in {TaskSourceType.MANUAL.value, "task"}:
      return
    task = await self._session.get(Task, graph_instance.source_id)
    if task is None or task.source_type != TaskSourceType.MANUAL:
      return
    metadata = dict(task.extra_metadata or {})
    if not metadata.get("workflow_node_instance_id"):
      return
    task.assignee_id = new_assignee_id
    metadata.update(
      {
        "workflow_handshake_state": "assigned",
        "latest_handshake_action": "takeover",
        "latest_handshake_actor_user_id": str(actor_id),
        "latest_takeover_reason": reason,
      }
    )
    task.extra_metadata = metadata
    task.updated_at = datetime.now(UTC)

  async def takeover_node_instance(
    self,
    *,
    node_instance_id: UUID,
    actor_id: UUID,
    actor_role: UserRole,
    assignee_id: UUID,
    reason: str,
  ) -> UUID:
    """管理员强制接管运行中节点，写入审计信息并通知原执行人。"""
    if actor_role != UserRole.ADMIN:
      raise AuthorizationError("仅管理员可以接管节点。")

    normalized_reason = reason.strip()
    if not normalized_reason:
      raise ConflictError("接管节点时必须填写原因。")

    node_instance: WorkflowNodeInstance | None = await self._session.scalar(
      select(WorkflowNodeInstance)
      .where(WorkflowNodeInstance.id == node_instance_id)
      .with_for_update()
    )
    if node_instance is None:
      raise NotFoundError("节点实例不存在。")

    graph_instance = await self._lock_graph_instance(instance_id=node_instance.instance_id)
    if graph_instance.status != WorkflowGraphInstanceStatus.ACTIVE:
      raise ConflictError("当前工作流图实例已结束，不能执行接管。")
    if node_instance.engine_state not in [
      WorkflowNodeEngineState.ACTIVATED,
      WorkflowNodeEngineState.ACKNOWLEDGED,
    ]:
      raise ConflictError("只有处于 ACTIVATED/ACKNOWLEDGED 状态的节点才能被接管。")

    assignee = await self._session.get(User, assignee_id)
    if assignee is None:
      raise NotFoundError("接管目标执行人不存在。")
    ensure_active_user(assignee)

    previous_assignee_id = node_instance.assignee_user_id
    if previous_assignee_id == assignee.id:
      raise ConflictError("接管目标执行人不能与当前执行人相同。")

    now = datetime.now(UTC)
    node_instance.assignee_user_id = assignee.id
    node_instance.engine_state = WorkflowNodeEngineState.ACTIVATED
    node_instance.business_state = WorkflowNodeBusinessState.ASSIGNED
    node_instance.activated_at = now
    node_instance.node_instance_version += 1

    config = dict(node_instance.config or {})
    config["takeover"] = {
      "reason": normalized_reason,
      "from_assignee_user_id": str(previous_assignee_id) if previous_assignee_id is not None else None,
      "to_assignee_user_id": str(assignee.id),
      "operator_user_id": str(actor_id),
      "taken_over_at": now.isoformat(),
    }
    node_instance.config = config
    graph_instance.current_node_key = node_instance.node_key
    await self._session.flush()

    if previous_assignee_id is not None and previous_assignee_id != assignee.id:
      previous_assignee = await self._session.get(User, previous_assignee_id)
      if previous_assignee is not None and previous_assignee.status == UserStatus.ACTIVE:
        await self._write_outbox_event(
          instance_id=node_instance.instance_id,
          node_instance_id=node_instance.id,
          event_type="workflow_node_taken_over",
          payload={
            "recipient_user_id": str(previous_assignee.id),
            "recipient_email": previous_assignee.email,
            "title": f"节点已被管理员接管：{node_instance.title}",
            "body_text": f"节点「{node_instance.title}」已由管理员接管并转派给其他执行人。原因：{normalized_reason}",
            "node_instance_id": str(node_instance.id),
            "workflow_graph_instance_id": str(node_instance.instance_id),
            "from_assignee_user_id": str(previous_assignee.id),
            "to_assignee_user_id": str(assignee.id),
            "operator_user_id": str(actor_id),
            "reason": normalized_reason,
          },
        )

    await self._sync_manual_task_projection_after_takeover(
      graph_instance=graph_instance,
      new_assignee_id=assignee.id,
      reason=normalized_reason,
      actor_id=actor_id,
    )
    await self._session.commit()
    return graph_instance.id

  async def deep_reject_to_upstream(
    self,
    *,
    node_instance_id: UUID,
    actor_id: UUID,
    target_node_key: str,
    reason: str | None = None,
  ) -> UUID:
    """将当前节点深度打回到任意上游节点，并采用 Append-Only 方式重放尾链。"""
    current_node_instance: WorkflowNodeInstance | None = await self._session.scalar(
      select(WorkflowNodeInstance)
      .where(WorkflowNodeInstance.id == node_instance_id)
      .with_for_update()
    )
    if current_node_instance is None:
      raise NotFoundError("节点实例不存在。")

    graph_instance = await self._lock_graph_instance(instance_id=current_node_instance.instance_id)
    self._ensure_snapshot_integrity(graph_instance)
    if graph_instance.status != WorkflowGraphInstanceStatus.ACTIVE:
      raise ConflictError("当前工作流图实例已结束，不能发起深度打回。")
    if current_node_instance.template_node_id is None or graph_instance.template_id is None:
      raise ConflictError("当前节点不属于模板图实例，不能发起深度打回。")
    if current_node_instance.engine_state not in [
      WorkflowNodeEngineState.ACTIVATED,
      WorkflowNodeEngineState.ACKNOWLEDGED,
    ]:
      raise ConflictError("只有处于 ACTIVATED/ACKNOWLEDGED 状态的节点才能发起深度打回。")
    if (
      current_node_instance.assignee_user_id is not None
      and current_node_instance.assignee_user_id != actor_id
    ):
      raise ConflictError("只有当前受理人才能发起深度打回。")

    if graph_instance.executor_kind == SNAPSHOT_EXECUTOR_KIND:
      template_nodes = runtime_nodes(graph_instance.definition_snapshot)
      edges = [
        edge
        for edge in runtime_edges(graph_instance.definition_snapshot)
        if not edge.is_reject_path
      ]
    else:
      template_nodes = list(
        await self._session.scalars(
          select(WorkflowGraphTemplateNode)
          .where(WorkflowGraphTemplateNode.template_id == graph_instance.template_id)
          .order_by(WorkflowGraphTemplateNode.sort_order.asc())
        )
      )
      edges = list(
        await self._session.scalars(
          select(WorkflowGraphTemplateEdge).where(
            WorkflowGraphTemplateEdge.template_id == graph_instance.template_id,
            WorkflowGraphTemplateEdge.is_reject_path.is_(False),
          )
        )
      )
    if not template_nodes:
      raise ConflictError("当前模板没有可用节点，无法执行深度打回。")

    template_node_by_key = {node.node_key: node for node in template_nodes}
    target_template_node = template_node_by_key.get(target_node_key)
    if target_template_node is None:
      raise ConflictError("目标节点不存在于当前模板中。")

    reachable_from_target = self._collect_reachable_template_node_ids(
      start_node_id=target_template_node.id,
      edges=edges,
    )
    if current_node_instance.template_node_id not in reachable_from_target:
      raise ConflictError("目标节点不是当前节点的上游节点，不能发起深度打回。")

    next_iteration = await self._resolve_next_iteration_for_node_key(
      instance_id=graph_instance.id,
      node_key=target_template_node.node_key,
    )
    if next_iteration > graph_instance.max_iterations:
      raise ConflictError("深度打回次数已达上限，系统已阻止继续迭代。")

    now = datetime.now(UTC)
    replay_template_node_ids = reachable_from_target

    # 清理当前链路中尚未收口的节点，避免与新一轮迭代并存为可操作态。
    stale_node_instances: list[WorkflowNodeInstance] = list(
      await self._session.scalars(
        select(WorkflowNodeInstance)
        .where(
          WorkflowNodeInstance.instance_id == graph_instance.id,
          WorkflowNodeInstance.template_node_id.in_(replay_template_node_ids),
          WorkflowNodeInstance.engine_state.in_(
            [
              WorkflowNodeEngineState.PENDING,
              WorkflowNodeEngineState.ACTIVATED,
              WorkflowNodeEngineState.ACKNOWLEDGED,
            ]
          ),
        )
        .with_for_update(skip_locked=True)
      )
    )
    for stale_node in stale_node_instances:
      stale_node.engine_state = WorkflowNodeEngineState.TERMINATED
      stale_node.business_state = WorkflowNodeBusinessState.CANCELLED
      stale_node.terminated_at = now
      stale_node.node_instance_version += 1
      stale_config = dict(stale_node.config or {})
      stale_config["system_resolution"] = {
        "reason": "deep_rejection_replayed",
        "target_node_key": target_node_key,
        "triggered_by_node_instance_id": str(current_node_instance.id),
        "triggered_by_user_id": str(actor_id),
        "triggered_at": now.isoformat(),
      }
      stale_node.config = stale_config

    latest_assignee_by_template_node_id = await self._load_latest_assignee_by_template_node_id(
      instance_id=graph_instance.id,
      template_node_ids=replay_template_node_ids,
    )

    replay_template_nodes = [
      node for node in template_nodes if node.id in replay_template_node_ids
    ]

    for template_node in replay_template_nodes:
      is_target = template_node.id == target_template_node.id
      clone_engine_state = (
        WorkflowNodeEngineState.ACTIVATED if is_target else WorkflowNodeEngineState.PENDING
      )
      clone_business_state = (
        WorkflowNodeBusinessState.ASSIGNED if is_target else WorkflowNodeBusinessState.DRAFT
      )
      clone_config = dict(template_node.config or {})
      clone_config["deep_rejection"] = {
        "target_node_key": target_node_key,
        "reason": reason,
        "iteration": next_iteration,
        "triggered_by_node_instance_id": str(current_node_instance.id),
        "triggered_by_user_id": str(actor_id),
        "triggered_at": now.isoformat(),
      }

      clone_node_instance = WorkflowNodeInstance(
        instance_id=graph_instance.id,
        template_node_id=template_node.id,
        node_key=template_node.node_key,
        title=template_node.title,
        node_type=template_node.node_type,
        engine_state=clone_engine_state,
        business_state=clone_business_state,
        assignee_user_id=latest_assignee_by_template_node_id.get(template_node.id),
        iteration=next_iteration,
        node_instance_version=1,
        config=clone_config,
        activated_at=now if is_target else None,
      )
      self._session.add(clone_node_instance)

    graph_instance.current_node_key = target_template_node.node_key
    graph_instance.status = WorkflowGraphInstanceStatus.ACTIVE
    graph_instance.completed_at = None
    await self._session.flush()

    await self._session.commit()
    return graph_instance.id

  def _collect_reachable_template_node_ids(
    self,
    *,
    start_node_id: UUID,
    edges: list[WorkflowGraphTemplateEdge | RuntimeDefinitionEdge],
  ) -> set[UUID]:
    adjacency: dict[UUID, list[UUID]] = {}
    for edge in edges:
      adjacency.setdefault(edge.from_node_id, []).append(edge.to_node_id)

    visited: set[UUID] = set()
    queue: list[UUID] = [start_node_id]
    while queue:
      current = queue.pop(0)
      if current in visited:
        continue
      visited.add(current)
      for downstream in adjacency.get(current, []):
        if downstream not in visited:
          queue.append(downstream)
    return visited

  async def _resolve_next_iteration_for_node_key(
    self,
    *,
    instance_id: UUID,
    node_key: str,
  ) -> int:
    max_iteration = await self._session.scalar(
      select(WorkflowNodeInstance.iteration)
      .where(
        WorkflowNodeInstance.instance_id == instance_id,
        WorkflowNodeInstance.node_key == node_key,
      )
      .order_by(WorkflowNodeInstance.iteration.desc())
      .limit(1)
    )
    if max_iteration is None:
      return 1
    return int(max_iteration) + 1

  async def _load_latest_assignee_by_template_node_id(
    self,
    *,
    instance_id: UUID,
    template_node_ids: set[UUID],
  ) -> dict[UUID, UUID | None]:
    if not template_node_ids:
      return {}

    node_instances = list(
      await self._session.scalars(
        select(WorkflowNodeInstance)
        .where(
          WorkflowNodeInstance.instance_id == instance_id,
          WorkflowNodeInstance.template_node_id.in_(template_node_ids),
        )
        .order_by(
          WorkflowNodeInstance.template_node_id.asc(),
          WorkflowNodeInstance.iteration.desc(),
          WorkflowNodeInstance.created_at.desc(),
        )
      )
    )

    latest: dict[UUID, UUID | None] = {}
    for node_instance in node_instances:
      if node_instance.template_node_id is None:
        continue
      if node_instance.template_node_id in latest:
        continue
      latest[node_instance.template_node_id] = node_instance.assignee_user_id
    return latest

  async def _lock_graph_instance(self, *, instance_id: UUID) -> WorkflowGraphInstance:
    instance: WorkflowGraphInstance | None = await self._session.scalar(
      select(WorkflowGraphInstance)
      .where(WorkflowGraphInstance.id == instance_id)
      .with_for_update()
    )
    if instance is None:
      raise NotFoundError("工作流图实例不存在。")
    return instance

  async def _resolve_current_node_key(
    self,
    *,
    graph_instance: WorkflowGraphInstance,
  ) -> str | None:
    instance_id = graph_instance.id
    active_nodes = list(
      await self._session.scalars(
        select(WorkflowNodeInstance)
        .where(
          WorkflowNodeInstance.instance_id == instance_id,
          WorkflowNodeInstance.engine_state == WorkflowNodeEngineState.ACTIVATED,
        )
      )
    )
    if not active_nodes:
      return None

    if graph_instance.executor_kind == SNAPSHOT_EXECUTOR_KIND:
      sort_order_by_node_key = {
        node.node_key: node.sort_order
        for node in runtime_nodes(graph_instance.definition_snapshot)
      }
      active_nodes.sort(
        key=lambda node_instance: (
          sort_order_by_node_key.get(node_instance.node_key, 0),
          node_instance.created_at,
          node_instance.node_key,
        )
      )
      return active_nodes[0].node_key

    template_node_ids = [
      node_instance.template_node_id
      for node_instance in active_nodes
      if node_instance.template_node_id is not None
    ]
    sort_order_by_template_node_id: dict[UUID, int] = {}
    if template_node_ids:
      template_nodes = list(
        await self._session.scalars(
          select(WorkflowGraphTemplateNode).where(
            WorkflowGraphTemplateNode.id.in_(template_node_ids)
          )
        )
      )
      sort_order_by_template_node_id = {
        template_node.id: template_node.sort_order
        for template_node in template_nodes
      }

    active_nodes.sort(
      key=lambda node_instance: (
        sort_order_by_template_node_id.get(node_instance.template_node_id, 0),
        node_instance.created_at,
        node_instance.node_key,
      )
    )
    return active_nodes[0].node_key

  # ------------------------------------------------------------------ #
  # Phase 3 / Single-node instance (手动临时任务)
  # ------------------------------------------------------------------ #

  async def create_single_node_instance(self, *, seed: SingleNodeWorkflowSeed) -> tuple[WorkflowGraphInstance, WorkflowNodeInstance]:
    now = datetime.now(UTC)
    instance = WorkflowGraphInstance(
      initiator_user_id=seed.creator_id,
      department_id=seed.department_id,
      source_type="task",
      status=WorkflowGraphInstanceStatus.ACTIVE,
      current_node_key="task-node",
      context={
        "title": seed.title,
        "description": seed.description,
        "priority": seed.priority.value,
        "due_date": seed.due_date.isoformat() if seed.due_date is not None else None,
      },
      context_version=1,
      max_iterations=5,
    )
    self._session.add(instance)
    await self._session.flush()

    node_instance = WorkflowNodeInstance(
      instance_id=instance.id,
      node_key="task-node",
      title=seed.title,
      node_type=WorkflowGraphNodeType.TASK,
      engine_state=WorkflowNodeEngineState.ACTIVATED,
      business_state=WorkflowNodeBusinessState.ASSIGNED,
      assignee_user_id=seed.assignee_id,
      iteration=1,
      node_instance_version=1,
      config={
        "description": seed.description,
        "priority": seed.priority.value,
        "due_date": seed.due_date.isoformat() if seed.due_date is not None else None,
      },
      activated_at=now,
    )
    self._session.add(node_instance)
    await self._session.flush()
    return instance, node_instance

  # ------------------------------------------------------------------ #
  # Phase 6 / Multi-node instance (图模板实例化)
  # ------------------------------------------------------------------ #

  async def create_multi_node_instance(
    self,
    *,
    template_id: UUID,
    initiator_id: UUID,
    department_id: UUID | None = None,
    context: dict[str, object] | None = None,
  ) -> MultiNodeWorkflowResult:
    """根据 WorkflowGraphTemplate 创建图实例与全部节点实例。

    - 无入度节点以 ACTIVATED 状态创建，其余节点以 PENDING 状态创建。
    - 支持 join_mode=all / join_mode=any。
    """
    template = await self._session.scalar(
      select(WorkflowGraphTemplate).where(WorkflowGraphTemplate.id == template_id)
    )
    if template is None:
      raise NotFoundError("工作流图模板不存在。")

    if template.status != WorkflowGraphTemplateStatus.ACTIVE:
      raise ConflictError("仅可实例化已发布的图模板。")
    ensure_template_scope_allows_department(template=template, department_id=department_id)

    nodes: list[WorkflowGraphTemplateNode] = list(
      await self._session.scalars(
        select(WorkflowGraphTemplateNode)
        .where(WorkflowGraphTemplateNode.template_id == template_id)
        .order_by(WorkflowGraphTemplateNode.sort_order)
      )
    )
    if not nodes:
      raise ConflictError("工作流图模板没有节点，无法实例化。")

    edges: list[WorkflowGraphTemplateEdge] = list(
      await self._session.scalars(
        select(WorkflowGraphTemplateEdge)
        .where(WorkflowGraphTemplateEdge.template_id == template_id)
      )
    )
    definition_snapshot = build_definition_snapshot(
      template=template,
      nodes=nodes,
      edges=edges,
    )

    # 计算每个节点的入度
    in_degree: dict[UUID, int] = {node.id: 0 for node in nodes}
    for edge in edges:
      if edge.is_reject_path:
        continue
      if edge.to_node_id in in_degree:
        in_degree[edge.to_node_id] += 1

    now = datetime.now(UTC)
    instance = WorkflowGraphInstance(
      template_id=template_id,
      initiator_user_id=initiator_id,
      department_id=department_id,
      source_type="template",
      status=WorkflowGraphInstanceStatus.ACTIVE,
      context=dict(context or {}),
      definition_snapshot=definition_snapshot,
      definition_hash=definition_snapshot_hash(definition_snapshot),
      engine_version=SNAPSHOT_ENGINE_VERSION,
      executor_kind=SNAPSHOT_EXECUTOR_KIND,
      context_version=1,
      max_iterations=5,
    )
    self._session.add(instance)
    await self._session.flush()

    node_instances: list[WorkflowNodeInstance] = []
    start_node_key: str | None = None

    for node in nodes:
      is_start = in_degree[node.id] == 0
      engine_state = WorkflowNodeEngineState.ACTIVATED if is_start else WorkflowNodeEngineState.PENDING
      business_state = WorkflowNodeBusinessState.ASSIGNED if is_start else WorkflowNodeBusinessState.DRAFT

      ni = WorkflowNodeInstance(
        instance_id=instance.id,
        template_node_id=node.id,
        node_key=node.node_key,
        title=node.title,
        node_type=node.node_type,
        engine_state=engine_state,
        business_state=business_state,
        iteration=1,
        node_instance_version=1,
        config=dict(node.config or {}),
        activated_at=now if is_start else None,
      )
      self._session.add(ni)
      node_instances.append(ni)

      if is_start and start_node_key is None:
        start_node_key = node.node_key

    instance.current_node_key = start_node_key
    await self._session.flush()

    # Phase 7: Notice Node 触达即完成，不阻塞主链。
    await self._auto_complete_activated_notice_nodes(
      graph_instance=instance,
      now=now,
    )

    return MultiNodeWorkflowResult(instance=instance, node_instances=node_instances)

  async def complete_node_instance(
    self,
    *,
    node_instance_id: UUID,
    actor_id: UUID,
    context_updates: dict[str, Any] | None = None,
  ) -> None:
    """标记节点实例为已完成，并在事务中检查 / 激活下游节点。

    支持 join_mode=all / join_mode=any。
    """
    # 先用 SELECT … FOR UPDATE 防止并发写
    node_instance: WorkflowNodeInstance | None = await self._session.scalar(
      select(WorkflowNodeInstance)
      .where(WorkflowNodeInstance.id == node_instance_id)
      .with_for_update()
    )
    if node_instance is None:
      raise NotFoundError("节点实例不存在。")

    graph_instance = await self._lock_graph_instance(instance_id=node_instance.instance_id)
    if node_instance.engine_state == WorkflowNodeEngineState.COMPLETED:
      await self._session.commit()
      return  # 幂等保护
    self._ensure_snapshot_integrity(graph_instance)
    if node_instance.engine_state == WorkflowNodeEngineState.TERMINATED:
      raise ConflictError("当前节点已被系统撤权，不能继续提交。")
    if graph_instance.status != WorkflowGraphInstanceStatus.ACTIVE:
      raise ConflictError("当前工作流图实例已结束，不能继续完成节点。")
    if node_instance.engine_state != WorkflowNodeEngineState.ACTIVATED:
      raise ConflictError("只有处于 ACTIVATED 状态的节点才能完成。")
    if node_instance.assignee_user_id is not None and node_instance.assignee_user_id != actor_id:
      raise ConflictError("只有当前受理人才能完成节点。")

    if context_updates:
      context_changed = self._apply_context_updates(
        graph_instance=graph_instance,
        context_updates=context_updates,
      )
      if context_changed:
        graph_instance.context_version += 1

    now = datetime.now(UTC)
    node_instance.engine_state = WorkflowNodeEngineState.COMPLETED
    node_instance.business_state = WorkflowNodeBusinessState.DONE
    node_instance.completed_at = now
    node_instance.node_instance_version += 1
    await self._session.flush()

    context = graph_instance.context if isinstance(graph_instance.context, dict) else {}
    if context.get("run_kind"):
      await WorkflowRunEventService(self._session).append(
        instance_id=graph_instance.id,
        event_type="node_completed",
        actor_user_id=actor_id,
        payload={
          "node_instance_id": str(node_instance.id),
          "node_key": node_instance.node_key,
          "instance_key": node_instance.instance_key,
        },
      )

    await self._activate_downstream(
      graph_instance=graph_instance,
      completed_node_instance=node_instance,
      now=now,
    )
    await self._session.commit()

  async def _resolve_outgoing_edges(
    self,
    *,
    graph_instance: WorkflowGraphInstance,
    completed_node_instance: WorkflowNodeInstance,
  ) -> list[WorkflowGraphTemplateEdge | RuntimeDefinitionEdge]:
    """Resolve forward edges; realign stale template_node_id via node_key when seed topology syncs."""
    if graph_instance.executor_kind == SNAPSHOT_EXECUTOR_KIND:
      return [
        edge
        for edge in runtime_edges(graph_instance.definition_snapshot)
        if edge.from_node_key == completed_node_instance.node_key and not edge.is_reject_path
      ]

    template_node_id = completed_node_instance.template_node_id
    if template_node_id is not None:
      outgoing_edges = list(
        await self._session.scalars(
          select(WorkflowGraphTemplateEdge).where(
            WorkflowGraphTemplateEdge.from_node_id == template_node_id,
            WorkflowGraphTemplateEdge.is_reject_path.is_(False),
          )
        )
      )
      if outgoing_edges:
        return outgoing_edges

    if graph_instance.template_id is None:
      return []

    live_template_node = await self._session.scalar(
      select(WorkflowGraphTemplateNode).where(
        WorkflowGraphTemplateNode.template_id == graph_instance.template_id,
        WorkflowGraphTemplateNode.node_key == completed_node_instance.node_key,
      )
    )
    if live_template_node is None:
      return []

    if completed_node_instance.template_node_id != live_template_node.id:
      completed_node_instance.template_node_id = live_template_node.id

    return list(
      await self._session.scalars(
        select(WorkflowGraphTemplateEdge).where(
          WorkflowGraphTemplateEdge.from_node_id == live_template_node.id,
          WorkflowGraphTemplateEdge.is_reject_path.is_(False),
        )
      )
    )

  async def _ensure_missing_template_node_instances(
    self,
    *,
    graph_instance: WorkflowGraphInstance,
  ) -> None:
    """Materialize PENDING node instances when template tail nodes were added after fork."""
    if graph_instance.executor_kind == SNAPSHOT_EXECUTOR_KIND:
      return
    if graph_instance.template_id is None:
      return

    template_nodes = list(
      await self._session.scalars(
        select(WorkflowGraphTemplateNode)
        .where(WorkflowGraphTemplateNode.template_id == graph_instance.template_id)
        .order_by(WorkflowGraphTemplateNode.sort_order.asc())
      )
    )
    if not template_nodes:
      return

    existing_keys = set(
      await self._session.scalars(
        select(WorkflowNodeInstance.node_key).where(
          WorkflowNodeInstance.instance_id == graph_instance.id,
        )
      )
    )

    for template_node in template_nodes:
      if template_node.node_key in existing_keys:
        continue
      self._session.add(
        WorkflowNodeInstance(
          instance_id=graph_instance.id,
          template_node_id=template_node.id,
          node_key=template_node.node_key,
          title=template_node.title,
          node_type=template_node.node_type,
          engine_state=WorkflowNodeEngineState.PENDING,
          business_state=WorkflowNodeBusinessState.DRAFT,
          iteration=1,
          node_instance_version=1,
          config=dict(template_node.config or {}),
        )
      )

    await self._session.flush()

  async def _all_template_nodes_completed(
    self,
    *,
    graph_instance: WorkflowGraphInstance,
  ) -> bool:
    if graph_instance.executor_kind == SNAPSHOT_EXECUTOR_KIND:
      template_node_keys = {
        node.node_key for node in runtime_nodes(graph_instance.definition_snapshot)
      }
    elif graph_instance.template_id is None:
      return True
    else:
      template_node_keys = set(
        await self._session.scalars(
          select(WorkflowGraphTemplateNode.node_key).where(
            WorkflowGraphTemplateNode.template_id == graph_instance.template_id,
          )
        )
      )
    if not template_node_keys:
      return True

    terminal_keys = set(
      await self._session.scalars(
        select(WorkflowNodeInstance.node_key).where(
          WorkflowNodeInstance.instance_id == graph_instance.id,
          WorkflowNodeInstance.engine_state.in_(
            [WorkflowNodeEngineState.COMPLETED, WorkflowNodeEngineState.TERMINATED]
          ),
        )
      )
    )
    return template_node_keys.issubset(terminal_keys)

  async def _activate_downstream(
    self,
    *,
    graph_instance: WorkflowGraphInstance,
    completed_node_instance: WorkflowNodeInstance,
    now: datetime,
  ) -> None:
    """检查并激活下游节点，支持 join_mode=all 与 join_mode=any。"""
    instance_id = completed_node_instance.instance_id
    template_node_id = completed_node_instance.template_node_id
    if template_node_id is None and not completed_node_instance.node_key:
      # 单步手动任务，没有模板节点，直接收口实例
      await self._maybe_complete_instance(graph_instance=graph_instance, now=now)
      return

    await self._ensure_missing_template_node_instances(graph_instance=graph_instance)

    outgoing_edges = await self._resolve_outgoing_edges(
      graph_instance=graph_instance,
      completed_node_instance=completed_node_instance,
    )

    if not outgoing_edges:
      # 叶节点，检查整个实例是否都完成
      await self._maybe_complete_instance(graph_instance=graph_instance, now=now)
      return

    downstream_node_ids = self._resolve_routable_downstream_node_ids(
      outgoing_edges=outgoing_edges,
      context=graph_instance.context,
    )

    if not downstream_node_ids:
      await self._maybe_complete_instance(graph_instance=graph_instance, now=now)
      return

    activated_notice_nodes: list[WorkflowNodeInstance] = []
    initiator: User | None = None
    template: WorkflowGraphTemplate | Any | None = None
    snapshot_node_by_id: dict[UUID, RuntimeDefinitionNode] = {}
    if graph_instance.executor_kind == SNAPSHOT_EXECUTOR_KIND:
      template = runtime_template(graph_instance.definition_snapshot)
      snapshot_node_by_id = {
        node.id: node for node in runtime_nodes(graph_instance.definition_snapshot)
      }
      initiator = await self._session.get(User, graph_instance.initiator_user_id)
      if initiator is not None:
        ensure_active_user(initiator)
    elif graph_instance.template_id is not None:
      template = await self._session.get(WorkflowGraphTemplate, graph_instance.template_id)
      initiator = await self._session.get(User, graph_instance.initiator_user_id)
      if initiator is not None:
        ensure_active_user(initiator)

    instance_context = graph_instance.context if isinstance(graph_instance.context, dict) else {}

    for downstream_template_node_id in downstream_node_ids:
      if graph_instance.executor_kind == SNAPSHOT_EXECUTOR_KIND:
        downstream_template_node = snapshot_node_by_id.get(downstream_template_node_id)
      else:
        downstream_template_node = await self._session.get(
          WorkflowGraphTemplateNode, downstream_template_node_id
        )
      if downstream_template_node is None:
        continue

      # 找出这个下游节点对应的实例节点（使用 FOR UPDATE 防止并发激活）
      downstream_ni: WorkflowNodeInstance | None = await self._session.scalar(
        select(WorkflowNodeInstance)
        .where(
          WorkflowNodeInstance.instance_id == instance_id,
          WorkflowNodeInstance.template_node_id == downstream_template_node_id,
          WorkflowNodeInstance.engine_state == WorkflowNodeEngineState.PENDING,
        )
        .with_for_update(skip_locked=True)
      )
      if downstream_ni is None:
        # In-place template seed can add new template_node rows while historical runs
        # still carry pending node_instances keyed by node_key only.
        downstream_ni = await self._session.scalar(
          select(WorkflowNodeInstance)
          .where(
            WorkflowNodeInstance.instance_id == instance_id,
            WorkflowNodeInstance.node_key == downstream_template_node.node_key,
            WorkflowNodeInstance.engine_state == WorkflowNodeEngineState.PENDING,
          )
          .with_for_update(skip_locked=True)
        )
        if downstream_ni is not None:
          downstream_ni.template_node_id = downstream_template_node_id
      if downstream_ni is None:
        # 已经激活或已完成，跳过
        continue

      # Wait-All: 检查所有上游节点是否均已完成
      if graph_instance.executor_kind == SNAPSHOT_EXECUTOR_KIND:
        incoming_edges = [
          edge
          for edge in runtime_edges(graph_instance.definition_snapshot)
          if edge.to_node_id == downstream_template_node_id and not edge.is_reject_path
        ]
      else:
        incoming_edges = list(
          await self._session.scalars(
            select(WorkflowGraphTemplateEdge)
            .where(
              WorkflowGraphTemplateEdge.to_node_id == downstream_template_node_id,
              WorkflowGraphTemplateEdge.is_reject_path.is_(False),
            )
          )
        )
      upstream_template_node_ids = {edge.from_node_id for edge in incoming_edges}

      can_activate = await self._upstream_join_satisfied(
        instance_id=instance_id,
        downstream_template_node=downstream_template_node,
        incoming_edges=incoming_edges,
      )
      if not can_activate:
        continue

      join_mode = (downstream_template_node.join_mode or "all").strip().lower()

      # 激活下游节点
      downstream_ni.engine_state = WorkflowNodeEngineState.ACTIVATED
      downstream_ni.business_state = WorkflowNodeBusinessState.ASSIGNED
      downstream_ni.activated_at = now
      downstream_ni.node_instance_version += 1

      if (
        downstream_ni.assignee_user_id is None
        and template is not None
        and initiator is not None
        and downstream_template_node is not None
      ):
        downstream_ni.assignee_user_id = await resolve_node_assignee_id(
          self._session,
          actor=initiator,
          template=template,
          template_node=downstream_template_node,
          node_instance=downstream_ni,
          context=instance_context,
          department_id=graph_instance.department_id,
        )

      if join_mode == "any":
        await self._terminate_wait_any_peer_nodes(
          instance_id=instance_id,
          upstream_template_node_ids=upstream_template_node_ids,
          winner_node_instance_id=completed_node_instance.id,
          now=now,
        )

      if downstream_template_node.node_type == WorkflowGraphNodeType.NOTICE:
        activated_notice_nodes.append(downstream_ni)

    graph_instance.current_node_key = await self._resolve_current_node_key(
      graph_instance=graph_instance,
    )

    await self._session.flush()
    await self._auto_complete_notice_nodes(
      graph_instance=graph_instance,
      notice_nodes=activated_notice_nodes,
      now=now,
    )
    await self._maybe_complete_instance(graph_instance=graph_instance, now=now)

  async def _upstream_join_satisfied(
    self,
    *,
    instance_id: UUID,
    downstream_template_node: WorkflowGraphTemplateNode | RuntimeDefinitionNode,
    incoming_edges: list[WorkflowGraphTemplateEdge | RuntimeDefinitionEdge],
  ) -> bool:
    """Evaluate join gates; multi_instance upstream requires every peer instance completed (W4)."""
    upstream_template_node_ids = {edge.from_node_id for edge in incoming_edges}
    if not upstream_template_node_ids:
      return True

    join_mode = (downstream_template_node.join_mode or "all").strip().lower()
    if join_mode not in {"all", "any"}:
      raise ConflictError(
        f"下游节点 '{downstream_template_node.node_key}' 使用了不支持的 join_mode：{downstream_template_node.join_mode}。"
      )

    branch_results: list[bool] = []
    for upstream_tpl_id in upstream_template_node_ids:
      upstream_instances = list(
        await self._session.scalars(
          select(WorkflowNodeInstance).where(
            WorkflowNodeInstance.instance_id == instance_id,
            WorkflowNodeInstance.template_node_id == upstream_tpl_id,
          )
        )
      )
      if not upstream_instances:
        branch_results.append(False)
        continue

      upstream_kind = "single"
      for upstream_instance in upstream_instances:
        if isinstance(upstream_instance.config, dict):
          upstream_kind = str(upstream_instance.config.get("kind") or "single")
          break

      completed_count = sum(
        1
        for node_instance in upstream_instances
        if node_instance.engine_state == WorkflowNodeEngineState.COMPLETED
      )
      if upstream_kind == "multi_instance":
        branch_results.append(completed_count == len(upstream_instances) and completed_count > 0)
      else:
        branch_results.append(completed_count > 0)

    if join_mode == "all":
      return all(branch_results)
    return any(branch_results)

  async def progress_from_completed_node(
    self,
    *,
    node_instance_id: UUID,
  ) -> list[WorkflowNodeInstance]:
    """Advance downstream nodes when the current node is already marked COMPLETED."""
    node_instance: WorkflowNodeInstance | None = await self._session.scalar(
      select(WorkflowNodeInstance)
      .where(WorkflowNodeInstance.id == node_instance_id)
      .with_for_update()
    )
    if node_instance is None:
      raise NotFoundError("节点实例不存在。")

    graph_instance = await self._lock_graph_instance(instance_id=node_instance.instance_id)
    self._ensure_snapshot_integrity(graph_instance)
    if graph_instance.status != WorkflowGraphInstanceStatus.ACTIVE:
      return []
    if node_instance.engine_state != WorkflowNodeEngineState.COMPLETED:
      raise ConflictError("节点尚未完成，无法推进下游。")

    pending_ids = set(
      await self._session.scalars(
        select(WorkflowNodeInstance.id).where(
          WorkflowNodeInstance.instance_id == node_instance.instance_id,
          WorkflowNodeInstance.engine_state == WorkflowNodeEngineState.PENDING,
        )
      )
    )

    now = datetime.now(UTC)
    await self._activate_downstream(
      graph_instance=graph_instance,
      completed_node_instance=node_instance,
      now=now,
    )
    await self._session.flush()

    if not pending_ids:
      return []

    return list(
      await self._session.scalars(
        select(WorkflowNodeInstance).where(
          WorkflowNodeInstance.id.in_(pending_ids),
          WorkflowNodeInstance.engine_state == WorkflowNodeEngineState.ACTIVATED,
        )
      )
    )

  async def _terminate_wait_any_peer_nodes(
    self,
    *,
    instance_id: UUID,
    upstream_template_node_ids: set[UUID],
    winner_node_instance_id: UUID,
    now: datetime,
  ) -> None:
    """Wait-Any 场景下终止同批次未完成节点，收回办理权限。"""
    if not upstream_template_node_ids:
      return

    peer_nodes: list[WorkflowNodeInstance] = list(
      await self._session.scalars(
        select(WorkflowNodeInstance)
        .where(
          WorkflowNodeInstance.instance_id == instance_id,
          WorkflowNodeInstance.template_node_id.in_(upstream_template_node_ids),
          WorkflowNodeInstance.id != winner_node_instance_id,
          WorkflowNodeInstance.engine_state.in_(
            [WorkflowNodeEngineState.ACTIVATED, WorkflowNodeEngineState.ACKNOWLEDGED]
          ),
        )
        .with_for_update(skip_locked=True)
      )
    )

    for peer in peer_nodes:
      peer.engine_state = WorkflowNodeEngineState.TERMINATED
      peer.business_state = WorkflowNodeBusinessState.CANCELLED
      peer.terminated_at = now
      peer.node_instance_version += 1

      config = dict(peer.config or {})
      config["system_resolution"] = {
        "reason": "wait_any_race_cancelled",
        "resolved_by_node_instance_id": str(winner_node_instance_id),
        "resolved_at": now.isoformat(),
      }
      peer.config = config

    if peer_nodes:
      await self._session.flush()

  def _apply_context_updates(
    self,
    *,
    graph_instance: WorkflowGraphInstance,
    context_updates: dict[str, Any],
  ) -> bool:
    current_context = dict(graph_instance.context or {})
    changed = False
    for key, value in context_updates.items():
      if value is None:
        if key in current_context:
          current_context.pop(key, None)
          changed = True
        continue

      if current_context.get(key) != value:
        current_context[key] = value
        changed = True

    if changed:
      graph_instance.context = current_context
    return changed

  def _resolve_routable_downstream_node_ids(
    self,
    *,
    outgoing_edges: list[WorkflowGraphTemplateEdge | RuntimeDefinitionEdge],
    context: dict[str, Any],
  ) -> set[UUID]:
    matched_edges: list[WorkflowGraphTemplateEdge | RuntimeDefinitionEdge] = []
    else_edges: list[WorkflowGraphTemplateEdge | RuntimeDefinitionEdge] = []

    for edge in sorted(outgoing_edges, key=lambda item: item.priority):
      condition = dict(edge.condition or {})
      if is_else_condition(condition):
        else_edges.append(edge)
        continue
      if evaluate_condition(condition, context):
        matched_edges.append(edge)

    selected = matched_edges or else_edges
    return {edge.to_node_id for edge in selected}

  async def _auto_complete_activated_notice_nodes(
    self,
    *,
    graph_instance: WorkflowGraphInstance,
    now: datetime,
  ) -> None:
    activated_notice_nodes = list(
      await self._session.scalars(
        select(WorkflowNodeInstance).where(
          WorkflowNodeInstance.instance_id == graph_instance.id,
          WorkflowNodeInstance.node_type == WorkflowGraphNodeType.NOTICE,
          WorkflowNodeInstance.engine_state == WorkflowNodeEngineState.ACTIVATED,
        )
      )
    )
    await self._auto_complete_notice_nodes(
      graph_instance=graph_instance,
      notice_nodes=activated_notice_nodes,
      now=now,
    )

  async def _auto_complete_notice_nodes(
    self,
    *,
    graph_instance: WorkflowGraphInstance,
    notice_nodes: list[WorkflowNodeInstance],
    now: datetime,
  ) -> None:
    for notice_node in notice_nodes:
      if notice_node.engine_state != WorkflowNodeEngineState.ACTIVATED:
        continue
      notice_node.engine_state = WorkflowNodeEngineState.COMPLETED
      notice_node.business_state = WorkflowNodeBusinessState.DONE
      notice_node.completed_at = now
      notice_node.node_instance_version += 1
      await self._session.flush()

      await self._activate_downstream(
        graph_instance=graph_instance,
        completed_node_instance=notice_node,
        now=now,
      )

  async def _maybe_complete_instance(
    self,
    *,
    graph_instance: WorkflowGraphInstance,
    now: datetime,
  ) -> None:
    """当实例的所有节点均已完成时，将实例状态置为 COMPLETED。"""
    pending_or_active_count = (
      await self._session.scalar(
        select(WorkflowNodeInstance.id)
        .where(
          WorkflowNodeInstance.instance_id == graph_instance.id,
          WorkflowNodeInstance.engine_state.in_(
            [WorkflowNodeEngineState.PENDING, WorkflowNodeEngineState.ACTIVATED, WorkflowNodeEngineState.ACKNOWLEDGED]
          ),
        )
        .limit(1)
      )
    )
    if pending_or_active_count is not None:
      return  # 还有未完成的节点

    if not await self._all_template_nodes_completed(graph_instance=graph_instance):
      return  # 模板尾节点尚未 materialize 或完成（避免 N10 后直接归档）

    if graph_instance.status == WorkflowGraphInstanceStatus.ACTIVE:
      context = dict(graph_instance.context or {})
      if context.get("run_kind") == "production":
        context["archived"] = True
        context["archived_at"] = now.isoformat()
        graph_instance.context = context
      graph_instance.status = WorkflowGraphInstanceStatus.COMPLETED
      graph_instance.completed_at = now
      graph_instance.current_node_key = None
      await self._session.flush()
      from app.services.workflow_graph_template_chain_service import maybe_trigger_template_chain

      await maybe_trigger_template_chain(self._session, instance=graph_instance)

  async def collect_projection_task_ids(self, *, instance_id: UUID) -> set[UUID]:
    """Task ids linked to a graph instance (ROOT + node projection tasks)."""
    instance = await self._session.get(WorkflowGraphInstance, instance_id)
    if instance is None:
      return set()

    task_ids: set[UUID] = set()
    if instance.source_id is not None:
      task_ids.add(instance.source_id)

    node_instances = list(
      await self._session.scalars(
        select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == instance_id)
      )
    )
    for node_instance in node_instances:
      config = node_instance.config if isinstance(node_instance.config, dict) else {}
      raw_task_id = config.get("task_id")
      if isinstance(raw_task_id, str) and raw_task_id.strip():
        try:
          task_ids.add(UUID(raw_task_id.strip()))
        except ValueError:
          continue
    return task_ids

  async def _cancel_single_instance_by_admin(
    self,
    *,
    actor_id: UUID,
    instance_id: UUID,
    reason: str,
    now: datetime,
  ) -> set[UUID]:
    graph_instance = await self._lock_graph_instance(instance_id=instance_id)
    if graph_instance.status not in {
      WorkflowGraphInstanceStatus.CANCELLED,
      WorkflowGraphInstanceStatus.TERMINATED,
      WorkflowGraphInstanceStatus.COMPLETED,
    }:
      node_instances = list(
        await self._session.scalars(
          select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == instance_id)
        )
      )
      for node_instance in node_instances:
        if node_instance.engine_state in {
          WorkflowNodeEngineState.COMPLETED,
          WorkflowNodeEngineState.TERMINATED,
        }:
          continue
        node_instance.engine_state = WorkflowNodeEngineState.TERMINATED
        node_instance.business_state = WorkflowNodeBusinessState.CANCELLED
        node_instance.terminated_at = now
        node_instance.completed_at = node_instance.completed_at or now
        node_instance.node_instance_version += 1

      context = dict(graph_instance.context or {})
      context["admin_archived"] = True
      context["admin_archived_at"] = now.isoformat()
      context["admin_archived_by_user_id"] = str(actor_id)
      context["admin_archive_reason"] = reason
      run_kind = str(context.get("run_kind") or "")
      if run_kind == "production":
        context["archived"] = True
        context["archived_at"] = now.isoformat()
      graph_instance.context = context
      graph_instance.status = WorkflowGraphInstanceStatus.CANCELLED
      graph_instance.cancelled_at = now
      graph_instance.completed_at = graph_instance.completed_at or now
      graph_instance.current_node_key = None
      await self._session.flush()

      await WorkflowRunEventService(self._session).append(
        instance_id=graph_instance.id,
        event_type="admin_cancelled",
        actor_user_id=actor_id,
        payload={
          "reason": reason,
          "run_kind": run_kind or None,
        },
      )

    return await self.collect_projection_task_ids(instance_id=instance_id)

  async def cancel_instance_by_admin(
    self,
    *,
    actor_id: UUID,
    instance_id: UUID,
    reason: str,
    cancel_active_child_runs: bool = False,
  ) -> tuple[set[UUID], list[UUID]]:
    """Terminate a workflow graph run and return linked task ids + cancelled instance ids."""
    normalized_reason = reason.strip()
    if not normalized_reason:
      raise ConflictError("归档时必须填写原因。")

    now = datetime.now(UTC)
    cancelled_instance_ids: list[UUID] = []
    task_ids: set[UUID] = set()

    task_ids |= await self._cancel_single_instance_by_admin(
      actor_id=actor_id,
      instance_id=instance_id,
      reason=normalized_reason,
      now=now,
    )
    cancelled_instance_ids.append(instance_id)

    if cancel_active_child_runs:
      child_instance_ids = list(
        await self._session.scalars(
          select(WorkflowGraphInstance.id).where(
            WorkflowGraphInstance.parent_instance_id == instance_id,
            WorkflowGraphInstance.status.in_(
              [
                WorkflowGraphInstanceStatus.PENDING,
                WorkflowGraphInstanceStatus.ACTIVE,
              ]
            ),
          )
        )
      )
      for child_instance_id in child_instance_ids:
        task_ids |= await self._cancel_single_instance_by_admin(
          actor_id=actor_id,
          instance_id=child_instance_id,
          reason=normalized_reason,
          now=now,
        )
        cancelled_instance_ids.append(child_instance_id)

    return task_ids, cancelled_instance_ids

  # ------------------------------------------------------------------ #
  # Phase 6 / Query helpers
  # ------------------------------------------------------------------ #

  async def get_instance(self, *, instance_id: UUID) -> WorkflowGraphInstance:
    instance: WorkflowGraphInstance | None = await self._session.scalar(
      select(WorkflowGraphInstance).where(WorkflowGraphInstance.id == instance_id)
    )
    if instance is None:
      raise NotFoundError("工作流图实例不存在。")
    return instance

  async def list_active_templates(self) -> list[WorkflowGraphTemplate]:
    return list(
      await self._session.scalars(
        select(WorkflowGraphTemplate)
        .where(WorkflowGraphTemplate.status == WorkflowGraphTemplateStatus.ACTIVE)
        .order_by(WorkflowGraphTemplate.code.asc())
      )
    )

  async def list_child_instances(
    self,
    *,
    parent_instance_id: UUID,
    limit: int = 50,
    include_completed: bool = False,
  ) -> list[WorkflowGraphInstance]:
    await self.get_instance(instance_id=parent_instance_id)
    normalized_limit = max(1, min(limit, 100))
    query = (
      select(WorkflowGraphInstance)
      .where(WorkflowGraphInstance.parent_instance_id == parent_instance_id)
      .order_by(WorkflowGraphInstance.created_at.asc())
      .limit(normalized_limit)
    )
    if not include_completed:
      query = query.where(WorkflowGraphInstance.status != WorkflowGraphInstanceStatus.COMPLETED)
    return list(await self._session.scalars(query))

  async def list_instances_for_template(
    self,
    *,
    template_id: UUID,
    limit: int = 10,
  ) -> list[WorkflowGraphInstance]:
    template_exists = await self._session.scalar(
      select(WorkflowGraphTemplate.id).where(WorkflowGraphTemplate.id == template_id)
    )
    if template_exists is None:
      raise NotFoundError("工作流图模板不存在。")

    normalized_limit = max(1, min(limit, 50))
    return list(
      await self._session.scalars(
        select(WorkflowGraphInstance)
        .where(WorkflowGraphInstance.template_id == template_id)
        .order_by(WorkflowGraphInstance.created_at.desc())
        .limit(normalized_limit)
      )
    )

  async def list_node_instances_for_graph(
    self,
    *,
    instance_id: UUID,
  ) -> list[WorkflowNodeInstance]:
    return list(
      await self._session.scalars(
        select(WorkflowNodeInstance)
        .where(WorkflowNodeInstance.instance_id == instance_id)
        .order_by(WorkflowNodeInstance.created_at.asc())
      )
    )

  async def list_department_runs(
    self,
    *,
    department_id: UUID,
    limit: int = 50,
    include_completed: bool = True,
  ) -> list[DepartmentRunSummary]:
    normalized_limit = max(1, min(limit, 100))
    query = (
      select(WorkflowGraphInstance)
      .where(
        WorkflowGraphInstance.department_id == department_id,
        WorkflowGraphInstance.parent_instance_id.is_(None),
      )
      .order_by(WorkflowGraphInstance.created_at.desc())
      .limit(normalized_limit)
    )
    if not include_completed:
      query = query.where(WorkflowGraphInstance.status != WorkflowGraphInstanceStatus.COMPLETED)
    instances = list(await self._session.scalars(query))
    if not instances:
      return []

    instance_ids = [instance.id for instance in instances]
    counts_raw = await self._session.execute(
      select(WorkflowRunEvent.instance_id, func.count())
      .where(WorkflowRunEvent.instance_id.in_(instance_ids))
      .group_by(WorkflowRunEvent.instance_id)
    )
    event_counts = {row[0]: int(row[1]) for row in counts_raw}

    summaries: list[DepartmentRunSummary] = []
    for instance in instances:
      run_label = instance.run_label
      if (not run_label or not str(run_label).strip()) and isinstance(instance.context, dict):
        raw = instance.context.get("run_label")
        if raw is not None:
          run_label = str(raw)
      summaries.append(
        DepartmentRunSummary(
          instance_id=instance.id,
          run_label=str(run_label).strip() if run_label else None,
          status=instance.status,
          created_at=instance.created_at,
          event_count=event_counts.get(instance.id, 0),
          department_id=instance.department_id,
        )
      )
    return summaries
