from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ProjectionCheckpoint, TaskLog
from app.services.workflow_projection_service import (
  PROJECTION_NAME,
  STREAM_TASK_LOGS,
  WorkflowProjectionService,
)
from app.workers.arq_worker import (
  WORKFLOW_PROJECTION_JOB,
  WorkerSettings,
  process_workflow_projection_events_job,
)
from app.workers.workflow_projection_worker import process_workflow_projection_events
from tests.test_workflow_projection_service import _seed_projection_sources


@pytest.mark.asyncio
async def test_projection_worker_isolates_stream_failure_from_business_sources(
  db_session: AsyncSession,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  await _seed_projection_sources(db_session)
  await db_session.commit()
  session_factory = async_sessionmaker(
    bind=db_session.bind,
    class_=AsyncSession,
    expire_on_commit=False,
  )
  original_consume = WorkflowProjectionService.consume_stream

  async def fail_task_log_stream(self, *, stream_name: str, batch_size: int = 100):
    if stream_name == STREAM_TASK_LOGS:
      raise RuntimeError("simulated task log projection failure")
    return await original_consume(self, stream_name=stream_name, batch_size=batch_size)

  monkeypatch.setattr(WorkflowProjectionService, "consume_stream", fail_task_log_stream)
  processed_count = await process_workflow_projection_events(
    session_factory=session_factory,
    batch_size=10,
  )
  assert processed_count == 2

  async with session_factory() as verification_session:
    checkpoint = await verification_session.scalar(
      select(ProjectionCheckpoint).where(
        ProjectionCheckpoint.projection_name == PROJECTION_NAME,
        ProjectionCheckpoint.stream_name == STREAM_TASK_LOGS,
      )
    )
    assert checkpoint is not None
    assert checkpoint.status == "failed"
    assert "simulated task log projection failure" in (checkpoint.last_error or "")
    assert await verification_session.scalar(select(func.count(TaskLog.id))) == 1


def test_projection_worker_is_registered_as_an_independent_periodic_job() -> None:
  assert process_workflow_projection_events_job in WorkerSettings.functions
  assert any(job.name == WORKFLOW_PROJECTION_JOB for job in WorkerSettings.cron_jobs)
