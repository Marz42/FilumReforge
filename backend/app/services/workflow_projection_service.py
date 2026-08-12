"""Flush-only Iteration 5 projector for rebuildable workflow query models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
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
  ProjectionCheckpoint,
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


PROJECTION_NAME = "workflow_query_v1"
PROJECTION_SCHEMA_VERSION = 1
STREAM_WORKFLOW_RUN_EVENTS = "workflow_run_events"
STREAM_TASK_LOGS = "task_logs"
STREAM_TASK_COMMENTS = "task_comments"
PROJECTION_STREAMS = (
  STREAM_WORKFLOW_RUN_EVENTS,
  STREAM_TASK_LOGS,
  STREAM_TASK_COMMENTS,
)


@dataclass(frozen=True, slots=True)
class ProjectionConsumeResult:
  stream_name: str
  processed_count: int
  cursor_occurred_at: datetime | None
  cursor_source_id: UUID | None


def _as_value(value: object) -> str:
  raw = getattr(value, "value", value)
  return str(raw)


def _normalize_datetime(value: datetime) -> datetime:
  if value.tzinfo is None:
    return value.replace(tzinfo=UTC)
  return value.astimezone(UTC)


def _source_revision(*values: datetime | None, floor: int = 0) -> int:
  timestamps = [_normalize_datetime(value).timestamp() for value in values if value is not None]
  if not timestamps:
    return max(0, floor)
  return max(max(0, int(max(timestamps) * 1_000_000)), floor)


def _max_datetime(*values: datetime | None) -> datetime:
  normalized = [_normalize_datetime(value) for value in values if value is not None]
  if not normalized:
    raise ValueError("At least one datetime is required")
  return max(normalized)


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


def _summary_text(value: object, *, limit: int = 300) -> str | None:
  if not isinstance(value, str):
    return None
  normalized = " ".join(value.strip().split())
  if not normalized:
    return None
  return normalized if len(normalized) <= limit else f"{normalized[: limit - 1]}…"


class WorkflowProjectionService:
  """Projection owner. Methods flush but never commit business or projection transactions."""

  def __init__(self, session: AsyncSession) -> None:
    self._session = session
    self._task_deriver = TaskService(session)

  async def consume_stream(
    self,
    *,
    stream_name: str,
    batch_size: int = 100,
  ) -> ProjectionConsumeResult:
    if stream_name not in PROJECTION_STREAMS:
      raise ValueError(f"Unsupported projection stream: {stream_name}")
    normalized_batch_size = max(1, min(batch_size, 1000))
    checkpoint = await self._lock_checkpoint(stream_name=stream_name)
    checkpoint.status = "running"
    checkpoint.attempt_count += 1
    await self._session.flush()

    source_model, time_column = self._stream_source(stream_name)
    statement = select(source_model)
    if checkpoint.cursor_occurred_at is not None and checkpoint.cursor_source_id is not None:
      statement = statement.where(
        or_(
          time_column > checkpoint.cursor_occurred_at,
          and_(
            time_column == checkpoint.cursor_occurred_at,
            source_model.id > checkpoint.cursor_source_id,
          ),
        )
      )
    sources = list(
      await self._session.scalars(
        statement.order_by(time_column.asc(), source_model.id.asc()).limit(
          normalized_batch_size
        )
      )
    )

    affected_task_ids: set[UUID] = set()
    affected_run_ids: set[UUID] = set()
    task_last_event_ids: dict[UUID, UUID] = {}
    run_last_event_ids: dict[UUID, UUID] = {}
    for source in sources:
      if stream_name == STREAM_WORKFLOW_RUN_EVENTS:
        entry = await self.project_run_event(source, refresh_parents=False)
        occurred_at = source.occurred_at
      elif stream_name == STREAM_TASK_LOGS:
        entry = await self.project_task_log(source, refresh_parents=False)
        occurred_at = source.created_at
      else:
        entry = await self.project_task_comment(source, refresh_parents=False)
        occurred_at = source.created_at
      if entry.task_id is not None:
        affected_task_ids.add(entry.task_id)
        task_last_event_ids[entry.task_id] = source.id
      if entry.process_run_id is not None:
        affected_run_ids.add(entry.process_run_id)
        if stream_name == STREAM_WORKFLOW_RUN_EVENTS:
          run_last_event_ids[entry.process_run_id] = source.id
      checkpoint.cursor_occurred_at = occurred_at
      checkpoint.cursor_source_id = source.id

    for task_id in sorted(affected_task_ids, key=str):
      await self.project_task(
        task_id=task_id,
        last_event_id=task_last_event_ids.get(task_id),
      )
    for run_id in sorted(affected_run_ids, key=str):
      await self.project_run(
        run_id=run_id,
        last_event_id=run_last_event_ids.get(run_id),
      )

    now = datetime.now(UTC)
    checkpoint.status = "idle"
    checkpoint.processed_count += len(sources)
    checkpoint.last_success_at = now
    checkpoint.last_error = None
    await self._session.flush()
    return ProjectionConsumeResult(
      stream_name=stream_name,
      processed_count=len(sources),
      cursor_occurred_at=checkpoint.cursor_occurred_at,
      cursor_source_id=checkpoint.cursor_source_id,
    )

  async def record_stream_failure(self, *, stream_name: str, error: Exception | str) -> None:
    if stream_name not in PROJECTION_STREAMS:
      raise ValueError(f"Unsupported projection stream: {stream_name}")
    checkpoint = await self._lock_checkpoint(stream_name=stream_name)
    checkpoint.status = "failed"
    checkpoint.attempt_count += 1
    checkpoint.last_error = _summary_text(str(error), limit=2000) or type(error).__name__
    await self._session.flush()

  async def set_checkpoint_cursor(
    self,
    *,
    stream_name: str,
    cursor: tuple[datetime, UUID] | None,
    processed_count: int | None = None,
  ) -> ProjectionCheckpoint:
    checkpoint = await self._lock_checkpoint(stream_name=stream_name)
    if cursor is None:
      checkpoint.cursor_occurred_at = None
      checkpoint.cursor_source_id = None
    else:
      checkpoint.cursor_occurred_at, checkpoint.cursor_source_id = cursor
    if processed_count is not None:
      checkpoint.processed_count = max(0, processed_count)
    checkpoint.status = "idle"
    checkpoint.last_success_at = datetime.now(UTC)
    checkpoint.last_error = None
    await self._session.flush()
    return checkpoint

  async def project_task(
    self,
    *,
    task_id: UUID,
    last_event_id: UUID | None = None,
    force: bool = False,
  ) -> TaskCenterItem | None:
    task = await self._load_task(task_id)
    if task is None:
      existing = await self._session.scalar(
        select(TaskCenterItem).where(TaskCenterItem.task_id == task_id)
      )
      if existing is not None:
        await self._session.delete(existing)
        await self._session.flush()
      return None

    graph_projection = (await self._task_deriver._graph_task_projection_map(tasks=[task])).get(
      task.id
    )
    instance, node = await self._task_graph_context(task=task)
    metadata = dict(task.extra_metadata or {})
    if metadata.get("workflow_graph_root_task") is True and instance is not None:
      return await self._project_process_run_item(
        instance=instance,
        root_task=task,
        last_event_id=last_event_id,
        force=force,
      )

    source_updated_at = _max_datetime(
      task.updated_at,
      instance.updated_at if instance is not None else None,
      node.updated_at if node is not None else None,
      *(
        [deliverable.updated_at for deliverable in node.deliverables]
        if node is not None
        else []
      ),
      *[watcher.created_at for watcher in task.watchers],
    )
    revision = _source_revision(source_updated_at)
    existing = await self._session.scalar(
      select(TaskCenterItem).where(
        TaskCenterItem.subject_type == "work_item",
        TaskCenterItem.subject_id == task.id,
      )
    )
    if existing is not None and existing.source_revision > revision and not force:
      return existing

    status = graph_projection.status if graph_projection is not None else task.status
    if graph_projection is not None:
      stage_label = graph_projection.current_stage_label
      handler_id = graph_projection.current_handler_id
      handler_label = graph_projection.current_handler_label
      latest_deliverable_at = graph_projection.latest_deliverable_submitted_at
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
      latest_deliverable_at = self._task_deriver._read_datetime_metadata(
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

    action_type = self._candidate_action_type(status=status, graph_projection=graph_projection)
    capability = read_task_capability(metadata) or {}
    item_kind = (
      "approval"
      if (
        (node is not None and node.node_type == WorkflowGraphNodeType.APPROVAL)
        or capability.get("surface") == "review"
      )
      else ("human_task" if graph_projection is not None else "standalone")
    )
    run_label = resolve_task_run_label(
      title=task.title,
      metadata=metadata,
      graph_run_label=instance.run_label if instance is not None else None,
    )
    user_state = resolve_task_user_facing_state(
      task=task,
      status=status,
      graph_business_state=(
        graph_projection.business_state if graph_projection is not None else None
      ),
      graph_node_key=graph_projection.node_key if graph_projection is not None else None,
    )
    audience_users = {task.creator_id, task.assignee_id, handler_id}
    audience_users.update(watcher.user_id for watcher in task.watchers)
    reviewer_id = self._task_deriver._read_uuid_metadata(metadata, "reviewer_id")
    audience_users.add(reviewer_id)
    if instance is not None:
      audience_users.add(instance.initiator_user_id)
    if node is not None:
      audience_users.add(node.assignee_user_id)

    values: dict[str, Any] = {
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
      "user_facing_state": user_state,
      "current_stage_label": stage_label,
      "current_handler_label": handler_label,
      "run_label": run_label,
      "creator_user_id": task.creator_id,
      "assignee_user_id": task.assignee_id,
      "current_action_owner_user_id": handler_id,
      "department_id": task.department_id,
      "execution_mode": derive_execution_mode(task),
      "assignment_mode": task.assignment_mode,
      "requires_action": handler_id is not None and action_type is not None,
      "action_type": action_type,
      "latest_deliverable_submitted_at": latest_deliverable_at,
      "rework_count": max(0, rework_count),
      "review_quality_score": quality_score,
      "source_created_at": task.created_at,
      "source_updated_at": source_updated_at,
      "due_at": task.due_date,
      "completed_at": completed_at,
      "is_archived": metadata.get("admin_archived") is True,
      "hidden_for_non_management": (
        resolve_task_root_visibility(metadata) == "hidden_for_non_management"
      ),
      "audience_user_ids": _string_ids(audience_users),
      "audience_department_ids": _string_ids({task.department_id}),
      "projection_schema_version": PROJECTION_SCHEMA_VERSION,
      "source_revision": revision,
      "projected_at": datetime.now(UTC),
    }
    item = existing or TaskCenterItem(**values)
    if existing is None:
      self._session.add(item)
    else:
      self._assign(item, values)
    if last_event_id is not None:
      item.last_event_id = last_event_id
    await self._session.flush()
    return item

  async def project_run(
    self,
    *,
    run_id: UUID,
    last_event_id: UUID | None = None,
    force: bool = False,
  ) -> ProcessRunSummary | None:
    instance = await self._load_run(run_id)
    if instance is None:
      summary = await self._session.scalar(
        select(ProcessRunSummary).where(ProcessRunSummary.process_run_id == run_id)
      )
      if summary is not None:
        await self._session.delete(summary)
      item = await self._session.scalar(
        select(TaskCenterItem).where(
          TaskCenterItem.subject_type == "process_run",
          TaskCenterItem.subject_id == run_id,
        )
      )
      if item is not None:
        await self._session.delete(item)
      await self._session.flush()
      return None

    nodes = list(instance.node_instances)
    terminal_states = {
      WorkflowNodeEngineState.COMPLETED,
      WorkflowNodeEngineState.SKIPPED,
      WorkflowNodeEngineState.TERMINATED,
    }
    active_states = {
      WorkflowNodeEngineState.ACTIVATED,
      WorkflowNodeEngineState.ACKNOWLEDGED,
    }
    blocked_states = {
      WorkflowNodeEngineState.FAILED,
      WorkflowNodeEngineState.SUSPENDED,
    }
    completed_count = sum(node.engine_state in terminal_states for node in nodes)
    active_count = sum(node.engine_state in active_states for node in nodes)
    pending_count = sum(node.engine_state == WorkflowNodeEngineState.PENDING for node in nodes)
    blocked_count = sum(node.engine_state in blocked_states for node in nodes)
    current_node = self._select_current_node(instance=instance)
    events = list(instance.run_events)
    latest_event = max(events, key=lambda event: (event.occurred_at, event.id), default=None)
    linked_tasks = [link.task for link in instance.human_task_links if link.task is not None]
    source_updated_values = [instance.updated_at]
    source_updated_values.extend(node.updated_at for node in nodes)
    source_updated_values.extend(event.occurred_at for event in events)
    source_updated_values.extend(task.updated_at for task in linked_tasks)
    source_updated_values.extend(
      watcher.created_at for task in linked_tasks for watcher in task.watchers
    )
    source_updated_at = _max_datetime(*source_updated_values)
    revision = _source_revision(source_updated_at, floor=instance.context_version)
    existing = await self._session.scalar(
      select(ProcessRunSummary).where(ProcessRunSummary.process_run_id == instance.id)
    )
    if existing is not None and existing.source_revision > revision and not force:
      await self._project_process_run_item(
        instance=instance,
        root_task=await self._find_root_task(instance.id),
        last_event_id=last_event_id,
        force=force,
      )
      return existing

    audience_users = {instance.initiator_user_id}
    audience_users.update(node.assignee_user_id for node in nodes)
    audience_users.update(event.actor_user_id for event in events)
    audience_departments = {instance.department_id}
    for task in linked_tasks:
      audience_users.update({task.creator_id, task.assignee_id})
      audience_users.update(watcher.user_id for watcher in task.watchers)
      audience_departments.add(task.department_id)
    total_count = len(nodes)
    progress = round(completed_count * 100 / total_count) if total_count else 0
    values: dict[str, Any] = {
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
      "total_node_count": total_count,
      "completed_node_count": completed_count,
      "active_node_count": active_count,
      "pending_node_count": pending_count,
      "blocked_node_count": blocked_count,
      "progress_percent": progress,
      "started_at": instance.created_at,
      "source_updated_at": source_updated_at,
      "completed_at": instance.completed_at,
      "latest_event_at": latest_event.occurred_at if latest_event is not None else None,
      "audience_user_ids": _string_ids(audience_users),
      "audience_department_ids": _string_ids(audience_departments),
      "projection_schema_version": PROJECTION_SCHEMA_VERSION,
      "source_revision": revision,
      "projected_at": datetime.now(UTC),
    }
    summary = existing or ProcessRunSummary(**values)
    if existing is None:
      self._session.add(summary)
    else:
      self._assign(summary, values)
    effective_last_event_id = last_event_id or (latest_event.id if latest_event is not None else None)
    if effective_last_event_id is not None:
      summary.last_event_id = effective_last_event_id
    await self._project_process_run_item(
      instance=instance,
      root_task=await self._find_root_task(instance.id),
      last_event_id=effective_last_event_id,
      force=force,
    )
    await self._session.flush()
    return summary

  async def project_run_event(
    self,
    event: WorkflowRunEvent,
    *,
    force: bool = False,
    refresh_parents: bool = True,
  ) -> NodeTimelineEntry:
    payload = dict(event.payload or {})
    node_id = _read_uuid(payload, "node_instance_id")
    task_id = _read_uuid(payload, "task_id")
    if task_id is None and node_id is not None:
      task_id = await self._task_id_for_node(node_id)
    values = {
      "process_run_id": event.instance_id,
      "node_instance_id": node_id,
      "task_id": task_id,
      "source_type": "workflow_run_event",
      "source_id": event.id,
      "entry_type": self._run_event_entry_type(event.event_type),
      "event_type": event.event_type,
      "actor_user_id": event.actor_user_id,
      "visibility": "public",
      "title": self._event_title(event.event_type),
      "summary": _summary_text(payload.get("reason")),
      "payload": self._safe_run_event_payload(payload),
      "occurred_at": event.occurred_at,
      "projection_schema_version": PROJECTION_SCHEMA_VERSION,
      "source_revision": _source_revision(
        event.created_at,
        event.occurred_at,
        floor=event.aggregate_version or event.event_version,
      ),
      "last_event_id": event.id,
      "projected_at": datetime.now(UTC),
    }
    entry = await self._upsert_timeline(values=values, force=force)
    if refresh_parents:
      await self.project_run(run_id=event.instance_id, last_event_id=event.id, force=force)
      if task_id is not None:
        await self.project_task(task_id=task_id, last_event_id=event.id, force=force)
    return entry

  async def project_task_log(
    self,
    log: TaskLog,
    *,
    force: bool = False,
    refresh_parents: bool = True,
  ) -> NodeTimelineEntry:
    run_id, node_id = await self._task_parent_ids(log.task_id)
    detail = dict(log.detail or {})
    event_type = _as_value(log.action_type)
    values = {
      "process_run_id": run_id,
      "node_instance_id": node_id,
      "task_id": log.task_id,
      "source_type": "task_log",
      "source_id": log.id,
      "entry_type": self._task_log_entry_type(event_type, detail),
      "event_type": event_type,
      "actor_user_id": log.operator_id,
      "visibility": "public",
      "title": self._event_title(event_type),
      "summary": _summary_text(detail.get("reason") or detail.get("message")),
      "payload": {
        "from_status": _as_value(log.from_status) if log.from_status is not None else None,
        "to_status": _as_value(log.to_status) if log.to_status is not None else None,
      },
      "occurred_at": log.created_at,
      "projection_schema_version": PROJECTION_SCHEMA_VERSION,
      "source_revision": _source_revision(log.created_at),
      "last_event_id": log.id,
      "projected_at": datetime.now(UTC),
    }
    entry = await self._upsert_timeline(values=values, force=force)
    if refresh_parents:
      await self.project_task(task_id=log.task_id, last_event_id=log.id, force=force)
      if run_id is not None:
        await self.project_run(run_id=run_id, last_event_id=log.id, force=force)
    return entry

  async def project_task_comment(
    self,
    comment: TaskComment,
    *,
    force: bool = False,
    refresh_parents: bool = True,
  ) -> NodeTimelineEntry:
    run_id, node_id = await self._task_parent_ids(comment.task_id)
    values = {
      "process_run_id": run_id,
      "node_instance_id": node_id,
      "task_id": comment.task_id,
      "source_type": "task_comment",
      "source_id": comment.id,
      "entry_type": "comment",
      "event_type": "comment_added",
      "actor_user_id": comment.user_id,
      "visibility": "internal" if comment.is_internal else "public",
      "title": "新增评论",
      "summary": _summary_text(comment.content, limit=160),
      "payload": {},
      "occurred_at": comment.created_at,
      "projection_schema_version": PROJECTION_SCHEMA_VERSION,
      "source_revision": _source_revision(comment.updated_at, comment.created_at),
      "last_event_id": comment.id,
      "projected_at": datetime.now(UTC),
    }
    entry = await self._upsert_timeline(values=values, force=force)
    if refresh_parents:
      await self.project_task(task_id=comment.task_id, last_event_id=comment.id, force=force)
      if run_id is not None:
        await self.project_run(run_id=run_id, last_event_id=comment.id, force=force)
    return entry

  async def _load_task(self, task_id: UUID) -> Task | None:
    return await self._session.scalar(
      select(Task)
      .options(
        selectinload(Task.creator).selectinload(User.profile),
        selectinload(Task.assignee).selectinload(User.profile),
        selectinload(Task.watchers),
      )
      .where(Task.id == task_id)
    )

  async def _load_run(self, run_id: UUID) -> WorkflowGraphInstance | None:
    return await self._session.scalar(
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
      .where(WorkflowGraphInstance.id == run_id)
    )

  async def _task_graph_context(
    self,
    *,
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
    instance = await self._load_run(instance_id) if instance_id else None
    node = None
    if node_id is not None:
      node = await self._session.scalar(
        select(WorkflowNodeInstance)
        .options(selectinload(WorkflowNodeInstance.deliverables))
        .where(WorkflowNodeInstance.id == node_id)
      )
    if instance is None:
      instance = await self._session.scalar(
        select(WorkflowGraphInstance).where(
          WorkflowGraphInstance.source_type == "task",
          WorkflowGraphInstance.source_id == task.id,
        )
      )
    return instance, node

  async def _project_process_run_item(
    self,
    *,
    instance: WorkflowGraphInstance,
    root_task: Task | None,
    last_event_id: UUID | None,
    force: bool,
  ) -> TaskCenterItem:
    current_node = self._select_current_node(instance=instance)
    revision = _source_revision(
      instance.updated_at,
      root_task.updated_at if root_task is not None else None,
      current_node.updated_at if current_node is not None else None,
      floor=instance.context_version,
    )
    existing = await self._session.scalar(
      select(TaskCenterItem).where(
        TaskCenterItem.subject_type == "process_run",
        TaskCenterItem.subject_id == instance.id,
      )
    )
    if existing is not None and existing.source_revision > revision and not force:
      return existing
    if root_task is not None:
      conflicting = await self._session.scalar(
        select(TaskCenterItem).where(
          TaskCenterItem.task_id == root_task.id,
          TaskCenterItem.id != existing.id if existing is not None else TaskCenterItem.id.is_not(None),
        )
      )
      if conflicting is not None:
        await self._session.delete(conflicting)
        await self._session.flush()

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
    values: dict[str, Any] = {
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
      "creator_user_id": root_task.creator_id if root_task is not None else instance.initiator_user_id,
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
      "source_updated_at": _max_datetime(
        instance.updated_at,
        root_task.updated_at if root_task is not None else instance.updated_at,
      ),
      "due_at": root_task.due_date if root_task is not None else None,
      "completed_at": instance.completed_at,
      "is_archived": (
        bool((root_task.extra_metadata or {}).get("admin_archived"))
        if root_task is not None
        else False
      ),
      "hidden_for_non_management": (
        resolve_task_root_visibility(dict(root_task.extra_metadata or {}))
        == "hidden_for_non_management"
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
      "projection_schema_version": PROJECTION_SCHEMA_VERSION,
      "source_revision": revision,
      "projected_at": datetime.now(UTC),
    }
    item = existing or TaskCenterItem(**values)
    if existing is None:
      self._session.add(item)
    else:
      self._assign(item, values)
    if last_event_id is not None:
      item.last_event_id = last_event_id
    await self._session.flush()
    return item

  async def _find_root_task(self, run_id: UUID) -> Task | None:
    candidate_ids = list(
      await self._session.scalars(
        select(Task.id).where(
          Task.extra_metadata["workflow_graph_instance_id"].as_string() == str(run_id),
          Task.extra_metadata["workflow_graph_root_task"].as_boolean().is_(True),
        )
      )
    )
    if not candidate_ids:
      return None
    return await self._load_task(candidate_ids[0])

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

  async def _task_id_for_node(self, node_id: UUID) -> UUID | None:
    return await self._session.scalar(
      select(WorkflowHumanTaskLink.task_id)
      .where(WorkflowHumanTaskLink.node_instance_id == node_id)
      .order_by(
        (WorkflowHumanTaskLink.lifecycle == "active").desc(),
        WorkflowHumanTaskLink.updated_at.desc(),
      )
    )

  async def _upsert_timeline(
    self,
    *,
    values: dict[str, Any],
    force: bool,
  ) -> NodeTimelineEntry:
    existing = await self._session.scalar(
      select(NodeTimelineEntry).where(
        NodeTimelineEntry.source_type == values["source_type"],
        NodeTimelineEntry.source_id == values["source_id"],
      )
    )
    if (
      existing is not None
      and existing.source_revision > int(values["source_revision"])
      and not force
    ):
      return existing
    entry = existing or NodeTimelineEntry(**values)
    if existing is None:
      self._session.add(entry)
    else:
      self._assign(entry, values)
    await self._session.flush()
    return entry

  async def _lock_checkpoint(self, *, stream_name: str) -> ProjectionCheckpoint:
    checkpoint = await self._session.scalar(
      select(ProjectionCheckpoint)
      .where(
        ProjectionCheckpoint.projection_name == PROJECTION_NAME,
        ProjectionCheckpoint.stream_name == stream_name,
      )
      .with_for_update()
    )
    if checkpoint is None:
      checkpoint = ProjectionCheckpoint(
        projection_name=PROJECTION_NAME,
        stream_name=stream_name,
        status="idle",
      )
      self._session.add(checkpoint)
      await self._session.flush()
    return checkpoint

  @staticmethod
  def _stream_source(stream_name: str) -> tuple[type, Any]:
    if stream_name == STREAM_WORKFLOW_RUN_EVENTS:
      return WorkflowRunEvent, WorkflowRunEvent.occurred_at
    if stream_name == STREAM_TASK_LOGS:
      return TaskLog, TaskLog.created_at
    if stream_name == STREAM_TASK_COMMENTS:
      return TaskComment, TaskComment.created_at
    raise ValueError(f"Unsupported projection stream: {stream_name}")

  @staticmethod
  def _assign(target: object, values: dict[str, Any]) -> None:
    for key, value in values.items():
      setattr(target, key, value)

  @staticmethod
  def _select_current_node(
    *,
    instance: WorkflowGraphInstance,
  ) -> WorkflowNodeInstance | None:
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
        return max(keyed, key=lambda node: (node.iteration, node.created_at, node.id))
    if active:
      return max(active, key=lambda node: (node.iteration, node.created_at, node.id))
    if instance.node_instances:
      return max(
        instance.node_instances,
        key=lambda node: (node.iteration, node.created_at, node.id),
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
      business_state = graph_projection.business_state
      if business_state == WorkflowNodeBusinessState.ASSIGNED:
        return "accept_assignment"
      if business_state == WorkflowNodeBusinessState.PENDING_REVIEW:
        return "review_deliverable"
      if business_state in {
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

  @staticmethod
  def _event_title(event_type: str) -> str:
    labels = {
      "created": "创建任务",
      "assigned": "分配任务",
      "status_changed": "更新任务状态",
      "commented": "新增评论",
      "attachment_added": "添加附件",
      "due_date_changed": "调整截止时间",
      "closed": "关闭任务",
      "node_completed": "节点已完成",
      "node_retried": "节点已重试",
      "node_taken_over": "节点已接管",
      "approval_requested": "发起验收",
      "approval_result_consumed": "验收结果已处理",
      "approval_blocked": "验收动作被阻止",
    }
    return labels.get(event_type, event_type.replace("_", " ").strip().title())

  @staticmethod
  def _safe_run_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    safe_keys = {
      "node_instance_id",
      "node_key",
      "instance_key",
      "task_id",
      "approval_instance_id",
      "approval_step_run_id",
      "action",
      "from_assignee_user_id",
      "to_assignee_user_id",
      "completion_mode",
    }
    result: dict[str, Any] = {}
    for key in safe_keys:
      value = payload.get(key)
      if isinstance(value, (str, int, float, bool)) or value is None:
        result[key] = value
    return result
