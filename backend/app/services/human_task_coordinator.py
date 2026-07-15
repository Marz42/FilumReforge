from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
  TaskSourceType,
  TaskStatus,
  WorkflowGraphInstanceStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.models import (
  Task,
  WorkflowGraphInstance,
  WorkflowHumanTaskLink,
  WorkflowNodeInstance,
)


logger = logging.getLogger(__name__)
_resolution_counts: Counter[str] = Counter()


@dataclass(slots=True, frozen=True)
class HumanTaskResolution:
  instance: WorkflowGraphInstance | None
  node_instance: WorkflowNodeInstance | None
  link: WorkflowHumanTaskLink | None
  source: str


@dataclass(slots=True, frozen=True)
class HumanTaskBackfillIssue:
  task_id: UUID
  code: str
  detail: str


@dataclass(slots=True)
class HumanTaskBackfillReport:
  scanned: int = 0
  eligible: int = 0
  created: int = 0
  existing: int = 0
  issues: list[HumanTaskBackfillIssue] = field(default_factory=list)


class HumanTaskCoordinator:
  """Application-layer boundary between Work Items and runtime node execution.

  I3-A limits this coordinator to durable relationship management. Runtime
  activation and capability-result commands move here in the next cutover.
  """

  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  @staticmethod
  def resolution_metrics() -> dict[str, int]:
    return dict(_resolution_counts)

  async def ensure_link(
    self,
    *,
    task_id: UUID,
    node_instance_id: UUID,
    link_role: str = "primary",
    source: str = "runtime",
    link_metadata: dict[str, object] | None = None,
  ) -> WorkflowHumanTaskLink:
    task = await self._session.get(Task, task_id)
    if task is None:
      raise NotFoundError("HumanTask Link 对应的 Work Item 不存在。")
    node_instance = await self._session.get(WorkflowNodeInstance, node_instance_id)
    if node_instance is None:
      raise NotFoundError("HumanTask Link 对应的 NodeInstance 不存在。")

    existing = await self._session.scalar(
      select(WorkflowHumanTaskLink).where(WorkflowHumanTaskLink.task_id == task_id)
    )
    if existing is not None:
      if existing.node_instance_id != node_instance_id:
        raise ConflictError("同一个 Work Item 不能关联多个 NodeInstance。")
      return existing

    if link_role == "primary":
      active_primary = await self._session.scalar(
        select(WorkflowHumanTaskLink).where(
          WorkflowHumanTaskLink.node_instance_id == node_instance_id,
          WorkflowHumanTaskLink.link_role == "primary",
          WorkflowHumanTaskLink.lifecycle == "active",
        )
      )
      if active_primary is not None:
        raise ConflictError("当前 NodeInstance 已有关联的 active primary Work Item。")

    link = WorkflowHumanTaskLink(
      instance_id=node_instance.instance_id,
      node_instance_id=node_instance.id,
      task_id=task.id,
      link_role=link_role,
      lifecycle="active",
      source=source,
      link_metadata=dict(link_metadata or {}),
    )
    try:
      async with self._session.begin_nested():
        self._session.add(link)
        await self._session.flush()
    except IntegrityError:
      existing = await self._session.scalar(
        select(WorkflowHumanTaskLink).where(WorkflowHumanTaskLink.task_id == task_id)
      )
      if existing is not None:
        if existing.node_instance_id != node_instance_id:
          raise ConflictError("同一个 Work Item 不能关联多个 NodeInstance。")
        return existing
      if link_role == "primary":
        active_primary = await self._session.scalar(
          select(WorkflowHumanTaskLink).where(
            WorkflowHumanTaskLink.node_instance_id == node_instance_id,
            WorkflowHumanTaskLink.link_role == "primary",
            WorkflowHumanTaskLink.lifecycle == "active",
          )
        )
        if active_primary is not None:
          raise ConflictError("当前 NodeInstance 已有关联的 active primary Work Item。")
      raise
    return link

  async def resolve_for_task(
    self,
    *,
    task: Task,
    allow_json_fallback: bool = True,
  ) -> HumanTaskResolution:
    link = await self._session.scalar(
      select(WorkflowHumanTaskLink)
      .options(
        selectinload(WorkflowHumanTaskLink.instance),
        selectinload(WorkflowHumanTaskLink.node_instance),
      )
      .where(WorkflowHumanTaskLink.task_id == task.id)
    )
    if link is not None:
      _resolution_counts["link"] += 1
      return HumanTaskResolution(
        instance=link.instance,
        node_instance=link.node_instance,
        link=link,
        source="link",
      )

    if not allow_json_fallback:
      _resolution_counts["none"] += 1
      return HumanTaskResolution(None, None, None, "none")

    metadata = task.extra_metadata if isinstance(task.extra_metadata, dict) else {}
    try:
      instance_id = UUID(str(metadata["workflow_graph_instance_id"]))
      node_instance_id = UUID(str(metadata["workflow_node_instance_id"]))
    except (KeyError, TypeError, ValueError):
      _resolution_counts["none"] += 1
      return HumanTaskResolution(None, None, None, "none")

    node_instance = await self._session.get(WorkflowNodeInstance, node_instance_id)
    if node_instance is None or node_instance.instance_id != instance_id:
      _resolution_counts["none"] += 1
      return HumanTaskResolution(None, None, None, "none")
    instance = await self._session.get(WorkflowGraphInstance, instance_id)
    if instance is None:
      _resolution_counts["none"] += 1
      return HumanTaskResolution(None, None, None, "none")

    logger.warning(
      "workflow_human_task_link_fallback task_id=%s instance_id=%s node_instance_id=%s",
      task.id,
      instance.id,
      node_instance.id,
    )
    _resolution_counts["json_fallback"] += 1
    return HumanTaskResolution(instance, node_instance, None, "json_fallback")

  async def bind_projection_task(
    self,
    *,
    task: Task,
    node_instance: WorkflowNodeInstance,
    source: str = "runtime",
    mark_doing: bool = False,
  ) -> WorkflowHumanTaskLink:
    node_instance.config = {
      **dict(node_instance.config or {}),
      "task_id": str(task.id),
    }
    if mark_doing and node_instance.business_state == WorkflowNodeBusinessState.ASSIGNED:
      node_instance.business_state = WorkflowNodeBusinessState.DOING
    return await self.ensure_link(
      task_id=task.id,
      node_instance_id=node_instance.id,
      source=source,
      link_metadata={"compatibility_json_written": True},
    )

  async def apply_review_projection_state(
    self,
    *,
    task: Task,
    node_instance: WorkflowNodeInstance,
    root_task: Task | None,
    reference_time: datetime,
  ) -> None:
    """Apply one coordinated Work Item / Node review transition."""
    task.status = TaskStatus.REVIEW
    task.completed_at = None
    task.updated_at = reference_time
    node_instance.engine_state = WorkflowNodeEngineState.ACKNOWLEDGED
    node_instance.business_state = WorkflowNodeBusinessState.PENDING_REVIEW
    node_instance.acknowledged_at = node_instance.acknowledged_at or reference_time
    node_instance.completed_at = None
    if root_task is not None:
      root_task.status = TaskStatus.REVIEW
      root_task.completed_at = None
      root_task.updated_at = reference_time

  async def apply_aggregate_confirmation(
    self,
    *,
    node_instance: WorkflowNodeInstance,
    task: Task | None,
    reference_time: datetime,
  ) -> None:
    """Resolve an aggregate capability across Runtime and its optional Work Item."""
    if node_instance.engine_state != WorkflowNodeEngineState.COMPLETED:
      node_instance.engine_state = WorkflowNodeEngineState.COMPLETED
      node_instance.business_state = WorkflowNodeBusinessState.DONE
      node_instance.completed_at = reference_time
    if task is None:
      return
    task.status = TaskStatus.DONE
    task.completed_at = reference_time
    task.updated_at = reference_time
    metadata = dict(task.extra_metadata or {})
    metadata["aggregate_confirmed_at"] = reference_time.isoformat()
    task.extra_metadata = metadata

  async def apply_handshake_acceptance(
    self,
    *,
    task: Task,
    node_instance: WorkflowNodeInstance,
    actor_id: UUID,
    reference_time: datetime,
  ) -> None:
    """Accept a HumanTask handshake without exposing Node writes to TaskService."""
    node_instance.business_state = WorkflowNodeBusinessState.ACCEPTED
    node_instance.acknowledged_at = reference_time
    metadata = dict(task.extra_metadata or {})
    metadata.update(
      {
        "workflow_handshake_state": "accepted",
        "latest_handshake_action": "accepted",
        "latest_handshake_actor_user_id": str(actor_id),
        "latest_handshake_at": reference_time.isoformat(),
      }
    )
    task.extra_metadata = metadata
    if task.status == TaskStatus.TODO:
      task.status = TaskStatus.DOING
      task.started_at = reference_time
    task.updated_at = reference_time

  async def sync_runtime_for_task_status(
    self,
    *,
    task: Task,
    target_status: TaskStatus,
    reference_time: datetime,
    force_business_state: WorkflowNodeBusinessState | None = None,
  ) -> None:
    resolution = await self.resolve_for_task(task=task)
    instance = resolution.instance
    node_instance = resolution.node_instance
    if instance is None or node_instance is None:
      return

    instance.status = WorkflowGraphInstanceStatus.ACTIVE
    instance.completed_at = None
    instance.current_node_key = node_instance.node_key
    if target_status == TaskStatus.DOING:
      node_instance.engine_state = WorkflowNodeEngineState.ACKNOWLEDGED
      node_instance.acknowledged_at = node_instance.acknowledged_at or reference_time
      node_instance.completed_at = None
      node_instance.business_state = force_business_state or WorkflowNodeBusinessState.DOING
      await self._set_link_lifecycle(resolution.link, lifecycle="active")
      return
    if target_status == TaskStatus.REVIEW:
      node_instance.engine_state = WorkflowNodeEngineState.ACKNOWLEDGED
      node_instance.acknowledged_at = node_instance.acknowledged_at or reference_time
      node_instance.completed_at = None
      node_instance.business_state = force_business_state or WorkflowNodeBusinessState.PENDING_REVIEW
      await self._set_link_lifecycle(resolution.link, lifecycle="active")
      return
    if target_status == TaskStatus.DONE:
      node_instance.engine_state = WorkflowNodeEngineState.COMPLETED
      node_instance.acknowledged_at = node_instance.acknowledged_at or reference_time
      node_instance.completed_at = reference_time
      node_instance.business_state = force_business_state or WorkflowNodeBusinessState.DONE
      if task.source_type == TaskSourceType.MANUAL:
        instance.status = WorkflowGraphInstanceStatus.COMPLETED
        instance.result = instance.result or "success"
        instance.completed_at = reference_time
        instance.current_node_key = None
      await self._set_link_lifecycle(
        resolution.link,
        lifecycle="completed",
        reference_time=reference_time,
      )

  async def sync_runtime_for_handshake_state(
    self,
    *,
    task: Task,
    business_state: WorkflowNodeBusinessState,
    reference_time: datetime,
    assignee_id: UUID | None = None,
    reset_acknowledged_at: bool = False,
  ) -> None:
    resolution = await self.resolve_for_task(task=task)
    instance = resolution.instance
    node_instance = resolution.node_instance
    if instance is None or node_instance is None:
      return
    if instance.status != WorkflowGraphInstanceStatus.ACTIVE:
      raise ConflictError("当前工作流图实例已结束，不能继续执行握手动作。")
    if node_instance.engine_state in {
      WorkflowNodeEngineState.COMPLETED,
      WorkflowNodeEngineState.TERMINATED,
    }:
      raise ConflictError("当前图节点已失效，不能继续执行握手动作。")

    instance.completed_at = None
    instance.current_node_key = node_instance.node_key
    node_instance.completed_at = None
    if assignee_id is not None:
      node_instance.assignee_user_id = assignee_id
    if business_state == WorkflowNodeBusinessState.ASSIGNED:
      node_instance.engine_state = WorkflowNodeEngineState.ACTIVATED
      node_instance.business_state = WorkflowNodeBusinessState.ASSIGNED
      if reset_acknowledged_at:
        node_instance.acknowledged_at = None
    else:
      node_instance.engine_state = WorkflowNodeEngineState.ACKNOWLEDGED
      node_instance.business_state = business_state
      node_instance.acknowledged_at = reference_time
    await self._set_link_lifecycle(resolution.link, lifecycle="active")

  async def sync_work_item_after_takeover(
    self,
    *,
    graph_instance: WorkflowGraphInstance,
    node_instance: WorkflowNodeInstance,
    new_assignee_id: UUID,
    reason: str,
    actor_id: UUID,
  ) -> None:
    link = await self._session.scalar(
      select(WorkflowHumanTaskLink).where(
        WorkflowHumanTaskLink.node_instance_id == node_instance.id,
        WorkflowHumanTaskLink.link_role == "primary",
      )
    )
    task = await self._session.get(Task, link.task_id) if link is not None else None
    if task is None and graph_instance.source_id is not None:
      task = await self._session.get(Task, graph_instance.source_id)
    if task is None or task.source_type != TaskSourceType.MANUAL:
      return
    metadata = dict(task.extra_metadata or {})
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

  async def sync_link_lifecycles_for_instance(
    self,
    *,
    instance_id: UUID,
    cancelled: bool = False,
  ) -> None:
    links = list(
      await self._session.scalars(
        select(WorkflowHumanTaskLink)
        .options(selectinload(WorkflowHumanTaskLink.node_instance))
        .where(WorkflowHumanTaskLink.instance_id == instance_id)
      )
    )
    now = datetime.now(UTC)
    for link in links:
      node = link.node_instance
      if node is None:
        continue
      if cancelled:
        await self._set_link_lifecycle(link, lifecycle="cancelled", reference_time=now)
      elif node.engine_state == WorkflowNodeEngineState.COMPLETED:
        await self._set_link_lifecycle(link, lifecycle="completed", reference_time=node.completed_at or now)
      elif node.engine_state in {
        WorkflowNodeEngineState.TERMINATED,
        WorkflowNodeEngineState.SKIPPED,
        WorkflowNodeEngineState.FAILED,
      }:
        await self._set_link_lifecycle(link, lifecycle="invalidated", reference_time=now)

  @staticmethod
  async def _set_link_lifecycle(
    link: WorkflowHumanTaskLink | None,
    *,
    lifecycle: str,
    reference_time: datetime | None = None,
  ) -> None:
    if link is None:
      return
    link.lifecycle = lifecycle
    if lifecycle == "completed":
      link.completed_at = reference_time or datetime.now(UTC)
      link.invalidated_at = None
    elif lifecycle in {"cancelled", "invalidated"}:
      link.completed_at = None
      link.invalidated_at = reference_time or datetime.now(UTC)
    else:
      link.completed_at = None
      link.invalidated_at = None

  async def backfill_existing_links(self, *, dry_run: bool = True) -> HumanTaskBackfillReport:
    """Cross-check all legacy JSON anchors and optionally materialize safe links."""
    report = HumanTaskBackfillReport()
    pending_links: list[tuple[UUID, UUID]] = []
    tasks = list(await self._session.scalars(select(Task).order_by(Task.created_at.asc())))
    for task in tasks:
      metadata = task.extra_metadata if isinstance(task.extra_metadata, dict) else {}
      if not metadata.get("workflow_node_instance_id") and not metadata.get("workflow_graph_instance_id"):
        continue
      report.scanned += 1

      try:
        node_id = UUID(str(metadata["workflow_node_instance_id"]))
        instance_id = UUID(str(metadata["workflow_graph_instance_id"]))
      except (KeyError, TypeError, ValueError):
        report.issues.append(
          HumanTaskBackfillIssue(task.id, "invalid_json_anchor", "Task metadata 中的 Run/Node UUID 无效。")
        )
        continue

      node_instance = await self._session.get(WorkflowNodeInstance, node_id)
      if node_instance is None:
        report.issues.append(
          HumanTaskBackfillIssue(task.id, "node_missing", "Task metadata 指向的 NodeInstance 不存在。")
        )
        continue
      if node_instance.instance_id != instance_id:
        report.issues.append(
          HumanTaskBackfillIssue(task.id, "instance_mismatch", "Task metadata 的 Run 与 Node 所属 Run 不一致。")
        )
        continue

      node_config = node_instance.config if isinstance(node_instance.config, dict) else {}
      if str(node_config.get("task_id") or "") != str(task.id):
        report.issues.append(
          HumanTaskBackfillIssue(task.id, "node_task_mismatch", "Node config.task_id 未与 Task 互相指向。")
        )
        continue

      instance = await self._session.get(WorkflowGraphInstance, instance_id)
      if instance is None:
        report.issues.append(
          HumanTaskBackfillIssue(task.id, "instance_missing", "Task metadata 指向的 Run 不存在。")
        )
        continue
      if task.source_type == TaskSourceType.MANUAL and instance.source_id != task.id:
        report.issues.append(
          HumanTaskBackfillIssue(task.id, "source_mismatch", "手动图任务未与 Run source_id 互相指向。")
        )
        continue

      report.eligible += 1
      existing = await self._session.scalar(
        select(WorkflowHumanTaskLink).where(WorkflowHumanTaskLink.task_id == task.id)
      )
      if existing is not None:
        if existing.node_instance_id != node_instance.id:
          report.issues.append(
            HumanTaskBackfillIssue(task.id, "link_mismatch", "既有 Link 与 JSON 锚点指向不同 Node。")
          )
        else:
          report.existing += 1
        continue

      pending_links.append((task.id, node_instance.id))

    if not dry_run and not report.issues:
      for task_id, node_instance_id in pending_links:
        await self.ensure_link(
          task_id=task_id,
          node_instance_id=node_instance_id,
          source="backfill",
          link_metadata={"backfilled_from": "legacy_json_anchors"},
        )
        report.created += 1

    return report
