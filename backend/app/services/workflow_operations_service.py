from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
  WorkflowGraphInstanceStatus,
  WorkflowNodeEngineState,
  WorkflowOutboxEventStatus,
)
from app.core.exceptions import AppValidationError, ConflictError, NotFoundError
from app.models import (
  ProjectionCheckpoint,
  ProjectionShadowObservation,
  TaskComment,
  TaskLog,
  WorkflowCommandReceipt,
  WorkflowGraphInstance,
  WorkflowNodeActivationDependency,
  WorkflowNodeInstance,
  WorkflowOperationalIncident,
  WorkflowOutboxEvent,
  WorkflowRunEvent,
)
from app.services.workflow_run_event_service import WorkflowRunEventService


def _utc(value: datetime | None) -> datetime | None:
  if value is None:
    return None
  if value.tzinfo is None:
    return value.replace(tzinfo=UTC)
  return value.astimezone(UTC)


def _seconds_since(value: datetime | None, *, now: datetime) -> int | None:
  normalized = _utc(value)
  if normalized is None:
    return None
  return max(0, int((now - normalized).total_seconds()))


def _uuid(value: UUID | None) -> str | None:
  return str(value) if value is not None else None


class WorkflowOperationsService:
  """Admin-facing, privacy-safe workflow operations read and action boundary."""

  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def build_dashboard(
    self,
    *,
    stalled_minutes: int = 30,
    limit: int = 50,
  ) -> dict[str, Any]:
    normalized_minutes = max(5, min(stalled_minutes, 1440))
    normalized_limit = max(1, min(limit, 100))
    now = datetime.now(UTC)

    run_counts = {
      status.value: int(count)
      for status, count in (
        await self._session.execute(
          select(WorkflowGraphInstance.status, func.count())
          .group_by(WorkflowGraphInstance.status)
        )
      ).all()
    }
    for status in WorkflowGraphInstanceStatus:
      run_counts.setdefault(status.value, 0)

    active_node_run_ids = set(
      await self._session.scalars(
        select(WorkflowNodeInstance.instance_id).where(
          WorkflowNodeInstance.engine_state.in_(
            [WorkflowNodeEngineState.ACTIVATED, WorkflowNodeEngineState.ACKNOWLEDGED]
          )
        )
      )
    )
    active_runs = list(
      await self._session.scalars(
        select(WorkflowGraphInstance).where(
          WorkflowGraphInstance.status == WorkflowGraphInstanceStatus.ACTIVE
        )
      )
    )
    stale_before = now - timedelta(minutes=normalized_minutes)
    stalled_runs = [
      run
      for run in active_runs
      if run.id not in active_node_run_ids
      and (_utc(run.updated_at) or now) <= stale_before
    ]

    failed_runs = list(
      await self._session.scalars(
        select(WorkflowGraphInstance)
        .where(WorkflowGraphInstance.status == WorkflowGraphInstanceStatus.FAILED)
        .order_by(WorkflowGraphInstance.updated_at.desc())
        .limit(normalized_limit)
      )
    )
    suspended_nodes = list(
      await self._session.scalars(
        select(WorkflowNodeInstance)
        .where(WorkflowNodeInstance.engine_state == WorkflowNodeEngineState.SUSPENDED)
        .order_by(WorkflowNodeInstance.updated_at.desc())
        .limit(normalized_limit)
      )
    )
    suspended_node_count = int(
      await self._session.scalar(
        select(func.count()).select_from(WorkflowNodeInstance).where(
          WorkflowNodeInstance.engine_state == WorkflowNodeEngineState.SUSPENDED
        )
      )
      or 0
    )
    failed_nodes = list(
      await self._session.scalars(
        select(WorkflowNodeInstance)
        .where(WorkflowNodeInstance.engine_state == WorkflowNodeEngineState.FAILED)
        .order_by(WorkflowNodeInstance.updated_at.desc())
        .limit(normalized_limit)
      )
    )
    waiting_dependencies = list(
      await self._session.scalars(
        select(WorkflowNodeActivationDependency)
        .where(WorkflowNodeActivationDependency.status == "waiting")
        .order_by(WorkflowNodeActivationDependency.created_at.asc())
        .limit(normalized_limit)
      )
    )
    join_wait_count = int(
      await self._session.scalar(
        select(func.count()).select_from(WorkflowNodeActivationDependency).where(
          WorkflowNodeActivationDependency.status == "waiting"
        )
      )
      or 0
    )
    oldest_join_wait = await self._session.scalar(
      select(func.min(WorkflowNodeActivationDependency.created_at)).where(
        WorkflowNodeActivationDependency.status == "waiting"
      )
    )

    outbox_counts = {
      status.value: int(count)
      for status, count in (
        await self._session.execute(
          select(WorkflowOutboxEvent.status, func.count()).group_by(WorkflowOutboxEvent.status)
        )
      ).all()
    }
    for status in WorkflowOutboxEventStatus:
      outbox_counts.setdefault(status.value, 0)
    backlog_statuses = [
      WorkflowOutboxEventStatus.PENDING,
      WorkflowOutboxEventStatus.RETRYING,
      WorkflowOutboxEventStatus.FAILED,
    ]
    oldest_outbox = await self._session.scalar(
      select(func.min(WorkflowOutboxEvent.created_at)).where(
        WorkflowOutboxEvent.status.in_(backlog_statuses)
      )
    )
    failed_outbox_rows = list(
      await self._session.scalars(
        select(WorkflowOutboxEvent)
        .where(WorkflowOutboxEvent.status == WorkflowOutboxEventStatus.FAILED)
        .order_by(WorkflowOutboxEvent.updated_at.desc())
        .limit(normalized_limit)
      )
    )
    incidents = list(
      await self._session.scalars(
        select(WorkflowOperationalIncident)
        .order_by(
          (WorkflowOperationalIncident.status == "open").desc(),
          WorkflowOperationalIncident.last_seen_at.desc(),
        )
        .limit(normalized_limit)
      )
    )
    context_conflicts = list(
      await self._session.scalars(
        select(WorkflowCommandReceipt)
        .where(WorkflowCommandReceipt.status == "failed")
        .order_by(WorkflowCommandReceipt.created_at.desc())
        .limit(normalized_limit)
      )
    )
    context_conflicts = [
      receipt
      for receipt in context_conflicts
      if "Context version" in str((receipt.error or {}).get("message") or "")
    ]

    issues: list[dict[str, Any]] = []
    for run in failed_runs:
      diagnostics = dict(run.diagnostics or {})
      code = str(diagnostics.get("code") or "failed_run")
      issues.append(
        {
          "category": code,
          "severity": "error",
          "instance_id": str(run.id),
          "node_instance_id": None,
          "title": run.run_label or "工作流运行失败",
          "message": str(diagnostics.get("message") or "工作流运行失败。"),
          "age_seconds": _seconds_since(run.updated_at, now=now),
        }
      )
    for run in sorted(stalled_runs, key=lambda item: _utc(item.updated_at) or now)[:normalized_limit]:
      issues.append(
        {
          "category": "stalled_run",
          "severity": "warning",
          "instance_id": str(run.id),
          "node_instance_id": None,
          "title": run.run_label or "工作流无可执行节点",
          "message": f"Run 超过 {normalized_minutes} 分钟无活动节点。",
          "age_seconds": _seconds_since(run.updated_at, now=now),
        }
      )
    for dependency in waiting_dependencies:
      issues.append(
        {
          "category": "join_wait",
          "severity": "info",
          "instance_id": str(dependency.instance_id),
          "node_instance_id": str(dependency.node_instance_id),
          "title": "Join 等待上游节点",
          "message": "Activation dependency 尚未满足。",
          "age_seconds": _seconds_since(dependency.created_at, now=now),
        }
      )
    for node in suspended_nodes:
      suspension = dict((node.config or {}).get("operational_suspension") or {})
      issues.append(
        {
          "category": "suspended_node",
          "severity": "warning",
          "instance_id": str(node.instance_id),
          "node_instance_id": str(node.id),
          "title": node.title,
          "message": (
            "管理员人工挂起。" if suspension.get("status") == "active" else "节点被运行时策略阻断。"
          ),
          "age_seconds": _seconds_since(node.updated_at, now=now),
        }
      )
    for node in failed_nodes:
      issues.append(
        {
          "category": "failed_node",
          "severity": "error",
          "instance_id": str(node.instance_id),
          "node_instance_id": str(node.id),
          "title": node.title,
          "message": "节点 Handler 执行失败，可在核对原因后受控重试。",
          "age_seconds": _seconds_since(node.updated_at, now=now),
        }
      )
    for receipt in context_conflicts:
      issues.append(
        {
          "category": "context_conflict",
          "severity": "warning",
          "instance_id": (
            str(receipt.aggregate_id) if receipt.aggregate_type == "workflow_run" else None
          ),
          "node_instance_id": (
            str(receipt.aggregate_id) if receipt.aggregate_type == "workflow_node" else None
          ),
          "title": "Context version 冲突",
          "message": "命令基于过期的上下文版本执行。",
          "age_seconds": _seconds_since(receipt.created_at, now=now),
        }
      )

    projection_streams = await self._projection_health(now=now)
    shadow = await self._latest_shadow_summary()
    return {
      "generated_at": now,
      "stalled_minutes": normalized_minutes,
      "metrics": {
        "runs": run_counts,
        "stalled_run_count": len(stalled_runs),
        "suspended_node_count": suspended_node_count,
        "join_wait_count": join_wait_count,
        "oldest_join_wait_seconds": _seconds_since(oldest_join_wait, now=now) or 0,
        "outbox": outbox_counts,
        "outbox_backlog_count": sum(outbox_counts[item.value] for item in backlog_statuses),
        "oldest_outbox_backlog_seconds": _seconds_since(oldest_outbox, now=now) or 0,
        "projection_failed_stream_count": sum(
          1 for item in projection_streams if item["status"] == "failed"
        ),
      },
      "projection_streams": projection_streams,
      "shadow": shadow,
      "issues": issues[:normalized_limit],
      "failed_outbox": [self._outbox_read(item) for item in failed_outbox_rows],
      "incidents": [self._incident_read(item) for item in incidents],
    }

  async def replay_outbox(
    self,
    *,
    outbox_event_id: UUID,
    actor_user_id: UUID,
    reason: str,
  ) -> dict[str, Any]:
    normalized_reason = self._validate_reason(reason)
    event = await self._session.scalar(
      select(WorkflowOutboxEvent)
      .where(WorkflowOutboxEvent.id == outbox_event_id)
      .with_for_update()
    )
    if event is None:
      raise NotFoundError("Outbox 事件不存在。")
    if event.status != WorkflowOutboxEventStatus.FAILED:
      raise ConflictError("只有 FAILED Outbox 事件可以人工重放。")
    now = datetime.now(UTC)
    event.status = WorkflowOutboxEventStatus.RETRYING
    event.attempt_count = 0
    event.available_at = now
    event.dispatched_at = None
    event.manual_replay_count += 1
    event.last_replayed_at = now
    event.last_replayed_by_user_id = actor_user_id
    event.last_replay_reason = normalized_reason
    await self._session.flush()
    await WorkflowRunEventService(self._session).append(
      instance_id=event.instance_id,
      event_type="outbox_replayed",
      actor_user_id=actor_user_id,
      node_instance_id=event.node_instance_id,
      payload={
        "outbox_event_id": str(event.id),
        "node_instance_id": _uuid(event.node_instance_id),
        "reason": normalized_reason,
        "manual_replay_count": event.manual_replay_count,
      },
    )
    return {
      "id": str(event.id),
      "status": event.status.value,
      "manual_replay_count": event.manual_replay_count,
    }

  async def update_incident(
    self,
    *,
    incident_id: UUID,
    actor_user_id: UUID,
    status: str,
    reason: str,
  ) -> dict[str, Any]:
    if status not in {"resolved", "ignored"}:
      raise AppValidationError("Incident 只能标记为 resolved 或 ignored。")
    normalized_reason = self._validate_reason(reason)
    incident = await self._session.scalar(
      select(WorkflowOperationalIncident)
      .where(WorkflowOperationalIncident.id == incident_id)
      .with_for_update()
    )
    if incident is None:
      raise NotFoundError("Incident 不存在。")
    incident.status = status
    incident.resolved_at = datetime.now(UTC)
    incident.resolved_by_user_id = actor_user_id
    incident.resolution_note = normalized_reason
    await self._session.flush()
    if incident.instance_id is not None:
      await WorkflowRunEventService(self._session).append(
        instance_id=incident.instance_id,
        event_type="operational_incident_updated",
        actor_user_id=actor_user_id,
        node_instance_id=incident.node_instance_id,
        task_id=incident.task_id,
        payload={
          "incident_id": str(incident.id),
          "node_instance_id": _uuid(incident.node_instance_id),
          "task_id": _uuid(incident.task_id),
          "status": status,
          "reason": normalized_reason,
        },
      )
    return {"id": str(incident.id), "status": incident.status}

  async def search_traces(
    self,
    *,
    request_id: str | None = None,
    command_id: str | None = None,
    correlation_id: UUID | None = None,
    instance_id: UUID | None = None,
    node_instance_id: UUID | None = None,
    task_id: UUID | None = None,
    limit: int = 50,
  ) -> list[dict[str, Any]]:
    query = select(WorkflowRunEvent)
    filters = []
    if request_id and request_id.strip():
      filters.append(WorkflowRunEvent.request_id == request_id.strip())
    if command_id and command_id.strip():
      filters.append(WorkflowRunEvent.command_id == command_id.strip())
    if correlation_id is not None:
      filters.append(WorkflowRunEvent.correlation_id == correlation_id)
    if instance_id is not None:
      filters.append(WorkflowRunEvent.instance_id == instance_id)
    if node_instance_id is not None:
      filters.append(WorkflowRunEvent.node_instance_id == node_instance_id)
    if task_id is not None:
      filters.append(WorkflowRunEvent.task_id == task_id)
    if filters:
      query = query.where(*filters)
    rows = list(
      await self._session.scalars(
        query.order_by(WorkflowRunEvent.occurred_at.desc()).limit(max(1, min(limit, 100)))
      )
    )
    return [
      {
        "id": str(item.id),
        "event_type": item.event_type,
        "occurred_at": item.occurred_at,
        "request_id": item.request_id,
        "command_id": item.command_id,
        "correlation_id": _uuid(item.correlation_id),
        "instance_id": str(item.instance_id),
        "node_instance_id": _uuid(item.node_instance_id),
        "task_id": _uuid(item.task_id),
        "actor_user_id": _uuid(item.actor_user_id),
        "payload_keys": sorted(str(key) for key in dict(item.payload or {})),
      }
      for item in rows
    ]

  async def _projection_health(self, *, now: datetime) -> list[dict[str, Any]]:
    source_models = {
      "workflow_run_events": (WorkflowRunEvent, WorkflowRunEvent.occurred_at),
      "task_logs": (TaskLog, TaskLog.created_at),
      "task_comments": (TaskComment, TaskComment.created_at),
    }
    checkpoints = {
      item.stream_name: item
      for item in await self._session.scalars(select(ProjectionCheckpoint))
    }
    result: list[dict[str, Any]] = []
    for stream_name, (model, occurred_column) in source_models.items():
      checkpoint = checkpoints.get(stream_name)
      source_count = int(
        await self._session.scalar(select(func.count()).select_from(model)) or 0
      )
      latest_source = await self._session.scalar(select(func.max(occurred_column)))
      oldest_source = await self._session.scalar(select(func.min(occurred_column)))
      cursor = checkpoint.cursor_occurred_at if checkpoint is not None else None
      if cursor is None:
        backlog_count = source_count
      else:
        backlog_count = int(
          await self._session.scalar(
            select(func.count()).select_from(model).where(occurred_column > cursor)
          )
          or 0
        )
      normalized_latest = _utc(latest_source)
      normalized_cursor = _utc(cursor)
      lag_seconds = 0
      if normalized_latest is not None:
        if normalized_cursor is None:
          lag_seconds = _seconds_since(oldest_source, now=now) or 0
        else:
          lag_seconds = max(0, int((normalized_latest - normalized_cursor).total_seconds()))
      result.append(
        {
          "stream_name": stream_name,
          "status": checkpoint.status if checkpoint is not None else "uninitialized",
          "processed_count": int(checkpoint.processed_count) if checkpoint is not None else 0,
          "source_count": source_count,
          "backlog_count": backlog_count,
          "lag_seconds": lag_seconds,
          "last_success_at": checkpoint.last_success_at if checkpoint is not None else None,
          "last_error": checkpoint.last_error if checkpoint is not None else None,
          "sampled_at": now,
        }
      )
    return result

  async def _latest_shadow_summary(self) -> dict[str, Any] | None:
    latest = await self._session.scalar(
      select(ProjectionShadowObservation)
      .order_by(ProjectionShadowObservation.observed_at.desc())
      .limit(1)
    )
    if latest is None:
      return None
    rows = list(
      await self._session.scalars(
        select(ProjectionShadowObservation).where(
          ProjectionShadowObservation.scan_id == latest.scan_id
        )
      )
    )
    outcome_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    for item in rows:
      outcome_counts[item.outcome] = outcome_counts.get(item.outcome, 0) + 1
      severity_counts[item.severity] = severity_counts.get(item.severity, 0) + 1
    return {
      "scan_id": str(latest.scan_id),
      "sample_mode": latest.sample_mode,
      "observed_at": latest.observed_at,
      "outcomes": outcome_counts,
      "severities": severity_counts,
    }

  @staticmethod
  def _validate_reason(reason: str) -> str:
    normalized = reason.strip()
    if len(normalized) < 3 or len(normalized) > 500:
      raise AppValidationError("运维原因长度必须为 3–500 个字符。")
    return normalized

  @staticmethod
  def _outbox_read(event: WorkflowOutboxEvent) -> dict[str, Any]:
    return {
      "id": str(event.id),
      "instance_id": str(event.instance_id),
      "node_instance_id": _uuid(event.node_instance_id),
      "event_type": event.event_type,
      "status": event.status.value,
      "attempt_count": event.attempt_count,
      "available_at": event.available_at,
      "last_error": event.last_error,
      "manual_replay_count": event.manual_replay_count,
      "last_replayed_at": event.last_replayed_at,
      "last_replayed_by_user_id": _uuid(event.last_replayed_by_user_id),
      "last_replay_reason": event.last_replay_reason,
      "updated_at": event.updated_at,
    }

  @staticmethod
  def _incident_read(incident: WorkflowOperationalIncident) -> dict[str, Any]:
    return {
      "id": str(incident.id),
      "category": incident.category,
      "status": incident.status,
      "severity": incident.severity,
      "occurrence_count": incident.occurrence_count,
      "first_seen_at": incident.first_seen_at,
      "last_seen_at": incident.last_seen_at,
      "resolved_at": incident.resolved_at,
      "resolved_by_user_id": _uuid(incident.resolved_by_user_id),
      "resolution_note": incident.resolution_note,
      "instance_id": _uuid(incident.instance_id),
      "node_instance_id": _uuid(incident.node_instance_id),
      "task_id": _uuid(incident.task_id),
      "command_receipt_id": _uuid(incident.command_receipt_id),
      "outbox_event_id": _uuid(incident.outbox_event_id),
      "engine_version": incident.engine_version,
      "detail_keys": sorted(str(key) for key in dict(incident.details or {})),
    }
