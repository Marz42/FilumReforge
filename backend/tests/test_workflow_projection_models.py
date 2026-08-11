from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NodeTimelineEntry, ProcessRunSummary, TaskCenterItem


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

  for model in (TaskCenterItem, ProcessRunSummary, NodeTimelineEntry):
    columns = model.__table__.columns
    assert columns["projection_schema_version"].nullable is False
    assert columns["source_revision"].nullable is False
    assert columns["last_event_id"].nullable is True
    assert columns["projected_at"].nullable is False

  # Actor-specific policy stays request-time; full business bodies stay in source tables.
  assert "available_actions" not in TaskCenterItem.__table__.columns
  assert "content" not in NodeTimelineEntry.__table__.columns
  assert "attachment_ids" not in NodeTimelineEntry.__table__.columns


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
