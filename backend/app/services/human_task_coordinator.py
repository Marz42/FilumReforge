from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
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
from app.services.work_item_write_service import WorkItemWriteService
from app.services.workflow_operational_incident_service import WorkflowOperationalIncidentService
from app.services.workflow_runtime_write_service import WorkflowRuntimeWriteService


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
  checkpoint_task_id: UUID | None = None


class HumanTaskCoordinator:
  """Application-layer boundary between Work Items and runtime node execution.

  I3-A limits this coordinator to durable relationship management. Runtime
  activation and capability-result commands move here in the next cutover.
  """

  def __init__(self, session: AsyncSession) -> None:
    self._session = session
    self._work_items = WorkItemWriteService(session)
    self._runtime = WorkflowRuntimeWriteService(session)
    self._incidents = WorkflowOperationalIncidentService(session)

  @staticmethod
  def resolution_metrics() -> dict[str, int]:
    return dict(_resolution_counts)

  def create_work_item(self, **values: object) -> Task:
    return self._work_items.create(**values)

  def create_runtime_instance(self, **values: object) -> WorkflowGraphInstance:
    return self._runtime.create_instance(**values)

  def create_runtime_node(self, **values: object) -> WorkflowNodeInstance:
    return self._runtime.create_node(**values)

  async def coordinate_mutations(
    self,
    *,
    task: Task | None = None,
    node_instance: WorkflowNodeInstance | None = None,
    graph_instance: WorkflowGraphInstance | None = None,
    task_changes: dict[str, object] | None = None,
    task_metadata_patch: dict[str, object] | None = None,
    node_changes: dict[str, object] | None = None,
    node_config_patch: dict[str, object] | None = None,
    instance_changes: dict[str, object] | None = None,
  ) -> None:
    """Coordinate owner-only mutations inside the caller's transaction."""
    if task is not None:
      if task_changes:
        self._work_items.update(task, **task_changes)
      if task_metadata_patch:
        self._work_items.patch_metadata(task, task_metadata_patch)
    if node_instance is not None:
      if node_changes:
        self._runtime.update_node(node_instance, **node_changes)
      if node_config_patch:
        self._runtime.patch_node_config(node_instance, node_config_patch)
    if graph_instance is not None and instance_changes:
      self._runtime.update_instance(graph_instance, **instance_changes)

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
      iteration=node_instance.iteration,
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

    if node_instance.iteration > 1:
      previous_link = await self._session.scalar(
        select(WorkflowHumanTaskLink)
        .join(
          WorkflowNodeInstance,
          WorkflowHumanTaskLink.node_instance_id == WorkflowNodeInstance.id,
        )
        .where(
          WorkflowHumanTaskLink.instance_id == node_instance.instance_id,
          WorkflowHumanTaskLink.link_role == link_role,
          WorkflowHumanTaskLink.id != link.id,
          WorkflowNodeInstance.node_key == node_instance.node_key,
          WorkflowNodeInstance.instance_key == node_instance.instance_key,
          WorkflowNodeInstance.iteration < node_instance.iteration,
        )
        .order_by(WorkflowNodeInstance.iteration.desc())
        .limit(1)
      )
      if previous_link is not None and previous_link.lifecycle != "superseded":
        await self.supersede_link(
          previous_link=previous_link,
          replacement_link=link,
        )
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
      metadata = task.extra_metadata if isinstance(task.extra_metadata, dict) else {}
      json_node_id = str(metadata.get("workflow_node_instance_id") or "")
      json_instance_id = str(metadata.get("workflow_graph_instance_id") or "")
      if (
        (json_node_id and json_node_id != str(link.node_instance_id))
        or (json_instance_id and json_instance_id != str(link.instance_id))
      ):
        await self._incidents.record(
          category="link_mismatch",
          identity={"task_id": str(task.id)},
          severity="error",
          instance_id=link.instance_id,
          node_instance_id=link.node_instance_id,
          task_id=task.id,
          engine_version=link.instance.engine_version if link.instance is not None else None,
          details={
            "link_instance_id": str(link.instance_id),
            "link_node_instance_id": str(link.node_instance_id),
            "json_instance_id": json_instance_id or None,
            "json_node_instance_id": json_node_id or None,
          },
        )
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
    await self._incidents.record(
      category="link_fallback",
      identity={"task_id": str(task.id)},
      severity="error",
      instance_id=instance.id,
      node_instance_id=node_instance.id,
      task_id=task.id,
      engine_version=instance.engine_version,
      details={"source": "legacy_json_anchors"},
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
    self._runtime.patch_node_config(node_instance, {"task_id": str(task.id)})
    if mark_doing and node_instance.business_state == WorkflowNodeBusinessState.ASSIGNED:
      self._runtime.update_node(
        node_instance,
        business_state=WorkflowNodeBusinessState.DOING,
      )
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
    self._work_items.update(
      task,
      status=TaskStatus.REVIEW,
      completed_at=None,
      updated_at=reference_time,
    )
    self._runtime.update_node(
      node_instance,
      engine_state=WorkflowNodeEngineState.ACKNOWLEDGED,
      business_state=WorkflowNodeBusinessState.PENDING_REVIEW,
      acknowledged_at=node_instance.acknowledged_at or reference_time,
      completed_at=None,
    )
    if root_task is not None:
      self._work_items.update(
        root_task,
        status=TaskStatus.REVIEW,
        completed_at=None,
        updated_at=reference_time,
      )

  async def apply_aggregate_confirmation(
    self,
    *,
    node_instance: WorkflowNodeInstance,
    task: Task | None,
    reference_time: datetime,
  ) -> None:
    """Resolve an aggregate capability across Runtime and its optional Work Item."""
    if node_instance.engine_state != WorkflowNodeEngineState.COMPLETED:
      self._runtime.update_node(
        node_instance,
        engine_state=WorkflowNodeEngineState.COMPLETED,
        business_state=WorkflowNodeBusinessState.DONE,
        completed_at=reference_time,
      )
    if task is None:
      return
    self._work_items.update(
      task,
      status=TaskStatus.DONE,
      completed_at=reference_time,
      updated_at=reference_time,
    )
    self._work_items.patch_metadata(
      task,
      {"aggregate_confirmed_at": reference_time.isoformat()},
    )

  async def apply_handshake_acceptance(
    self,
    *,
    task: Task,
    node_instance: WorkflowNodeInstance,
    actor_id: UUID,
    reference_time: datetime,
  ) -> None:
    """Accept a HumanTask handshake without exposing Node writes to TaskService."""
    self._runtime.update_node(
      node_instance,
      business_state=WorkflowNodeBusinessState.ACCEPTED,
      acknowledged_at=reference_time,
    )
    self._work_items.patch_metadata(
      task,
      {
        "workflow_handshake_state": "accepted",
        "latest_handshake_action": "accepted",
        "latest_handshake_actor_user_id": str(actor_id),
        "latest_handshake_at": reference_time.isoformat(),
      },
    )
    if task.status == TaskStatus.TODO:
      self._work_items.update(task, status=TaskStatus.DOING, started_at=reference_time)
    self._work_items.update(task, updated_at=reference_time)

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

    self._runtime.update_instance(
      instance,
      status=WorkflowGraphInstanceStatus.ACTIVE,
      completed_at=None,
      current_node_key=node_instance.node_key,
    )
    if target_status == TaskStatus.DOING:
      self._runtime.update_node(
        node_instance,
        engine_state=WorkflowNodeEngineState.ACKNOWLEDGED,
        acknowledged_at=node_instance.acknowledged_at or reference_time,
        completed_at=None,
        business_state=force_business_state or WorkflowNodeBusinessState.DOING,
      )
      await self._set_link_lifecycle(resolution.link, lifecycle="active")
      return
    if target_status == TaskStatus.REVIEW:
      self._runtime.update_node(
        node_instance,
        engine_state=WorkflowNodeEngineState.ACKNOWLEDGED,
        acknowledged_at=node_instance.acknowledged_at or reference_time,
        completed_at=None,
        business_state=force_business_state or WorkflowNodeBusinessState.PENDING_REVIEW,
      )
      await self._set_link_lifecycle(resolution.link, lifecycle="active")
      return
    if target_status == TaskStatus.DONE:
      self._runtime.update_node(
        node_instance,
        engine_state=WorkflowNodeEngineState.COMPLETED,
        acknowledged_at=node_instance.acknowledged_at or reference_time,
        completed_at=reference_time,
        business_state=force_business_state or WorkflowNodeBusinessState.DONE,
      )
      if task.source_type == TaskSourceType.MANUAL:
        self._runtime.update_instance(
          instance,
          status=WorkflowGraphInstanceStatus.COMPLETED,
          result=instance.result or "success",
          completed_at=reference_time,
          current_node_key=None,
        )
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

    self._runtime.update_instance(
      instance,
      completed_at=None,
      current_node_key=node_instance.node_key,
    )
    self._runtime.update_node(node_instance, completed_at=None)
    if assignee_id is not None:
      self._runtime.update_node(node_instance, assignee_user_id=assignee_id)
    if business_state == WorkflowNodeBusinessState.ASSIGNED:
      self._runtime.update_node(
        node_instance,
        engine_state=WorkflowNodeEngineState.ACTIVATED,
        business_state=WorkflowNodeBusinessState.ASSIGNED,
      )
      if reset_acknowledged_at:
        self._runtime.update_node(node_instance, acknowledged_at=None)
    else:
      self._runtime.update_node(
        node_instance,
        engine_state=WorkflowNodeEngineState.ACKNOWLEDGED,
        business_state=business_state,
        acknowledged_at=reference_time,
      )
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
    self._work_items.update(task, assignee_id=new_assignee_id)
    self._work_items.patch_metadata(
      task,
      {
        "workflow_handshake_state": "assigned",
        "latest_handshake_action": "takeover",
        "latest_handshake_actor_user_id": str(actor_id),
        "latest_takeover_reason": reason,
      },
    )
    self._work_items.update(task, updated_at=datetime.now(UTC))

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

  async def _set_link_lifecycle(
    self,
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
      link.superseded_at = None
      link.superseded_by_link_id = None
    elif lifecycle in {"cancelled", "invalidated"}:
      link.completed_at = None
      link.invalidated_at = reference_time or datetime.now(UTC)
      link.superseded_at = None
      link.superseded_by_link_id = None
    else:
      link.completed_at = None
      link.invalidated_at = None
      if lifecycle != "superseded":
        link.superseded_at = None
        link.superseded_by_link_id = None

  async def supersede_link(
    self,
    *,
    previous_link: WorkflowHumanTaskLink,
    replacement_link: WorkflowHumanTaskLink,
    reference_time: datetime | None = None,
  ) -> None:
    if previous_link.id == replacement_link.id:
      raise ConflictError("HumanTask Link 不能 supersede 自己。")
    previous_link.lifecycle = "superseded"
    previous_link.completed_at = None
    previous_link.invalidated_at = None
    previous_link.superseded_at = reference_time or datetime.now(UTC)
    previous_link.superseded_by_link_id = replacement_link.id

  async def backfill_existing_links(
    self,
    *,
    dry_run: bool = True,
    after_task_id: UUID | None = None,
    limit: int | None = None,
  ) -> HumanTaskBackfillReport:
    """Cross-check all legacy JSON anchors and optionally materialize safe links."""
    report = HumanTaskBackfillReport()
    pending_links: list[tuple[UUID, UUID]] = []
    query = select(Task).order_by(Task.created_at.asc(), Task.id.asc())
    if after_task_id is not None:
      checkpoint = await self._session.get(Task, after_task_id)
      if checkpoint is None:
        raise NotFoundError("HumanTask Link 回填 checkpoint Task 不存在。")
      query = query.where(
        or_(
          Task.created_at > checkpoint.created_at,
          and_(Task.created_at == checkpoint.created_at, Task.id > checkpoint.id),
        )
      )
    if limit is not None:
      if limit <= 0 or limit > 10_000:
        raise ConflictError("HumanTask Link 回填 batch size 必须在 1–10000 之间。")
      query = query.limit(limit)
    tasks = list(await self._session.scalars(query))
    for task in tasks:
      report.checkpoint_task_id = task.id
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
          if not dry_run:
            await self._incidents.record(
              category="link_mismatch",
              identity={"task_id": str(task.id)},
              severity="error",
              instance_id=existing.instance_id,
              node_instance_id=existing.node_instance_id,
              task_id=task.id,
              details={"json_node_instance_id": str(node_instance.id)},
            )
        else:
          report.existing += 1
        continue

      pending_links.append((task.id, node_instance.id))

    if not dry_run:
      for issue in report.issues:
        await self._incidents.record(
          category="link_backfill_issue",
          identity={"task_id": str(issue.task_id), "code": issue.code},
          severity="error",
          task_id=issue.task_id,
          details={"code": issue.code, "detail": issue.detail},
        )

    if not dry_run:
      for task_id, node_instance_id in pending_links:
        await self.ensure_link(
          task_id=task_id,
          node_instance_id=node_instance_id,
          source="backfill",
          link_metadata={"backfilled_from": "legacy_json_anchors"},
        )
        report.created += 1

    return report
