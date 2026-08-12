"""Privacy-safe, read-only old-vs-projection shadow comparison for Iteration 5-C."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
  TaskStatus,
  WorkflowGraphInstanceStatus,
  WorkflowGraphNodeType,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.models import (
  NodeTimelineEntry,
  ProcessRunSummary,
  ProjectionShadowObservation,
  Task,
  TaskCenterItem,
  TaskComment,
  TaskLog,
  User,
  WorkflowGraphInstance,
  WorkflowHumanTaskLink,
  WorkflowNodeInstance,
  WorkflowRunEvent,
)
from app.services.task_action_policy import derive_execution_mode, standalone_action_owner_id
from app.services.task_service import GraphTaskProjection, TaskService
from app.services.task_user_facing_state import resolve_task_run_label, resolve_task_user_facing_state
from app.services.user_display import user_display_label
from app.services.workflow_template_capability_contract import (
  read_task_capability,
  resolve_task_root_visibility,
)


SHADOW_CONTRACT_VERSION = 1
DEFAULT_LAG_GRACE_SECONDS = 60

_CRITICAL_FIELDS = {
  "subject_type",
  "subject_id",
  "task_id",
  "process_run_id",
  "node_instance_id",
  "department_id",
  "audience_user_ids",
  "audience_department_ids",
  "hidden_for_non_management",
  "is_archived",
  "visibility",
}
_ERROR_FIELDS = {
  "raw_status",
  "engine_state",
  "business_state",
  "user_facing_state",
  "current_action_owner_user_id",
  "requires_action",
  "action_type",
  "status",
  "result",
  "current_node_key",
  "total_node_count",
  "completed_node_count",
  "active_node_count",
  "pending_node_count",
  "blocked_node_count",
  "progress_percent",
  "source_type",
  "source_id",
  "entry_type",
  "event_type",
  "actor_user_id",
  "occurred_at",
  "source_revision",
  "projection_row",
}


@dataclass(frozen=True, slots=True)
class WorkflowProjectionShadowScanResult:
  scan_id: UUID
  sample_mode: str
  compared_count: int
  match_count: int
  difference_count: int
  lagging_count: int
  missing_count: int
  orphan_count: int


def _normalize_datetime(value: datetime) -> datetime:
  if value.tzinfo is None:
    return value.replace(tzinfo=UTC)
  return value.astimezone(UTC)


def _max_datetime(*values: datetime | None) -> datetime:
  normalized = [_normalize_datetime(value) for value in values if value is not None]
  if not normalized:
    raise ValueError("At least one datetime is required")
  return max(normalized)


def _source_revision(*values: datetime | None, floor: int = 0) -> int:
  timestamps = [_normalize_datetime(value).timestamp() for value in values if value is not None]
  if not timestamps:
    return max(0, floor)
  return max(max(0, int(max(timestamps) * 1_000_000)), floor)


def _as_value(value: object) -> str:
  return str(getattr(value, "value", value))


def _read_uuid(payload: dict[str, Any], *keys: str) -> UUID | None:
  for key in keys:
    raw = payload.get(key)
    if raw is None:
      continue
    try:
      return UUID(str(raw))
    except ValueError:
      continue
  return None


def _string_ids(values: set[UUID | None]) -> list[str]:
  return sorted(str(value) for value in values if value is not None)


def _canonicalize(value: Any) -> Any:
  if isinstance(value, datetime):
    return _normalize_datetime(value).isoformat()
  if isinstance(value, UUID):
    return str(value)
  if isinstance(value, Enum):
    return value.value
  if isinstance(value, dict):
    return {str(key): _canonicalize(item) for key, item in sorted(value.items())}
  if isinstance(value, (list, tuple, set)):
    normalized = [_canonicalize(item) for item in value]
    return sorted(normalized) if isinstance(value, set) else normalized
  return value


def _fingerprint(snapshot: dict[str, Any]) -> str:
  encoded = json.dumps(
    _canonicalize(snapshot),
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
  ).encode("utf-8")
  return hashlib.sha256(encoded).hexdigest()


class WorkflowProjectionShadowService:
  """Compare source-derived snapshots with projections and flush safe observations."""

  def __init__(self, session: AsyncSession) -> None:
    self._session = session
    self._task_deriver = TaskService(session)

  async def scan(
    self,
    *,
    sample_mode: str,
    task_limit: int = 100,
    run_limit: int = 100,
    timeline_limit: int = 200,
    lag_grace_seconds: int = DEFAULT_LAG_GRACE_SECONDS,
    scan_id: UUID | None = None,
  ) -> WorkflowProjectionShadowScanResult:
    if sample_mode not in {"recent", "full"}:
      raise ValueError("sample_mode must be 'recent' or 'full'")
    effective_scan_id = scan_id or uuid4()
    observed_at = datetime.now(UTC)
    grace = timedelta(seconds=max(0, lag_grace_seconds))
    observations: list[ProjectionShadowObservation] = []

    tasks = await self._load_tasks(sample_mode=sample_mode, limit=task_limit)
    graph_map = await self._task_deriver._graph_task_projection_map(tasks=tasks)
    for task in tasks:
      if dict(task.extra_metadata or {}).get("workflow_graph_root_task") is True:
        continue
      expected, source_time = await self._expected_task_snapshot(
        task=task,
        graph_projection=graph_map.get(task.id),
      )
      actual_row = await self._session.scalar(
        select(TaskCenterItem).where(
          TaskCenterItem.subject_type == "work_item",
          TaskCenterItem.subject_id == task.id,
        )
      )
      observations.append(
        self._compare(
          scan_id=effective_scan_id,
          sample_mode=sample_mode,
          comparison_name="task_center_item",
          subject_type="work_item",
          subject_id=task.id,
          expected=expected,
          actual=self._task_item_snapshot(actual_row) if actual_row is not None else None,
          expected_revision=int(expected["source_revision"]),
          actual_revision=actual_row.source_revision if actual_row is not None else None,
          source_time=source_time,
          observed_at=observed_at,
          grace=grace,
        )
      )

    runs = await self._load_runs(sample_mode=sample_mode, limit=run_limit)
    for run in runs:
      expected, source_time = self._expected_run_snapshot(run)
      actual_row = await self._session.scalar(
        select(ProcessRunSummary).where(ProcessRunSummary.process_run_id == run.id)
      )
      observations.append(
        self._compare(
          scan_id=effective_scan_id,
          sample_mode=sample_mode,
          comparison_name="process_run_summary",
          subject_type="process_run",
          subject_id=run.id,
          expected=expected,
          actual=self._run_summary_snapshot(actual_row) if actual_row is not None else None,
          expected_revision=int(expected["source_revision"]),
          actual_revision=actual_row.source_revision if actual_row is not None else None,
          source_time=source_time,
          observed_at=observed_at,
          grace=grace,
        )
      )
      root_task = await self._find_root_task(run.id)
      item_expected, item_source_time = self._expected_process_run_item_snapshot(
        instance=run,
        root_task=root_task,
      )
      process_item = await self._session.scalar(
        select(TaskCenterItem).where(
          TaskCenterItem.subject_type == "process_run",
          TaskCenterItem.subject_id == run.id,
        )
      )
      observations.append(
        self._compare(
          scan_id=effective_scan_id,
          sample_mode=sample_mode,
          comparison_name="process_run_item",
          subject_type="process_run",
          subject_id=run.id,
          expected=item_expected,
          actual=(self._task_item_snapshot(process_item) if process_item is not None else None),
          expected_revision=int(item_expected["source_revision"]),
          actual_revision=process_item.source_revision if process_item is not None else None,
          source_time=item_source_time,
          observed_at=observed_at,
          grace=grace,
        )
      )

    timeline_sources = await self._load_timeline_sources(
      sample_mode=sample_mode,
      limit=timeline_limit,
    )
    for source in timeline_sources:
      expected, source_time, source_type, subject_id = await self._expected_timeline_snapshot(
        source
      )
      actual_row = await self._session.scalar(
        select(NodeTimelineEntry).where(
          NodeTimelineEntry.source_type == source_type,
          NodeTimelineEntry.source_id == subject_id,
        )
      )
      observations.append(
        self._compare(
          scan_id=effective_scan_id,
          sample_mode=sample_mode,
          comparison_name="node_timeline_entry",
          subject_type=source_type,
          subject_id=subject_id,
          expected=expected,
          actual=self._timeline_snapshot(actual_row) if actual_row is not None else None,
          expected_revision=int(expected["source_revision"]),
          actual_revision=actual_row.source_revision if actual_row is not None else None,
          source_time=source_time,
          observed_at=observed_at,
          grace=grace,
        )
      )

    if sample_mode == "full":
      observations.extend(
        await self._find_orphans(
          scan_id=effective_scan_id,
          observed_at=observed_at,
          task_ids={
            task.id
            for task in tasks
            if dict(task.extra_metadata or {}).get("workflow_graph_root_task") is not True
          },
          run_ids={run.id for run in runs},
          timeline_ids={
            (self._timeline_source_type(source), source.id) for source in timeline_sources
          },
        )
      )

    self._session.add_all(observations)
    await self._session.flush()
    return WorkflowProjectionShadowScanResult(
      scan_id=effective_scan_id,
      sample_mode=sample_mode,
      compared_count=len(observations),
      match_count=sum(item.outcome == "match" for item in observations),
      difference_count=sum(item.outcome == "difference" for item in observations),
      lagging_count=sum(item.outcome == "lagging" for item in observations),
      missing_count=sum(item.outcome == "missing_projection" for item in observations),
      orphan_count=sum(item.outcome == "orphan_projection" for item in observations),
    )

  async def prune(self, *, retention_days: int = 30) -> int:
    """Delete expired derived evidence only; business sources and projections are untouched."""
    cutoff = datetime.now(UTC) - timedelta(days=max(1, retention_days))
    result = await self._session.execute(
      delete(ProjectionShadowObservation).where(
        ProjectionShadowObservation.created_at < cutoff
      )
    )
    await self._session.flush()
    return max(0, result.rowcount or 0)

  async def _load_tasks(self, *, sample_mode: str, limit: int) -> list[Task]:
    statement = (
      select(Task)
      .options(
        selectinload(Task.creator).selectinload(User.profile),
        selectinload(Task.assignee).selectinload(User.profile),
        selectinload(Task.watchers),
      )
      .order_by(Task.updated_at.desc(), Task.id.desc())
    )
    if sample_mode == "recent":
      statement = statement.limit(max(1, min(limit, 1000)))
    return list(await self._session.scalars(statement))

  async def _load_runs(
    self,
    *,
    sample_mode: str,
    limit: int,
  ) -> list[WorkflowGraphInstance]:
    statement = (
      select(WorkflowGraphInstance)
      .options(
        selectinload(WorkflowGraphInstance.node_instances)
        .selectinload(WorkflowNodeInstance.deliverables),
        selectinload(WorkflowGraphInstance.node_instances)
        .selectinload(WorkflowNodeInstance.assignee)
        .selectinload(User.profile),
        selectinload(WorkflowGraphInstance.run_events),
        selectinload(WorkflowGraphInstance.human_task_links)
        .selectinload(WorkflowHumanTaskLink.task)
        .selectinload(Task.watchers),
      )
      .order_by(WorkflowGraphInstance.updated_at.desc(), WorkflowGraphInstance.id.desc())
    )
    if sample_mode == "recent":
      statement = statement.limit(max(1, min(limit, 1000)))
    return list(await self._session.scalars(statement))

  async def _load_timeline_sources(self, *, sample_mode: str, limit: int) -> list[Any]:
    sources: list[Any] = []
    for model, time_column in (
      (WorkflowRunEvent, WorkflowRunEvent.occurred_at),
      (TaskLog, TaskLog.created_at),
      (TaskComment, TaskComment.updated_at),
    ):
      statement = select(model).order_by(time_column.desc(), model.id.desc())
      if sample_mode == "recent":
        statement = statement.limit(max(1, min(limit, 1000)))
      sources.extend(list(await self._session.scalars(statement)))
    sources.sort(key=lambda item: (self._timeline_source_time(item), item.id), reverse=True)
    if sample_mode == "recent":
      return sources[: max(1, min(limit, 1000))]
    return sources

  async def _expected_task_snapshot(
    self,
    *,
    task: Task,
    graph_projection: GraphTaskProjection | None,
  ) -> tuple[dict[str, Any], datetime]:
    instance, node = await self._task_graph_context(task)
    metadata = dict(task.extra_metadata or {})
    source_time = _max_datetime(
      task.updated_at,
      instance.updated_at if instance is not None else None,
      node.updated_at if node is not None else None,
      *([item.updated_at for item in node.deliverables] if node is not None else []),
      *[watcher.created_at for watcher in task.watchers],
    )
    status = graph_projection.status if graph_projection is not None else task.status
    if graph_projection is not None:
      stage_label = graph_projection.current_stage_label
      handler_id = graph_projection.current_handler_id
      handler_label = graph_projection.current_handler_label
      deliverable_at = graph_projection.latest_deliverable_submitted_at
      rework_count = graph_projection.rework_count
      quality_score = graph_projection.review_quality_score
      completed_at = graph_projection.completed_at
    else:
      stage_label, handler_label = (
        self._task_deriver._manual_graph_context(task=task)
        or self._task_deriver._standalone_context(task=task)
        or (f"任务：{_as_value(task.status)}", user_display_label(task.assignee))
      )
      handler_id = self._task_deriver._manual_graph_current_handler_id(task=task)
      if handler_id is None:
        handler_id = standalone_action_owner_id(task)
      deliverable_at = self._task_deriver._read_datetime_metadata(
        metadata,
        "latest_deliverable_submitted_at",
      )
      rework_count = self._task_deriver._read_int_metadata(metadata, "rework_count")
      quality_score = self._task_deriver._read_int_metadata(
        metadata,
        "latest_review_quality_score",
        default=-1,
      )
      if quality_score < 1:
        quality_score = None
      completed_at = task.completed_at if status == TaskStatus.DONE else None

    capability = read_task_capability(metadata) or {}
    item_kind = (
      "approval"
      if (
        (node is not None and node.node_type == WorkflowGraphNodeType.APPROVAL)
        or capability.get("surface") == "review"
      )
      else ("human_task" if graph_projection is not None else "standalone")
    )
    action_type = self._candidate_action_type(
      status=status,
      graph_projection=graph_projection,
    )
    audience_users = {task.creator_id, task.assignee_id, handler_id}
    audience_users.update(watcher.user_id for watcher in task.watchers)
    audience_users.add(self._task_deriver._read_uuid_metadata(metadata, "reviewer_id"))
    if instance is not None:
      audience_users.add(instance.initiator_user_id)
    if node is not None:
      audience_users.add(node.assignee_user_id)
    snapshot = {
      "subject_type": "work_item",
      "item_kind": item_kind,
      "subject_id": task.id,
      "task_id": task.id,
      "process_run_id": instance.id if instance is not None else None,
      "node_instance_id": node.id if node is not None else None,
      "title": task.title,
      "priority": _as_value(task.priority),
      "raw_status": _as_value(status),
      "engine_state": _as_value(node.engine_state) if node is not None else None,
      "business_state": _as_value(node.business_state) if node is not None else None,
      "user_facing_state": resolve_task_user_facing_state(
        task=task,
        status=status,
        graph_business_state=(graph_projection.business_state if graph_projection else None),
        graph_node_key=graph_projection.node_key if graph_projection else None,
      ),
      "current_stage_label": stage_label,
      "current_handler_label": handler_label,
      "run_label": resolve_task_run_label(
        title=task.title,
        metadata=metadata,
        graph_run_label=instance.run_label if instance is not None else None,
      ),
      "creator_user_id": task.creator_id,
      "assignee_user_id": task.assignee_id,
      "current_action_owner_user_id": handler_id,
      "department_id": task.department_id,
      "execution_mode": derive_execution_mode(task),
      "assignment_mode": task.assignment_mode,
      "requires_action": handler_id is not None and action_type is not None,
      "action_type": action_type,
      "latest_deliverable_submitted_at": deliverable_at,
      "rework_count": max(0, rework_count),
      "review_quality_score": quality_score,
      "source_created_at": task.created_at,
      "source_updated_at": source_time,
      "due_at": task.due_date,
      "completed_at": completed_at,
      "is_archived": metadata.get("admin_archived") is True,
      "hidden_for_non_management": (
        resolve_task_root_visibility(metadata) == "hidden_for_non_management"
      ),
      "audience_user_ids": _string_ids(audience_users),
      "audience_department_ids": _string_ids({task.department_id}),
      "projection_schema_version": SHADOW_CONTRACT_VERSION,
      "source_revision": _source_revision(source_time),
    }
    return _canonicalize(snapshot), source_time

  def _expected_run_snapshot(
    self,
    instance: WorkflowGraphInstance,
  ) -> tuple[dict[str, Any], datetime]:
    nodes = list(instance.node_instances)
    terminal = {
      WorkflowNodeEngineState.COMPLETED,
      WorkflowNodeEngineState.SKIPPED,
      WorkflowNodeEngineState.TERMINATED,
    }
    active = {
      WorkflowNodeEngineState.ACTIVATED,
      WorkflowNodeEngineState.ACKNOWLEDGED,
    }
    blocked = {
      WorkflowNodeEngineState.FAILED,
      WorkflowNodeEngineState.SUSPENDED,
    }
    completed_count = sum(node.engine_state in terminal for node in nodes)
    events = list(instance.run_events)
    linked_tasks = [link.task for link in instance.human_task_links if link.task is not None]
    source_values = [instance.updated_at]
    source_values.extend(node.updated_at for node in nodes)
    source_values.extend(event.occurred_at for event in events)
    source_values.extend(task.updated_at for task in linked_tasks)
    source_values.extend(
      watcher.created_at for task in linked_tasks for watcher in task.watchers
    )
    source_time = _max_datetime(*source_values)
    current_node = self._select_current_node(instance)
    latest_event = max(events, key=lambda item: (item.occurred_at, item.id), default=None)
    audience_users = {instance.initiator_user_id}
    audience_users.update(node.assignee_user_id for node in nodes)
    audience_users.update(event.actor_user_id for event in events)
    audience_departments = {instance.department_id}
    for task in linked_tasks:
      audience_users.update({task.creator_id, task.assignee_id})
      audience_users.update(watcher.user_id for watcher in task.watchers)
      audience_departments.add(task.department_id)
    total = len(nodes)
    snapshot = {
      "process_run_id": instance.id,
      "template_id": instance.template_id,
      "parent_process_run_id": instance.parent_instance_id,
      "source_type": instance.source_type,
      "source_id": instance.source_id,
      "department_id": instance.department_id,
      "initiator_user_id": instance.initiator_user_id,
      "run_label": instance.run_label,
      "status": _as_value(instance.status),
      "result": instance.result,
      "current_node_key": instance.current_node_key,
      "current_stage_label": current_node.title if current_node is not None else None,
      "total_node_count": total,
      "completed_node_count": completed_count,
      "active_node_count": sum(node.engine_state in active for node in nodes),
      "pending_node_count": sum(
        node.engine_state == WorkflowNodeEngineState.PENDING for node in nodes
      ),
      "blocked_node_count": sum(node.engine_state in blocked for node in nodes),
      "progress_percent": int(completed_count * 100 / total) if total else 0,
      "started_at": instance.created_at,
      "source_updated_at": source_time,
      "completed_at": instance.completed_at,
      "latest_event_at": latest_event.occurred_at if latest_event is not None else None,
      "audience_user_ids": _string_ids(audience_users),
      "audience_department_ids": _string_ids(audience_departments),
      "projection_schema_version": SHADOW_CONTRACT_VERSION,
      "source_revision": _source_revision(source_time, floor=instance.context_version),
    }
    return _canonicalize(snapshot), source_time

  def _expected_process_run_item_snapshot(
    self,
    *,
    instance: WorkflowGraphInstance,
    root_task: Task | None,
  ) -> tuple[dict[str, Any], datetime]:
    current_node = self._select_current_node(instance)
    revision_time = _max_datetime(
      instance.updated_at,
      root_task.updated_at if root_task is not None else None,
      current_node.updated_at if current_node is not None else None,
    )
    audience_users = {instance.initiator_user_id}
    audience_users.update(node.assignee_user_id for node in instance.node_instances)
    if root_task is not None:
      audience_users.update({root_task.creator_id, root_task.assignee_id})
      audience_users.update(watcher.user_id for watcher in root_task.watchers)
    raw_status = _as_value(instance.status)
    user_state = {
      WorkflowGraphInstanceStatus.COMPLETED: "completed",
      WorkflowGraphInstanceStatus.FAILED: "blocked",
      WorkflowGraphInstanceStatus.TERMINATED: "blocked",
      WorkflowGraphInstanceStatus.CANCELLED: "completed",
      WorkflowGraphInstanceStatus.PENDING: "pending",
    }.get(instance.status, "in_progress")
    source_updated_at = _max_datetime(
      instance.updated_at,
      root_task.updated_at if root_task is not None else instance.updated_at,
    )
    root_metadata = dict(root_task.extra_metadata or {}) if root_task is not None else {}
    snapshot = {
      "subject_type": "process_run",
      "item_kind": "process_run",
      "subject_id": instance.id,
      "task_id": root_task.id if root_task is not None else None,
      "process_run_id": instance.id,
      "node_instance_id": current_node.id if current_node is not None else None,
      "title": (
        root_task.title
        if root_task is not None
        else (instance.run_label or f"流程运行 {str(instance.id)[:8]}")
      ),
      "priority": _as_value(root_task.priority) if root_task is not None else "medium",
      "raw_status": raw_status,
      "engine_state": raw_status,
      "business_state": (
        _as_value(current_node.business_state) if current_node is not None else None
      ),
      "user_facing_state": user_state,
      "current_stage_label": current_node.title if current_node is not None else None,
      "current_handler_label": (
        user_display_label(current_node.assignee)
        if current_node is not None and current_node.assignee_user_id is not None
        else None
      ),
      "run_label": instance.run_label,
      "creator_user_id": (
        root_task.creator_id if root_task is not None else instance.initiator_user_id
      ),
      "assignee_user_id": root_task.assignee_id if root_task is not None else None,
      "current_action_owner_user_id": None,
      "department_id": (
        root_task.department_id if root_task is not None else instance.department_id
      ),
      "execution_mode": "workflow",
      "assignment_mode": root_task.assignment_mode if root_task is not None else None,
      "requires_action": False,
      "action_type": None,
      "latest_deliverable_submitted_at": None,
      "rework_count": 0,
      "review_quality_score": None,
      "source_created_at": root_task.created_at if root_task is not None else instance.created_at,
      "source_updated_at": source_updated_at,
      "due_at": root_task.due_date if root_task is not None else None,
      "completed_at": instance.completed_at,
      "is_archived": root_metadata.get("admin_archived") is True,
      "hidden_for_non_management": (
        resolve_task_root_visibility(root_metadata) == "hidden_for_non_management"
        if root_task is not None
        else False
      ),
      "audience_user_ids": _string_ids(audience_users),
      "audience_department_ids": _string_ids(
        {
          instance.department_id,
          root_task.department_id if root_task is not None else None,
        }
      ),
      "projection_schema_version": SHADOW_CONTRACT_VERSION,
      "source_revision": _source_revision(
        instance.updated_at,
        root_task.updated_at if root_task is not None else None,
        current_node.updated_at if current_node is not None else None,
        floor=instance.context_version,
      ),
    }
    return _canonicalize(snapshot), revision_time

  async def _expected_timeline_snapshot(
    self,
    source: WorkflowRunEvent | TaskLog | TaskComment,
  ) -> tuple[dict[str, Any], datetime, str, UUID]:
    if isinstance(source, WorkflowRunEvent):
      payload = dict(source.payload or {})
      node_id = _read_uuid(payload, "node_instance_id")
      task_id = _read_uuid(payload, "task_id")
      if task_id is None and node_id is not None:
        task_id = await self._task_id_for_node(node_id)
      snapshot = {
        "process_run_id": source.instance_id,
        "node_instance_id": node_id,
        "task_id": task_id,
        "source_type": "workflow_run_event",
        "source_id": source.id,
        "entry_type": self._run_event_entry_type(source.event_type),
        "event_type": source.event_type,
        "actor_user_id": source.actor_user_id,
        "visibility": "public",
        "occurred_at": source.occurred_at,
        "projection_schema_version": SHADOW_CONTRACT_VERSION,
        "source_revision": _source_revision(
          source.created_at,
          source.occurred_at,
          floor=source.aggregate_version or source.event_version,
        ),
        "last_event_id": source.id,
      }
      return _canonicalize(snapshot), source.occurred_at, "workflow_run_event", source.id

    run_id, node_id = await self._task_parent_ids(source.task_id)
    if isinstance(source, TaskLog):
      detail = dict(source.detail or {})
      event_type = _as_value(source.action_type)
      snapshot = {
        "process_run_id": run_id,
        "node_instance_id": node_id,
        "task_id": source.task_id,
        "source_type": "task_log",
        "source_id": source.id,
        "entry_type": self._task_log_entry_type(event_type, detail),
        "event_type": event_type,
        "actor_user_id": source.operator_id,
        "visibility": "public",
        "occurred_at": source.created_at,
        "projection_schema_version": SHADOW_CONTRACT_VERSION,
        "source_revision": _source_revision(source.created_at),
        "last_event_id": source.id,
      }
      return _canonicalize(snapshot), source.created_at, "task_log", source.id

    snapshot = {
      "process_run_id": run_id,
      "node_instance_id": node_id,
      "task_id": source.task_id,
      "source_type": "task_comment",
      "source_id": source.id,
      "entry_type": "comment",
      "event_type": "comment_added",
      "actor_user_id": source.user_id,
      "visibility": "internal" if source.is_internal else "public",
      "occurred_at": source.created_at,
      "projection_schema_version": SHADOW_CONTRACT_VERSION,
      "source_revision": _source_revision(source.updated_at, source.created_at),
      "last_event_id": source.id,
    }
    return _canonicalize(snapshot), source.updated_at, "task_comment", source.id

  async def _task_graph_context(
    self,
    task: Task,
  ) -> tuple[WorkflowGraphInstance | None, WorkflowNodeInstance | None]:
    link = await self._session.scalar(
      select(WorkflowHumanTaskLink)
      .options(
        selectinload(WorkflowHumanTaskLink.instance),
        selectinload(WorkflowHumanTaskLink.node_instance).selectinload(
          WorkflowNodeInstance.deliverables
        ),
      )
      .where(WorkflowHumanTaskLink.task_id == task.id)
      .order_by(
        (WorkflowHumanTaskLink.lifecycle == "active").desc(),
        WorkflowHumanTaskLink.updated_at.desc(),
      )
    )
    if link is not None:
      return link.instance, link.node_instance
    metadata = dict(task.extra_metadata or {})
    instance_id = _read_uuid(metadata, "workflow_graph_instance_id")
    node_id = _read_uuid(metadata, "workflow_node_instance_id")
    instance = await self._session.get(WorkflowGraphInstance, instance_id) if instance_id else None
    node = None
    if node_id is not None:
      node = await self._session.scalar(
        select(WorkflowNodeInstance)
        .options(selectinload(WorkflowNodeInstance.deliverables))
        .where(WorkflowNodeInstance.id == node_id)
      )
    return instance, node

  async def _task_parent_ids(self, task_id: UUID) -> tuple[UUID | None, UUID | None]:
    link = await self._session.scalar(
      select(WorkflowHumanTaskLink)
      .where(WorkflowHumanTaskLink.task_id == task_id)
      .order_by(
        (WorkflowHumanTaskLink.lifecycle == "active").desc(),
        WorkflowHumanTaskLink.updated_at.desc(),
      )
    )
    if link is not None:
      return link.instance_id, link.node_instance_id
    task = await self._session.get(Task, task_id)
    if task is None:
      return None, None
    metadata = dict(task.extra_metadata or {})
    return (
      _read_uuid(metadata, "workflow_graph_instance_id"),
      _read_uuid(metadata, "workflow_node_instance_id"),
    )

  async def _find_root_task(self, run_id: UUID) -> Task | None:
    task_id = await self._session.scalar(
      select(Task.id).where(
        Task.extra_metadata["workflow_graph_instance_id"].as_string() == str(run_id),
        Task.extra_metadata["workflow_graph_root_task"].as_boolean().is_(True),
      )
    )
    if task_id is None:
      return None
    return await self._session.scalar(
      select(Task)
      .options(
        selectinload(Task.creator).selectinload(User.profile),
        selectinload(Task.assignee).selectinload(User.profile),
        selectinload(Task.watchers),
      )
      .where(Task.id == task_id)
    )

  async def _find_orphans(
    self,
    *,
    scan_id: UUID,
    observed_at: datetime,
    task_ids: set[UUID],
    run_ids: set[UUID],
    timeline_ids: set[tuple[str, UUID]],
  ) -> list[ProjectionShadowObservation]:
    orphans: list[ProjectionShadowObservation] = []
    task_items = list(
      await self._session.scalars(
        select(TaskCenterItem).where(TaskCenterItem.subject_type == "work_item")
      )
    )
    for item in task_items:
      if item.subject_id not in task_ids:
        orphans.append(
          self._orphan_observation(
            scan_id=scan_id,
            comparison_name="task_center_item",
            subject_type="work_item",
            subject_id=item.subject_id,
            actual=self._task_item_snapshot(item),
            actual_revision=item.source_revision,
            observed_at=observed_at,
          )
        )

    summaries = list(await self._session.scalars(select(ProcessRunSummary)))
    for item in summaries:
      if item.process_run_id not in run_ids:
        orphans.append(
          self._orphan_observation(
            scan_id=scan_id,
            comparison_name="process_run_summary",
            subject_type="process_run",
            subject_id=item.process_run_id,
            actual=self._run_summary_snapshot(item),
            actual_revision=item.source_revision,
            observed_at=observed_at,
          )
        )

    timeline_items = list(await self._session.scalars(select(NodeTimelineEntry)))
    for item in timeline_items:
      if (item.source_type, item.source_id) not in timeline_ids:
        orphans.append(
          self._orphan_observation(
            scan_id=scan_id,
            comparison_name="node_timeline_entry",
            subject_type=item.source_type,
            subject_id=item.source_id,
            actual=self._timeline_snapshot(item),
            actual_revision=item.source_revision,
            observed_at=observed_at,
          )
        )
    return orphans

  @staticmethod
  def _orphan_observation(
    *,
    scan_id: UUID,
    comparison_name: str,
    subject_type: str,
    subject_id: UUID,
    actual: dict[str, Any],
    actual_revision: int,
    observed_at: datetime,
  ) -> ProjectionShadowObservation:
    return ProjectionShadowObservation(
      scan_id=scan_id,
      comparison_name=comparison_name,
      subject_type=subject_type,
      subject_id=subject_id,
      sample_mode="full",
      outcome="orphan_projection",
      severity="error",
      mismatch_fields=["source_row"],
      expected_fingerprint=_fingerprint({"source_row": "absent"}),
      actual_fingerprint=_fingerprint(actual),
      expected_source_revision=None,
      actual_source_revision=actual_revision,
      lag_ms=None,
      details={
        "contract_version": SHADOW_CONTRACT_VERSION,
        "compared_field_count": 0,
      },
      observed_at=observed_at,
    )

  async def _task_id_for_node(self, node_id: UUID) -> UUID | None:
    return await self._session.scalar(
      select(WorkflowHumanTaskLink.task_id)
      .where(WorkflowHumanTaskLink.node_instance_id == node_id)
      .order_by(
        (WorkflowHumanTaskLink.lifecycle == "active").desc(),
        WorkflowHumanTaskLink.updated_at.desc(),
      )
    )

  def _compare(
    self,
    *,
    scan_id: UUID,
    sample_mode: str,
    comparison_name: str,
    subject_type: str,
    subject_id: UUID,
    expected: dict[str, Any],
    actual: dict[str, Any] | None,
    expected_revision: int,
    actual_revision: int | None,
    source_time: datetime,
    observed_at: datetime,
    grace: timedelta,
  ) -> ProjectionShadowObservation:
    age = max(timedelta(), observed_at - _normalize_datetime(source_time))
    if actual is None:
      mismatch_fields = ["projection_row"]
      outcome = "lagging" if age <= grace else "missing_projection"
      severity = "info" if outcome == "lagging" else "error"
      lag_ms = max(0, int(age.total_seconds() * 1000))
    else:
      mismatch_fields = sorted(
        key for key in expected if _canonicalize(expected[key]) != _canonicalize(actual.get(key))
      )
      if mismatch_fields and actual_revision is not None and actual_revision < expected_revision and age <= grace:
        outcome = "lagging"
        severity = "info"
      elif mismatch_fields:
        outcome = "difference"
        severity = self._severity(mismatch_fields)
      else:
        outcome = "match"
        severity = "info"
      lag_ms = (
        max(0, (expected_revision - actual_revision) // 1000)
        if actual_revision is not None
        else None
      )
    return ProjectionShadowObservation(
      scan_id=scan_id,
      comparison_name=comparison_name,
      subject_type=subject_type,
      subject_id=subject_id,
      sample_mode=sample_mode,
      outcome=outcome,
      severity=severity,
      mismatch_fields=mismatch_fields,
      expected_fingerprint=_fingerprint(expected),
      actual_fingerprint=_fingerprint(actual) if actual is not None else None,
      expected_source_revision=expected_revision,
      actual_source_revision=actual_revision,
      lag_ms=lag_ms,
      details={
        "contract_version": SHADOW_CONTRACT_VERSION,
        "compared_field_count": len(expected),
      },
      observed_at=observed_at,
    )

  @staticmethod
  def _severity(mismatch_fields: list[str]) -> str:
    fields = set(mismatch_fields)
    if fields & _CRITICAL_FIELDS:
      return "critical"
    if fields & _ERROR_FIELDS:
      return "error"
    return "warning"

  @staticmethod
  def _task_item_snapshot(item: TaskCenterItem) -> dict[str, Any]:
    fields = (
      "subject_type", "item_kind", "subject_id", "task_id", "process_run_id",
      "node_instance_id", "title", "priority", "raw_status", "engine_state",
      "business_state", "user_facing_state", "current_stage_label",
      "current_handler_label", "run_label", "creator_user_id", "assignee_user_id",
      "current_action_owner_user_id", "department_id", "execution_mode",
      "assignment_mode", "requires_action", "action_type",
      "latest_deliverable_submitted_at", "rework_count", "review_quality_score",
      "source_created_at", "source_updated_at", "due_at", "completed_at", "is_archived",
      "hidden_for_non_management", "audience_user_ids", "audience_department_ids",
      "projection_schema_version", "source_revision",
    )
    return _canonicalize({field: getattr(item, field) for field in fields})

  @staticmethod
  def _run_summary_snapshot(item: ProcessRunSummary) -> dict[str, Any]:
    fields = (
      "process_run_id", "template_id", "parent_process_run_id", "source_type", "source_id",
      "department_id", "initiator_user_id", "run_label", "status", "result",
      "current_node_key", "current_stage_label", "total_node_count",
      "completed_node_count", "active_node_count", "pending_node_count",
      "blocked_node_count", "progress_percent", "started_at", "source_updated_at",
      "completed_at", "latest_event_at", "audience_user_ids", "audience_department_ids",
      "projection_schema_version", "source_revision",
    )
    return _canonicalize({field: getattr(item, field) for field in fields})

  @staticmethod
  def _timeline_snapshot(item: NodeTimelineEntry) -> dict[str, Any]:
    fields = (
      "process_run_id", "node_instance_id", "task_id", "source_type", "source_id",
      "entry_type", "event_type", "actor_user_id", "visibility", "occurred_at",
      "projection_schema_version", "source_revision", "last_event_id",
    )
    return _canonicalize({field: getattr(item, field) for field in fields})

  @staticmethod
  def _timeline_source_time(source: Any) -> datetime:
    if isinstance(source, WorkflowRunEvent):
      return _normalize_datetime(source.occurred_at)
    if isinstance(source, TaskComment):
      return _normalize_datetime(source.updated_at)
    return _normalize_datetime(source.created_at)

  @staticmethod
  def _timeline_source_type(source: Any) -> str:
    if isinstance(source, WorkflowRunEvent):
      return "workflow_run_event"
    if isinstance(source, TaskComment):
      return "task_comment"
    return "task_log"

  @staticmethod
  def _select_current_node(instance: WorkflowGraphInstance) -> WorkflowNodeInstance | None:
    active = [
      node
      for node in instance.node_instances
      if node.engine_state
      not in {
        WorkflowNodeEngineState.COMPLETED,
        WorkflowNodeEngineState.SKIPPED,
        WorkflowNodeEngineState.TERMINATED,
      }
    ]
    if instance.current_node_key:
      keyed = [node for node in active if node.node_key == instance.current_node_key]
      if keyed:
        return max(keyed, key=lambda item: (item.iteration, item.created_at, item.id))
    if active:
      return max(active, key=lambda item: (item.iteration, item.created_at, item.id))
    if instance.node_instances:
      return max(
        instance.node_instances,
        key=lambda item: (item.iteration, item.created_at, item.id),
      )
    return None

  @staticmethod
  def _candidate_action_type(
    *,
    status: TaskStatus,
    graph_projection: GraphTaskProjection | None,
  ) -> str | None:
    if status in {TaskStatus.DONE, TaskStatus.BLOCKED}:
      return None
    if graph_projection is not None:
      if graph_projection.business_state == WorkflowNodeBusinessState.ASSIGNED:
        return "accept_assignment"
      if graph_projection.business_state == WorkflowNodeBusinessState.PENDING_REVIEW:
        return "review_deliverable"
      if graph_projection.business_state in {
        WorkflowNodeBusinessState.DOING,
        WorkflowNodeBusinessState.RETURNED_FOR_REWORK,
      }:
        return "submit_deliverable"
    return {
      TaskStatus.TODO: "start_work",
      TaskStatus.DOING: "submit_deliverable",
      TaskStatus.REVIEW: "review_deliverable",
    }.get(status)

  @staticmethod
  def _run_event_entry_type(event_type: str) -> str:
    if "approval" in event_type:
      return "approval"
    if any(token in event_type for token in ("rework", "reject", "return")):
      return "rework"
    if any(token in event_type for token in ("takeover", "taken_over", "delegate")):
      return "takeover"
    if any(token in event_type for token in ("deliverable", "submission")):
      return "deliverable"
    if event_type.startswith(("run_", "admin_", "context_")):
      return "system"
    return "node_event"

  @staticmethod
  def _task_log_entry_type(event_type: str, detail: dict[str, Any]) -> str:
    if any(token in event_type for token in ("attachment", "deliverable")):
      return "deliverable"
    detail_action = str(detail.get("action") or detail.get("handshake_action") or "")
    if any(token in detail_action for token in ("rework", "return", "reject")):
      return "rework"
    if any(token in detail_action for token in ("takeover", "delegate")):
      return "takeover"
    return "work_item_activity"
