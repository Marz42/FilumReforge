from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import WorkflowGraphNodeType, WorkflowNodeBusinessState, WorkflowNodeEngineState
from app.models import (
  ProcessRunSummary,
  NodeTimelineEntry,
  ProjectionShadowObservation,
  Task,
  TaskCenterItem,
  WorkflowGraphInstance,
  WorkflowNodeInstance,
)
from app.scripts.scan_workflow_projection_shadow import parse_args as parse_scan_args
from app.services.workflow_projection_rebuild_service import WorkflowProjectionRebuildService
from app.services.workflow_projection_shadow_service import WorkflowProjectionShadowService
from tests.test_workflow_projection_service import _seed_projection_sources


def test_shadow_scan_cli_requires_an_explicit_scope() -> None:
  assert parse_scan_args(["--recent"]).sample_mode == "recent"
  assert parse_scan_args(["--full"]).sample_mode == "full"
  with pytest.raises(SystemExit):
    parse_scan_args([])
  with pytest.raises(SystemExit):
    parse_scan_args(["--recent", "--full"])


@pytest.mark.asyncio
async def test_full_shadow_scan_matches_all_three_projection_families(
  db_session: AsyncSession,
) -> None:
  await _seed_projection_sources(db_session)
  await WorkflowProjectionRebuildService(db_session).rebuild_all()

  result = await WorkflowProjectionShadowService(db_session).scan(sample_mode="full")

  assert result.compared_count >= 5
  assert result.difference_count == 0
  observations = list(
    await db_session.scalars(
      select(ProjectionShadowObservation).where(
        ProjectionShadowObservation.scan_id == result.scan_id
      )
    )
  )
  assert {item.comparison_name for item in observations} >= {
    "task_center_item",
    "process_run_summary",
    "node_timeline_entry",
  }
  assert {item.outcome for item in observations} == {"match"}


@pytest.mark.asyncio
async def test_shadow_difference_records_only_field_names_and_fingerprints(
  db_session: AsyncSession,
) -> None:
  seeded = await _seed_projection_sources(db_session)
  task = seeded["task"]
  assert isinstance(task, Task)
  await WorkflowProjectionRebuildService(db_session).rebuild_all()
  item = await db_session.scalar(select(TaskCenterItem).where(TaskCenterItem.task_id == task.id))
  assert item is not None
  item.title = "不应出现在观察记录里的投影旧值"
  await db_session.flush()

  result = await WorkflowProjectionShadowService(db_session).scan(sample_mode="full")
  observation = await db_session.scalar(
    select(ProjectionShadowObservation).where(
      ProjectionShadowObservation.scan_id == result.scan_id,
      ProjectionShadowObservation.comparison_name == "task_center_item",
      ProjectionShadowObservation.subject_id == task.id,
    )
  )

  assert observation is not None
  assert observation.outcome == "difference"
  assert "title" in observation.mismatch_fields
  assert observation.expected_fingerprint != observation.actual_fingerprint
  serialized = str(observation.details)
  assert "不应出现在观察记录里的投影旧值" not in serialized
  assert str(seeded["comment"].content) not in serialized


@pytest.mark.asyncio
async def test_missing_projection_uses_lag_grace_window(db_session: AsyncSession) -> None:
  seeded = await _seed_projection_sources(db_session)
  task = seeded["task"]
  assert isinstance(task, Task)
  await WorkflowProjectionRebuildService(db_session).rebuild_all()
  item = await db_session.scalar(select(TaskCenterItem).where(TaskCenterItem.task_id == task.id))
  assert item is not None
  await db_session.delete(item)
  await db_session.flush()

  recent = await WorkflowProjectionShadowService(db_session).scan(
    sample_mode="full",
    lag_grace_seconds=60,
  )
  recent_observation = await db_session.scalar(
    select(ProjectionShadowObservation).where(
      ProjectionShadowObservation.scan_id == recent.scan_id,
      ProjectionShadowObservation.comparison_name == "task_center_item",
      ProjectionShadowObservation.subject_id == task.id,
    )
  )
  assert recent_observation is not None
  assert recent_observation.outcome == "lagging"

  stale = await WorkflowProjectionShadowService(db_session).scan(
    sample_mode="full",
    lag_grace_seconds=0,
  )
  stale_observation = await db_session.scalar(
    select(ProjectionShadowObservation).where(
      ProjectionShadowObservation.scan_id == stale.scan_id,
      ProjectionShadowObservation.comparison_name == "task_center_item",
      ProjectionShadowObservation.subject_id == task.id,
    )
  )
  assert stale_observation is not None
  assert stale_observation.outcome == "missing_projection"
  assert stale_observation.severity == "error"


