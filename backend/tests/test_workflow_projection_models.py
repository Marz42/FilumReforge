from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import BigInteger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
  NodeTimelineEntry,
  ProcessRunSummary,
  ProjectionCheckpoint,
  ProjectionShadowObservation,
  TaskCenterItem,
)


def _constraint_names(model: type) -> set[str]:
  return {
    constraint.name
    for constraint in model.__table__.constraints
    if constraint.name is not None
  }


def _index_names(model: type) -> set[str]:
  return {index.name for index in model.__table__.indexes if index.name is not None}


def test_projection_models_fix_identity_rebuild_and_sort_contracts() -> None:
  assert TaskCenterItem.__tablename__ == "task_center_items"
  assert ProcessRunSummary.__tablename__ == "process_run_summaries"
  assert NodeTimelineEntry.__tablename__ == "node_timeline_entries"
  assert ProjectionCheckpoint.__tablename__ == "projection_checkpoints"
  assert ProjectionShadowObservation.__tablename__ == "projection_shadow_observations"

  assert "uq_task_center_items_subject" in _constraint_names(TaskCenterItem)
  assert "task_center_items_subject_target_chk" in _constraint_names(TaskCenterItem)
  assert "task_center_items_subject_kind_chk" in _constraint_names(TaskCenterItem)
  assert "idx_task_center_items_action_due" in _index_names(TaskCenterItem)
  assert "idx_task_center_items_history" in _index_names(TaskCenterItem)

  assert "uq_process_run_summaries_run" in _constraint_names(ProcessRunSummary)
  assert "process_run_summaries_progress_chk" in _constraint_names(ProcessRunSummary)
  assert "idx_process_run_summaries_status_updated" in _index_names(ProcessRunSummary)

  assert "uq_node_timeline_entries_source" in _constraint_names(NodeTimelineEntry)
  assert "node_timeline_entries_parent_chk" in _constraint_names(NodeTimelineEntry)
  assert "idx_node_timeline_entries_run_time" in _index_names(NodeTimelineEntry)
  assert "idx_node_timeline_entries_task_time" in _index_names(NodeTimelineEntry)

  assert "uq_projection_checkpoints_projection_stream" in _constraint_names(ProjectionCheckpoint)
  assert "projection_checkpoints_cursor_pair_chk" in _constraint_names(ProjectionCheckpoint)
  assert "projection_checkpoints_status_chk" in _constraint_names(ProjectionCheckpoint)
  assert "idx_projection_checkpoints_status" in _index_names(ProjectionCheckpoint)

  assert "uq_projection_shadow_scan_subject" in _constraint_names(
    ProjectionShadowObservation
  )
  assert "projection_shadow_outcome_chk" in _constraint_names(
    ProjectionShadowObservation
  )
  assert "idx_projection_shadow_scan_outcome" in _index_names(
    ProjectionShadowObservation
  )
  assert "idx_projection_shadow_created_at" in _index_names(
    ProjectionShadowObservation
  )

  for model in (TaskCenterItem, ProcessRunSummary, NodeTimelineEntry):
    columns = model.__table__.columns
    assert columns["projection_schema_version"].nullable is False
    assert columns["source_revision"].nullable is False
    assert isinstance(columns["source_revision"].type, BigInteger)
    assert columns["last_event_id"].nullable is True
    assert columns["projected_at"].nullable is False

  checkpoint_columns = ProjectionCheckpoint.__table__.columns
  assert checkpoint_columns["cursor_occurred_at"].nullable is True
  assert checkpoint_columns["cursor_source_id"].nullable is True
  assert checkpoint_columns["processed_count"].nullable is False
  assert checkpoint_columns["attempt_count"].nullable is False
  assert isinstance(checkpoint_columns["processed_count"].type, BigInteger)

  # Actor-specific policy stays request-time; full business bodies stay in source tables.
  assert "available_actions" not in TaskCenterItem.__table__.columns
  assert "content" not in NodeTimelineEntry.__table__.columns
  assert "attachment_ids" not in NodeTimelineEntry.__table__.columns

  # Shadow evidence stores only field names and fingerprints, never compared values.
  shadow_columns = ProjectionShadowObservation.__table__.columns
  assert "mismatch_fields" in shadow_columns
  assert "expected_fingerprint" in shadow_columns
  assert "actual_fingerprint" in shadow_columns
  for forbidden in ("expected_payload", "actual_payload", "content", "description", "email"):
    assert forbidden not in shadow_columns


@pytest.mark.asyncio
async def test_task_center_subject_identity_is_idempotent(db_session: AsyncSession) -> None:
  now = datetime.now(UTC)
  subject_id = uuid4()
  db_session.add(
    TaskCenterItem(
      subject_type="system_alert",
      item_kind="system_alert",
      subject_id=subject_id,
      title="投影延迟",
      raw_status="open",
      source_created_at=now,
      source_updated_at=now,
    )
  )
  await db_session.flush()

  db_session.add(
    TaskCenterItem(
      subject_type="system_alert",
      item_kind="system_alert",
      subject_id=subject_id,
      title="重复投影",
      raw_status="open",
      source_created_at=now,
      source_updated_at=now,
    )
  )
  with pytest.raises(IntegrityError):
    await db_session.flush()
  await db_session.rollback()


@pytest.mark.asyncio
async def test_projection_database_constraints_reject_invalid_shapes(
  db_session: AsyncSession,
) -> None:
  now = datetime.now(UTC)
  db_session.add(
    TaskCenterItem(
      subject_type="work_item",
      item_kind="human_task",
      subject_id=uuid4(),
      title="缺少 Task 引用",
      raw_status="todo",
      source_created_at=now,
      source_updated_at=now,
    )
  )
  with pytest.raises(IntegrityError):
    await db_session.flush()
  await db_session.rollback()

  db_session.add(
    ProjectionCheckpoint(
      projection_name="workflow_query_v1",
      stream_name="task_logs",
      status="idle",
      cursor_occurred_at=now,
      cursor_source_id=None,
    )
  )
  with pytest.raises(IntegrityError):
    await db_session.flush()
  await db_session.rollback()

  db_session.add(
    ProcessRunSummary(
      process_run_id=uuid4(),
      status="active",
      progress_percent=101,
      started_at=now,
    )
  )
  with pytest.raises(IntegrityError):
    await db_session.flush()
  await db_session.rollback()

  db_session.add(
    NodeTimelineEntry(
      source_type="workflow_run_event",
      source_id=uuid4(),
      entry_type="node_event",
      event_type="node_completed",
      visibility="public",
      title="缺少父对象",
      occurred_at=now,
    )
  )
  with pytest.raises(IntegrityError):
    await db_session.flush()
  await db_session.rollback()
