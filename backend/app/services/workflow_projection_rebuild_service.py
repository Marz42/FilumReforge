"""Flush-only single-object and full rebuild orchestration for Iteration 5 projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
  NodeTimelineEntry,
  ProcessRunSummary,
  ProjectionCheckpoint,
  Task,
  TaskCenterItem,
  TaskComment,
  TaskLog,
  WorkflowGraphInstance,
  WorkflowHumanTaskLink,
  WorkflowRunEvent,
)
from app.services.workflow_projection_service import (
  PROJECTION_NAME,
  STREAM_TASK_COMMENTS,
  STREAM_TASK_LOGS,
  STREAM_WORKFLOW_RUN_EVENTS,
  WorkflowProjectionService,
)


@dataclass(frozen=True, slots=True)
class ProjectionRebuildResult:
  task_count: int
  run_count: int
  timeline_count: int


class WorkflowProjectionRebuildService:
  """Projection-only rebuild commands. The caller owns commit/rollback."""

  def __init__(self, session: AsyncSession) -> None:
    self._session = session
    self._projector = WorkflowProjectionService(session)

  async def rebuild_task(
    self,
    task_id: UUID,
    *,
    refresh_run: bool = True,
  ) -> TaskCenterItem | None:
    await self._session.execute(
      delete(NodeTimelineEntry).where(
        NodeTimelineEntry.task_id == task_id,
        NodeTimelineEntry.source_type.in_(["task_log", "task_comment"]),
      )
    )
    logs = list(
      await self._session.scalars(
        select(TaskLog)
        .where(TaskLog.task_id == task_id)
        .order_by(TaskLog.created_at.asc(), TaskLog.id.asc())
      )
    )
    comments = list(
      await self._session.scalars(
        select(TaskComment)
        .where(TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at.asc(), TaskComment.id.asc())
      )
    )
    for log in logs:
      await self._projector.project_task_log(log, force=True, refresh_parents=False)
    for comment in comments:
      await self._projector.project_task_comment(
        comment,
        force=True,
        refresh_parents=False,
      )
    item = await self._projector.project_task(task_id=task_id, force=True)
    if refresh_run:
      run_id = await self._run_id_for_task(task_id)
      if run_id is not None:
        await self._projector.project_run(run_id=run_id, force=True)
    await self._session.flush()
    return item

  async def rebuild_run(self, run_id: UUID) -> ProcessRunSummary | None:
    await self._session.execute(
      delete(NodeTimelineEntry).where(
        NodeTimelineEntry.process_run_id == run_id,
        NodeTimelineEntry.source_type == "workflow_run_event",
      )
    )
    events = list(
      await self._session.scalars(
        select(WorkflowRunEvent)
        .where(WorkflowRunEvent.instance_id == run_id)
        .order_by(WorkflowRunEvent.occurred_at.asc(), WorkflowRunEvent.id.asc())
      )
    )
    for event in events:
      await self._projector.project_run_event(event, force=True, refresh_parents=False)

    task_ids = set(
      await self._session.scalars(
        select(WorkflowHumanTaskLink.task_id).where(
          WorkflowHumanTaskLink.instance_id == run_id
        )
      )
    )
    root_task_ids = list(
      await self._session.scalars(
        select(Task.id).where(
          Task.extra_metadata["workflow_graph_instance_id"].as_string() == str(run_id),
          Task.extra_metadata["workflow_graph_root_task"].as_boolean().is_(True),
        )
      )
    )
    task_ids.update(root_task_ids)
    for task_id in sorted(task_ids, key=str):
      await self.rebuild_task(task_id, refresh_run=False)
    summary = await self._projector.project_run(run_id=run_id, force=True)
    await self._session.flush()
    return summary

  async def rebuild_all(self) -> ProjectionRebuildResult:
    high_watermarks = {
      STREAM_WORKFLOW_RUN_EVENTS: await self._high_watermark(
        WorkflowRunEvent,
        WorkflowRunEvent.occurred_at,
      ),
      STREAM_TASK_LOGS: await self._high_watermark(TaskLog, TaskLog.created_at),
      STREAM_TASK_COMMENTS: await self._high_watermark(
        TaskComment,
        TaskComment.created_at,
      ),
    }
    source_counts = {
      STREAM_WORKFLOW_RUN_EVENTS: int(
        await self._session.scalar(select(func.count(WorkflowRunEvent.id))) or 0
      ),
      STREAM_TASK_LOGS: int(
        await self._session.scalar(select(func.count(TaskLog.id))) or 0
      ),
      STREAM_TASK_COMMENTS: int(
        await self._session.scalar(select(func.count(TaskComment.id))) or 0
      ),
    }
    task_ids = list(await self._session.scalars(select(Task.id).order_by(Task.id.asc())))
    run_ids = list(
      await self._session.scalars(
        select(WorkflowGraphInstance.id).order_by(WorkflowGraphInstance.id.asc())
      )
    )

    await self._session.execute(delete(NodeTimelineEntry))
    await self._session.execute(delete(TaskCenterItem))
    await self._session.execute(delete(ProcessRunSummary))
    await self._session.execute(
      delete(ProjectionCheckpoint).where(
        ProjectionCheckpoint.projection_name == PROJECTION_NAME
      )
    )
    await self._session.flush()

    for task_id in task_ids:
      await self.rebuild_task(task_id, refresh_run=False)
    for run_id in run_ids:
      await self.rebuild_run(run_id)
    for stream_name, cursor in high_watermarks.items():
      await self._projector.set_checkpoint_cursor(
        stream_name=stream_name,
        cursor=cursor,
        processed_count=source_counts[stream_name],
      )
    timeline_count = int(
      await self._session.scalar(select(func.count(NodeTimelineEntry.id))) or 0
    )
    await self._session.flush()
    return ProjectionRebuildResult(
      task_count=len(task_ids),
      run_count=len(run_ids),
      timeline_count=timeline_count,
    )

  async def _run_id_for_task(self, task_id: UUID) -> UUID | None:
    run_id = await self._session.scalar(
      select(WorkflowHumanTaskLink.instance_id)
      .where(WorkflowHumanTaskLink.task_id == task_id)
      .order_by(
        (WorkflowHumanTaskLink.lifecycle == "active").desc(),
        WorkflowHumanTaskLink.updated_at.desc(),
      )
    )
    if run_id is not None:
      return run_id
    task = await self._session.get(Task, task_id)
    if task is None:
      return None
    raw = dict(task.extra_metadata or {}).get("workflow_graph_instance_id")
    try:
      return UUID(str(raw)) if raw is not None else None
    except ValueError:
      return None

  async def _high_watermark(
    self,
    model: type,
    time_column: object,
  ) -> tuple[datetime, UUID] | None:
    source = await self._session.scalar(
      select(model).order_by(time_column.desc(), model.id.desc()).limit(1)
    )
    if source is None:
      return None
    return getattr(source, time_column.key), source.id