@pytest.mark.asyncio
async def test_run_progress_matches_existing_integer_floor_contract(
  db_session: AsyncSession,
) -> None:
  seeded = await _seed_projection_sources(db_session)
  run = seeded["run"]
  node = seeded["node"]
  assert isinstance(run, WorkflowGraphInstance)
  assert isinstance(node, WorkflowNodeInstance)
  node.engine_state = WorkflowNodeEngineState.COMPLETED
  node.business_state = WorkflowNodeBusinessState.DONE
  db_session.add_all(
    [
      WorkflowNodeInstance(
        instance_id=run.id,
        node_key="completed-second",
        title="第二个完成节点",
        node_type=WorkflowGraphNodeType.TASK,
        engine_state=WorkflowNodeEngineState.COMPLETED,
        business_state=WorkflowNodeBusinessState.DONE,
        iteration=1,
        node_instance_version=1,
      ),
      WorkflowNodeInstance(
        instance_id=run.id,
        node_key="pending-third",
        title="第三个待处理节点",
        node_type=WorkflowGraphNodeType.TASK,
        engine_state=WorkflowNodeEngineState.PENDING,
        business_state=WorkflowNodeBusinessState.DRAFT,
        iteration=1,
        node_instance_version=1,
      ),
    ]
  )
  await db_session.flush()

  await WorkflowProjectionRebuildService(db_session).rebuild_all()
  summary = await db_session.scalar(
    select(ProcessRunSummary).where(ProcessRunSummary.process_run_id == run.id)
  )
  assert summary is not None
  assert summary.progress_percent == 66
  result = await WorkflowProjectionShadowService(db_session).scan(sample_mode="full")
  assert result.difference_count == 0


@pytest.mark.asyncio
async def test_full_scan_identifies_orphan_timeline_projection(
  db_session: AsyncSession,
) -> None:
  seeded = await _seed_projection_sources(db_session)
  await WorkflowProjectionRebuildService(db_session).rebuild_all()
  source_id = uuid4()
  db_session.add(
    NodeTimelineEntry(
      process_run_id=seeded["run"].id,
      node_instance_id=seeded["node"].id,
      task_id=seeded["task"].id,
      source_type="task_log",
      source_id=source_id,
      entry_type="work_item_activity",
      event_type="deleted_source",
      visibility="public",
      title="已无源记录的派生行",
      occurred_at=datetime.now(UTC),
      source_revision=1,
    )
  )
  await db_session.flush()

  result = await WorkflowProjectionShadowService(db_session).scan(sample_mode="full")
  observation = await db_session.scalar(
    select(ProjectionShadowObservation).where(
      ProjectionShadowObservation.scan_id == result.scan_id,
      ProjectionShadowObservation.subject_id == source_id,
    )
  )
  assert result.orphan_count == 1
  assert observation is not None
  assert observation.outcome == "orphan_projection"
  assert observation.severity == "error"


@pytest.mark.asyncio
async def test_shadow_evidence_retention_prunes_only_expired_rows(
  db_session: AsyncSession,
) -> None:
  now = datetime.now(UTC)
  expired = ProjectionShadowObservation(
    scan_id=uuid4(),
    comparison_name="task_center_item",
    subject_type="work_item",
    subject_id=uuid4(),
    sample_mode="recent",
    outcome="match",
    severity="info",
    mismatch_fields=[],
    expected_fingerprint="a" * 64,
    actual_fingerprint="a" * 64,
    details={},
    observed_at=now - timedelta(days=31),
    created_at=now - timedelta(days=31),
    updated_at=now - timedelta(days=31),
  )
  retained = ProjectionShadowObservation(
    scan_id=uuid4(),
    comparison_name="task_center_item",
    subject_type="work_item",
    subject_id=uuid4(),
    sample_mode="recent",
    outcome="match",
    severity="info",
    mismatch_fields=[],
    expected_fingerprint="b" * 64,
    actual_fingerprint="b" * 64,
    details={},
    observed_at=now,
  )
  db_session.add_all([expired, retained])
  await db_session.flush()

  assert await WorkflowProjectionShadowService(db_session).prune(retention_days=30) == 1
  assert await db_session.get(ProjectionShadowObservation, expired.id) is None
  assert await db_session.get(ProjectionShadowObservation, retained.id) is retained
