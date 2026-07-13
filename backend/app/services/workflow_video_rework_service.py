"""Video workflow v1 targeted rework and rejection (W5)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
  TaskSourceType,
  TaskStatus,
  UserRole,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models import (
  Task,
  User,
  WorkflowDeliverable,
  WorkflowGraphInstance,
  WorkflowNodeInstance,
)
from app.schemas.workflow_video import (
  RejectCapturesResponse,
  RejectProductionStepResponse,
  RejectedCaptureItem,
  validate_node_config,
  validate_run_context,
)
from app.services.access_control import ensure_active_user
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_orchestration_service import WorkflowOrchestrationService
from app.services.workflow_run_event_service import WorkflowRunEventService

DEFAULT_PROPOSE_NODE_KEY = "N1_PROPOSE"
DEFAULT_AGGREGATE_NODE_KEY = "N2_AGGREGATE"


class WorkflowVideoReworkService:
  def __init__(
    self,
    session: AsyncSession,
    *,
    workflow_graph_service: WorkflowGraphService | None = None,
    orchestration_service: WorkflowOrchestrationService | None = None,
  ) -> None:
    self._session = session
    self._workflow_graph_service = workflow_graph_service or WorkflowGraphService(session)
    self._orchestration_service = orchestration_service or WorkflowOrchestrationService(
      session,
      workflow_graph_service=self._workflow_graph_service,
    )

  async def _ensure_reject_actor(self, *, actor: User, instance: WorkflowGraphInstance) -> None:
    if actor.role in {UserRole.ADMIN, UserRole.HR}:
      return
    if actor.id == instance.initiator_user_id:
      return

    context = instance.context if isinstance(instance.context, dict) else {}
    manager_id = context.get("manager_user_id")
    if manager_id is not None and str(manager_id) == str(actor.id):
      return

    aggregate_nodes = list(
      await self._session.scalars(
        select(WorkflowNodeInstance)
        .where(
          WorkflowNodeInstance.instance_id == instance.id,
          WorkflowNodeInstance.node_key == DEFAULT_AGGREGATE_NODE_KEY,
        )
        .order_by(WorkflowNodeInstance.iteration.desc())
      )
    )
    aggregate_node = aggregate_nodes[0] if aggregate_nodes else None
    if aggregate_node is not None and aggregate_node.assignee_user_id == actor.id:
      return

    raise AuthorizationError("当前账号不能打回采集内容。")

  async def _list_latest_propose_nodes(
    self,
    *,
    instance_id: UUID,
    source_node_key: str,
  ) -> list[WorkflowNodeInstance]:
    node_instances = list(
      await self._session.scalars(
        select(WorkflowNodeInstance)
        .where(
          WorkflowNodeInstance.instance_id == instance_id,
          WorkflowNodeInstance.node_key == source_node_key,
        )
        .order_by(
          WorkflowNodeInstance.instance_key.asc(),
          WorkflowNodeInstance.iteration.desc(),
          WorkflowNodeInstance.created_at.desc(),
        )
      )
    )
    latest_by_key: dict[str, WorkflowNodeInstance] = {}
    for node_instance in node_instances:
      key = node_instance.instance_key
      if key not in latest_by_key:
        latest_by_key[key] = node_instance
    return list(latest_by_key.values())

  async def _resolve_node_for_rejection(
    self,
    *,
    instance_id: UUID,
    source_node_key: str,
    item: RejectedCaptureItem,
  ) -> WorkflowNodeInstance:
    if item.instance_key is not None:
      normalized_key = str(item.instance_key).strip()
      matches = list(
        await self._session.scalars(
          select(WorkflowNodeInstance)
          .where(
            WorkflowNodeInstance.instance_id == instance_id,
            WorkflowNodeInstance.node_key == source_node_key,
            WorkflowNodeInstance.instance_key == normalized_key,
          )
          .order_by(WorkflowNodeInstance.iteration.desc())
        )
      )
      if not matches:
        raise NotFoundError(f"未找到 instance_key={normalized_key} 的采集节点。")
      return matches[0]

    assert item.topic_id is not None
    topic_id = str(item.topic_id)
    for node_instance in await self._list_latest_propose_nodes(
      instance_id=instance_id,
      source_node_key=source_node_key,
    ):
      deliverable = await self._session.scalar(
        select(WorkflowDeliverable).where(WorkflowDeliverable.node_instance_id == node_instance.id)
      )
      if deliverable is None or not isinstance(deliverable.payload, dict):
        continue
      raw_topics = deliverable.payload.get("topics")
      if not isinstance(raw_topics, list):
        continue
      for entry in raw_topics:
        if isinstance(entry, dict) and str(entry.get("topic_id")) == topic_id:
          return node_instance

    raise NotFoundError(f"未找到包含 topic_id={topic_id} 的采集提交。")

  async def _regress_aggregate_gate(self, *, instance: WorkflowGraphInstance) -> None:
    propose_nodes = await self._list_latest_propose_nodes(
      instance_id=instance.id,
      source_node_key=DEFAULT_PROPOSE_NODE_KEY,
    )
    if propose_nodes and all(
      node.engine_state == WorkflowNodeEngineState.COMPLETED for node in propose_nodes
    ):
      return

    aggregate_node = await self._session.scalar(
      select(WorkflowNodeInstance)
      .where(
        WorkflowNodeInstance.instance_id == instance.id,
        WorkflowNodeInstance.node_key == DEFAULT_AGGREGATE_NODE_KEY,
      )
      .order_by(WorkflowNodeInstance.iteration.desc())
      .limit(1)
    )
    if aggregate_node is None:
      return

    if aggregate_node.engine_state == WorkflowNodeEngineState.ACTIVATED:
      aggregate_node.engine_state = WorkflowNodeEngineState.PENDING
      aggregate_node.business_state = WorkflowNodeBusinessState.ASSIGNED
      aggregate_node.activated_at = None

    config = aggregate_node.config if isinstance(aggregate_node.config, dict) else {}
    raw_task_id = config.get("task_id")
    if raw_task_id is not None:
      aggregate_task = await self._session.get(Task, UUID(str(raw_task_id)))
      if aggregate_task is not None:
        aggregate_task.status = TaskStatus.TODO
        aggregate_task.updated_at = datetime.now(UTC)
        metadata = dict(aggregate_task.extra_metadata or {})
        metadata["gate_waiting_all_captures"] = True
        aggregate_task.extra_metadata = metadata

    instance.current_node_key = DEFAULT_PROPOSE_NODE_KEY

  async def _reopen_capture_node(
    self,
    *,
    actor: User,
    instance: WorkflowGraphInstance,
    node_instance: WorkflowNodeInstance,
    reason: str,
    topic_id: UUID | None = None,
  ) -> None:
    if node_instance.engine_state not in {
      WorkflowNodeEngineState.COMPLETED,
      WorkflowNodeEngineState.ACTIVATED,
    }:
      raise ConflictError("当前采集节点状态不允许打回。")

    now = datetime.now(UTC)
    node_instance.engine_state = WorkflowNodeEngineState.ACTIVATED
    node_instance.business_state = WorkflowNodeBusinessState.DOING
    node_instance.completed_at = None
    node_instance.activated_at = now
    node_instance.node_instance_version += 1

    config = dict(node_instance.config or {})
    config["targeted_rejection"] = {
      "reason": reason,
      "topic_id": str(topic_id) if topic_id is not None else None,
      "rejected_by_user_id": str(actor.id),
      "rejected_at": now.isoformat(),
    }
    node_instance.config = config

    deliverable = await self._session.scalar(
      select(WorkflowDeliverable).where(WorkflowDeliverable.node_instance_id == node_instance.id)
    )
    if deliverable is not None:
      payload = dict(deliverable.payload or {})
      history = payload.get("rejection_history")
      if not isinstance(history, list):
        history = []
      history.append(
        {
          "reason": reason,
          "topic_id": str(topic_id) if topic_id is not None else None,
          "rejected_at": now.isoformat(),
          "rejected_by_user_id": str(actor.id),
        }
      )
      payload["rejection_history"] = history
      if topic_id is not None and isinstance(payload.get("topics"), list):
        payload["topics"] = [
          entry
          for entry in payload["topics"]
          if not (
            isinstance(entry, dict) and str(entry.get("topic_id")) == str(topic_id)
          )
        ]
      deliverable.payload = payload
      deliverable.summary = f"打回补交：{reason}"

    raw_task_id = config.get("task_id")
    if raw_task_id is not None:
      task = await self._session.get(Task, UUID(str(raw_task_id)))
      if task is not None:
        task.status = TaskStatus.DOING
        task.updated_at = now
        metadata = dict(task.extra_metadata or {})
        metadata["latest_rework_reason"] = reason
        metadata["latest_capture_state"] = "rejected"
        metadata["latest_review_state"] = "returned_for_rework"
        metadata["rework_count"] = int(metadata.get("rework_count") or 0) + 1
        if topic_id is not None:
          metadata["rejected_topic_id"] = str(topic_id)
        task.extra_metadata = metadata

    await WorkflowRunEventService(self._session).append(
      instance_id=instance.id,
      event_type="capture_rejected",
      actor_user_id=actor.id,
      payload={
        "node_instance_id": str(node_instance.id),
        "instance_key": node_instance.instance_key,
        "topic_id": str(topic_id) if topic_id is not None else None,
        "reason": reason,
      },
    )

  async def apply_capture_rejections(
    self,
    *,
    actor: User,
    instance_id: UUID,
    rejections: list[RejectedCaptureItem],
    source_node_key: str = DEFAULT_PROPOSE_NODE_KEY,
  ) -> RejectCapturesResponse:
    ensure_active_user(actor)
    instance = await self._session.get(WorkflowGraphInstance, instance_id)
    if instance is None:
      raise NotFoundError("图实例不存在。")
    await self._ensure_reject_actor(actor=actor, instance=instance)

    reopened_keys: list[str] = []
    seen_keys: set[str] = set()

    for item in rejections:
      node_instance = await self._resolve_node_for_rejection(
        instance_id=instance_id,
        source_node_key=source_node_key,
        item=item,
      )
      if node_instance.instance_key in seen_keys:
        continue
      seen_keys.add(node_instance.instance_key)
      await self._reopen_capture_node(
        actor=actor,
        instance=instance,
        node_instance=node_instance,
        reason=item.reason.strip(),
        topic_id=item.topic_id,
      )
      reopened_keys.append(node_instance.instance_key)

    await self._regress_aggregate_gate(instance=instance)
    await self._session.commit()

    return RejectCapturesResponse(
      instance_id=instance_id,
      reopened_count=len(reopened_keys),
      reopened_instance_keys=reopened_keys,
    )

  async def reject_production_step(
    self,
    *,
    actor: User,
    task_id: UUID,
    reason: str,
    target_node_key: str | None = None,
  ) -> RejectProductionStepResponse:
    """W5-2: deep reject using node acceptance_spec (production template chain)."""
    ensure_active_user(actor)
    normalized_reason = reason.strip()
    if not normalized_reason:
      raise ConflictError("打回时必须填写原因。")

    task = await self._session.scalar(
      select(Task)
      .options(selectinload(Task.assignee))
      .where(Task.id == task_id)
    )
    if task is None:
      raise NotFoundError("任务不存在。")
    if actor.role not in {UserRole.ADMIN, UserRole.HR} and actor.id != task.assignee_id:
      raise AuthorizationError("当前账号不能打回该制作节点。")

    metadata = dict(task.extra_metadata or {})
    node_id = metadata.get("workflow_node_instance_id")
    if node_id is None:
      raise ConflictError("当前任务未关联图引擎节点。")

    node_instance = await self._session.scalar(
      select(WorkflowNodeInstance)
      .options(selectinload(WorkflowNodeInstance.template_node))
      .where(WorkflowNodeInstance.id == UUID(str(node_id)))
    )
    if node_instance is None:
      raise NotFoundError("节点实例不存在。")

    node_config_raw = node_instance.config if isinstance(node_instance.config, dict) else {}
    if node_instance.template_node is not None and isinstance(node_instance.template_node.config, dict):
      node_config_raw = {**node_instance.template_node.config, **node_config_raw}
    node_config = validate_node_config(node_config_raw)
    acceptance = node_config.acceptance_spec
    if acceptance is None or acceptance.reject_to is None:
      raise ConflictError("当前节点未配置 acceptance_spec.reject_to。")

    resolved_target = target_node_key or acceptance.reject_to.node_key
    instance = await self._session.get(WorkflowGraphInstance, node_instance.instance_id)
    if instance is None:
      raise NotFoundError("图实例不存在。")

    await self._workflow_graph_service.deep_reject_to_upstream(
      node_instance_id=node_instance.id,
      actor_id=actor.id,
      target_node_key=resolved_target,
      reason=normalized_reason,
    )

    target_node = await self._session.scalar(
      select(WorkflowNodeInstance)
      .where(
        WorkflowNodeInstance.instance_id == instance.id,
        WorkflowNodeInstance.node_key == resolved_target,
        WorkflowNodeInstance.engine_state == WorkflowNodeEngineState.ACTIVATED,
      )
      .order_by(WorkflowNodeInstance.iteration.desc())
      .limit(1)
    )
    if target_node is not None:
      await self._orchestration_service.ensure_projection_tasks(
        actor=actor,
        instance=instance,
        node_instances=[target_node],
      )

    await WorkflowRunEventService(self._session).append(
      instance_id=instance.id,
      event_type="production_deep_reject",
      actor_user_id=actor.id,
      payload={
        "from_node_instance_id": str(node_instance.id),
        "from_node_key": node_instance.node_key,
        "target_node_key": resolved_target,
        "reason": normalized_reason,
      },
    )
    await self._session.commit()

    if target_node is None:
      raise ConflictError("深度打回后未找到已激活的目标节点。")

    return RejectProductionStepResponse(
      instance_id=instance.id,
      target_node_key=resolved_target,
      target_node_instance_id=target_node.id,
      iteration=target_node.iteration,
    )
