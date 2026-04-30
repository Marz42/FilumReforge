from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
  TaskPriority,
  WorkflowGraphInstanceStatus,
  WorkflowGraphNodeType,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.models import (
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateEdge,
  WorkflowGraphTemplateNode,
  WorkflowNodeInstance,
)


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
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

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

    template_nodes = list(
      await self._session.scalars(
        select(WorkflowGraphTemplateNode)
        .where(WorkflowGraphTemplateNode.template_id == graph_instance.template_id)
        .order_by(WorkflowGraphTemplateNode.sort_order.asc())
      )
    )
    if not template_nodes:
      raise ConflictError("当前模板没有可用节点，无法执行深度打回。")

    template_node_by_key = {node.node_key: node for node in template_nodes}
    target_template_node = template_node_by_key.get(target_node_key)
    if target_template_node is None:
      raise ConflictError("目标节点不存在于当前模板中。")

    edges = list(
      await self._session.scalars(
        select(WorkflowGraphTemplateEdge).where(
          WorkflowGraphTemplateEdge.template_id == graph_instance.template_id,
          WorkflowGraphTemplateEdge.is_reject_path.is_(False),
        )
      )
    )

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

    return graph_instance.id

  def _collect_reachable_template_node_ids(
    self,
    *,
    start_node_id: UUID,
    edges: list[WorkflowGraphTemplateEdge],
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

  async def _resolve_current_node_key(self, *, instance_id: UUID) -> str | None:
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

    # 计算每个节点的入度
    in_degree: dict[UUID, int] = {node.id: 0 for node in nodes}
    for edge in edges:
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
      return  # 幂等保护
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

    await self._activate_downstream(
      graph_instance=graph_instance,
      completed_node_instance=node_instance,
      now=now,
    )

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
    if template_node_id is None:
      # 单步手动任务，没有模板节点，直接收口实例
      await self._maybe_complete_instance(graph_instance=graph_instance, now=now)
      return

    # 找出本节点在模板中的出边（即下游节点的 template_node_id）
    outgoing_edges: list[WorkflowGraphTemplateEdge] = list(
      await self._session.scalars(
        select(WorkflowGraphTemplateEdge)
        .where(
          WorkflowGraphTemplateEdge.from_node_id == template_node_id,
          WorkflowGraphTemplateEdge.is_reject_path.is_(False),
        )
      )
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

    for downstream_template_node_id in downstream_node_ids:
      downstream_template_node: WorkflowGraphTemplateNode | None = await self._session.get(
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
        # 已经激活或已完成，跳过
        continue

      # Wait-All: 检查所有上游节点是否均已完成
      incoming_edges: list[WorkflowGraphTemplateEdge] = list(
        await self._session.scalars(
          select(WorkflowGraphTemplateEdge)
          .where(
            WorkflowGraphTemplateEdge.to_node_id == downstream_template_node_id,
            WorkflowGraphTemplateEdge.is_reject_path.is_(False),
          )
        )
      )
      upstream_template_node_ids = {edge.from_node_id for edge in incoming_edges}

      completed_upstream_ids = set(
        await self._session.scalars(
          select(WorkflowNodeInstance.template_node_id)
          .where(
            WorkflowNodeInstance.instance_id == instance_id,
            WorkflowNodeInstance.template_node_id.in_(upstream_template_node_ids),
            WorkflowNodeInstance.engine_state == WorkflowNodeEngineState.COMPLETED,
          )
        )
      )

      join_mode = (downstream_template_node.join_mode or "all").strip().lower()
      can_activate = False
      if join_mode == "all":
        can_activate = upstream_template_node_ids == completed_upstream_ids
      elif join_mode == "any":
        # Wait-Any: 任一上游先完成即满足激活条件。
        can_activate = bool(completed_upstream_ids.intersection(upstream_template_node_ids))
      else:
        raise ConflictError(
          f"下游节点 '{downstream_template_node.node_key}' 使用了不支持的 join_mode：{downstream_template_node.join_mode}。"
        )

      if not can_activate:
        continue

      # 激活下游节点
      downstream_ni.engine_state = WorkflowNodeEngineState.ACTIVATED
      downstream_ni.business_state = WorkflowNodeBusinessState.ASSIGNED
      downstream_ni.activated_at = now
      downstream_ni.node_instance_version += 1

      if join_mode == "any":
        await self._terminate_wait_any_peer_nodes(
          instance_id=instance_id,
          upstream_template_node_ids=upstream_template_node_ids,
          winner_node_instance_id=completed_node_instance.id,
          now=now,
        )

      if downstream_template_node.node_type == WorkflowGraphNodeType.NOTICE:
        activated_notice_nodes.append(downstream_ni)

    graph_instance.current_node_key = await self._resolve_current_node_key(instance_id=instance_id)

    await self._session.flush()
    await self._auto_complete_notice_nodes(
      graph_instance=graph_instance,
      notice_nodes=activated_notice_nodes,
      now=now,
    )
    await self._maybe_complete_instance(graph_instance=graph_instance, now=now)

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
    outgoing_edges: list[WorkflowGraphTemplateEdge],
    context: dict[str, Any],
  ) -> set[UUID]:
    matched_edges: list[WorkflowGraphTemplateEdge] = []
    else_edges: list[WorkflowGraphTemplateEdge] = []

    for edge in sorted(outgoing_edges, key=lambda item: item.priority):
      condition = dict(edge.condition or {})
      if self._is_else_condition(condition):
        else_edges.append(edge)
        continue
      if self._evaluate_condition(condition=condition, context=context):
        matched_edges.append(edge)

    selected = matched_edges or else_edges
    return {edge.to_node_id for edge in selected}

  def _is_else_condition(self, condition: dict[str, Any]) -> bool:
    return bool(condition.get("else") is True or condition.get("type") == "else")

  def _evaluate_condition(
    self,
    *,
    condition: dict[str, Any],
    context: dict[str, Any],
  ) -> bool:
    if not condition:
      return True

    all_conditions = condition.get("all")
    if isinstance(all_conditions, list):
      return all(
        self._evaluate_condition(condition=item, context=context)
        for item in all_conditions
        if isinstance(item, dict)
      )

    any_conditions = condition.get("any")
    if isinstance(any_conditions, list):
      return any(
        self._evaluate_condition(condition=item, context=context)
        for item in any_conditions
        if isinstance(item, dict)
      )

    field_name = condition.get("field")
    if not isinstance(field_name, str) or not field_name:
      return False

    actual_value = self._resolve_context_value(context=context, field_path=field_name)
    operator = str(condition.get("operator") or "eq").lower()
    expected_value = condition.get("value")

    if operator == "eq":
      return actual_value == expected_value
    if operator == "neq":
      return actual_value != expected_value
    if operator == "gt":
      return self._safe_compare(actual_value, expected_value, compare="gt")
    if operator == "gte":
      return self._safe_compare(actual_value, expected_value, compare="gte")
    if operator == "lt":
      return self._safe_compare(actual_value, expected_value, compare="lt")
    if operator == "lte":
      return self._safe_compare(actual_value, expected_value, compare="lte")
    if operator == "in":
      return isinstance(expected_value, list) and actual_value in expected_value
    if operator == "not_in":
      return isinstance(expected_value, list) and actual_value not in expected_value
    if operator == "contains":
      if isinstance(actual_value, list):
        return expected_value in actual_value
      if isinstance(actual_value, str) and isinstance(expected_value, str):
        return expected_value in actual_value
      return False
    if operator == "exists":
      return actual_value is not None

    return False

  def _resolve_context_value(self, *, context: dict[str, Any], field_path: str) -> Any:
    value: Any = context
    for part in field_path.split("."):
      if not isinstance(value, dict) or part not in value:
        return None
      value = value[part]
    return value

  def _safe_compare(self, actual_value: Any, expected_value: Any, *, compare: str) -> bool:
    try:
      if compare == "gt":
        return actual_value > expected_value
      if compare == "gte":
        return actual_value >= expected_value
      if compare == "lt":
        return actual_value < expected_value
      return actual_value <= expected_value
    except TypeError:
      return False

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

    if graph_instance.status == WorkflowGraphInstanceStatus.ACTIVE:
      graph_instance.status = WorkflowGraphInstanceStatus.COMPLETED
      graph_instance.completed_at = now
      graph_instance.current_node_key = None
      await self._session.flush()

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