from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
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
    - join_mode=any 目前不受支持，遇到时抛出 ConflictError（留待 Phase 8）。
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

    # Phase 8 guard: join_mode=any not yet supported
    for node in nodes:
      if node.join_mode == "any" and node.assignment_mode == "fan_out":
        raise ConflictError(
          f"节点 '{node.node_key}' 使用 join_mode=any，当前版本暂不支持，请等待 Phase 8 发布。"
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

    return MultiNodeWorkflowResult(instance=instance, node_instances=node_instances)

  async def complete_node_instance(
    self,
    *,
    node_instance_id: UUID,
    actor_id: UUID,
  ) -> None:
    """标记节点实例为已完成，并在事务中检查 / 激活下游节点。

    不支持 join_mode=any（Phase 8 保留）。
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
    if graph_instance.status != WorkflowGraphInstanceStatus.ACTIVE:
      raise ConflictError("当前工作流图实例已结束，不能继续完成节点。")
    if node_instance.engine_state != WorkflowNodeEngineState.ACTIVATED:
      raise ConflictError("只有处于 ACTIVATED 状态的节点才能完成。")
    if node_instance.assignee_user_id is not None and node_instance.assignee_user_id != actor_id:
      raise ConflictError("只有当前受理人才能完成节点。")

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
    """检查并激活下游节点。只处理 join_mode=all（Wait-All）和单入度顺序流。"""
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

    downstream_node_ids = {edge.to_node_id for edge in outgoing_edges}

    for downstream_template_node_id in downstream_node_ids:
      downstream_template_node: WorkflowGraphTemplateNode | None = await self._session.get(
        WorkflowGraphTemplateNode, downstream_template_node_id
      )
      if downstream_template_node is None:
        continue

      # Phase 8 guard
      if downstream_template_node.join_mode == "any":
        raise ConflictError(
          f"下游节点 '{downstream_template_node.node_key}' 使用 join_mode=any，当前版本暂不支持。"
        )

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

      all_upstream_done = upstream_template_node_ids == completed_upstream_ids
      if not all_upstream_done:
        continue

      # 激活下游节点
      downstream_ni.engine_state = WorkflowNodeEngineState.ACTIVATED
      downstream_ni.business_state = WorkflowNodeBusinessState.ASSIGNED
      downstream_ni.activated_at = now
      downstream_ni.node_instance_version += 1

    graph_instance.current_node_key = await self._resolve_current_node_key(instance_id=instance_id)

    await self._session.flush()
    await self._maybe_complete_instance(graph_instance=graph_instance, now=now)

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