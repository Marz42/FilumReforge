from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
  TaskActionType,
  TaskPriority,
  TaskSourceType,
  TaskStatus,
  UserRole,
  UserStatus,
  WorkflowGraphInstanceStatus,
  WorkflowGraphNodeType,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.core.config import Settings
from app.models import (
  NodeTimelineEntry,
  ProcessRunSummary,
  ProjectionCheckpoint,
  Task,
  TaskCenterItem,
  TaskComment,
  TaskLog,
  TaskWatcher,
  User,
  WorkflowGraphInstance,
  WorkflowHumanTaskLink,
  WorkflowNodeInstance,
  WorkflowRunEvent,
)
from app.services.workflow_projection_rebuild_service import WorkflowProjectionRebuildService
from app.services.task_service import TaskService
from app.scripts.rebuild_workflow_projections import parse_args as parse_rebuild_args
from app.services.workflow_projection_service import (
  PROJECTION_NAME,
  STREAM_TASK_COMMENTS,
  STREAM_TASK_LOGS,
  STREAM_WORKFLOW_RUN_EVENTS,
  WorkflowProjectionService,
)


def test_rebuild_cli_requires_one_explicit_scope() -> None:
  task_id = "00000000-0000-0000-0000-000000000001"
  run_id = "00000000-0000-0000-0000-000000000002"
  assert parse_rebuild_args(["--task-id", task_id]).task_id == task_id
  assert parse_rebuild_args(["--run-id", run_id]).run_id == run_id
  assert parse_rebuild_args(["--all"]).rebuild_all is True
  with pytest.raises(SystemExit):
    parse_rebuild_args([])
  with pytest.raises(SystemExit):
    parse_rebuild_args(["--all", "--task-id", task_id])


async def _seed_projection_sources(db_session: AsyncSession) -> dict[str, object]:
  now = datetime.now(UTC)
  creator = User(
    email="projection-creator@example.com",
    password_hash="test",
    role=UserRole.ADMIN,
    status=UserStatus.ACTIVE,
  )
  assignee = User(
    email="projection-assignee@example.com",
    password_hash="test",
    role=UserRole.EMPLOYEE,
    status=UserStatus.ACTIVE,
  )
  watcher = User(
    email="projection-watcher@example.com",
    password_hash="test",
    role=UserRole.EMPLOYEE,
    status=UserStatus.ACTIVE,
  )
  db_session.add_all([creator, assignee, watcher])
  await db_session.flush()

  run = WorkflowGraphInstance(
    initiator_user_id=creator.id,
    source_type="template",
    status=WorkflowGraphInstanceStatus.ACTIVE,
    current_node_key="approve",
    run_label="投影测试 Run",
    context={},
    context_version=1,
    max_iterations=5,
  )
  db_session.add(run)
  await db_session.flush()

  node = WorkflowNodeInstance(
    instance_id=run.id,
    node_key="approve",
    title="负责人验收",
    node_type=WorkflowGraphNodeType.APPROVAL,
    engine_state=WorkflowNodeEngineState.ACTIVATED,
    business_state=WorkflowNodeBusinessState.PENDING_REVIEW,
    assignee_user_id=assignee.id,
    iteration=1,
    node_instance_version=2,
    activated_at=now,
  )
  db_session.add(node)
  await db_session.flush()

  task = Task(
    title="提交并验收材料",
    creator_id=creator.id,
    assignee_id=assignee.id,
    status=TaskStatus.REVIEW,
    priority=TaskPriority.HIGH,
    source_type=TaskSourceType.TEMPLATE,
    assignment_mode="direct",
    extra_metadata={
      "workflow_graph_instance_id": str(run.id),
      "workflow_node_instance_id": str(node.id),
      "reviewer_id": str(creator.id),
      "task_capability": {
        "surface": "review",
        "submit_mode": "review",
        "state_policy": "review",
      },
    },
  )
  db_session.add(task)
  await db_session.flush()
  db_session.add_all([
    WorkflowHumanTaskLink(
      instance_id=run.id,
      node_instance_id=node.id,
      task_id=task.id,
      link_role="primary",
      lifecycle="active",
      source="runtime",
      iteration=1,
    ),
    TaskWatcher(
      task_id=task.id,
      user_id=watcher.id,
      relation="watching",
      created_by=creator.id,
    ),
  ])
  await db_session.flush()

  run_event = WorkflowRunEvent(
    instance_id=run.id,
    event_type="approval_requested",
    event_version=1,
    aggregate_version=2,
    actor_user_id=creator.id,
    payload={"node_instance_id": str(node.id), "task_id": str(task.id)},
    occurred_at=now,
    created_at=now,
  )
  task_log = TaskLog(
    task_id=task.id,
    operator_id=assignee.id,
    action_type=TaskActionType.STATUS_CHANGED,
    from_status=TaskStatus.DOING,
    to_status=TaskStatus.REVIEW,
    detail={"reason": "提交验收"},
    created_at=now + timedelta(microseconds=1),
  )
  comment = TaskComment(
    task_id=task.id,
    user_id=watcher.id,
    content="这是一条只投影摘要、不复制完整业务正文的评论。",
    is_internal=True,
    created_at=now + timedelta(microseconds=2),
    updated_at=now + timedelta(microseconds=2),
  )
  db_session.add_all([run_event, task_log, comment])
  await db_session.flush()
  return {
    "creator": creator,
    "assignee": assignee,
    "watcher": watcher,
    "run": run,
    "node": node,
    "task": task,
    "run_event": run_event,
    "task_log": task_log,
    "comment": comment,
  }


@pytest.mark.asyncio
async def test_single_task_and_run_rebuild_are_idempotent(db_session: AsyncSession) -> None:
  seeded = await _seed_projection_sources(db_session)
  task = seeded["task"]
  run = seeded["run"]
  creator = seeded["creator"]
  watcher = seeded["watcher"]
  assert isinstance(task, Task)
  assert isinstance(run, WorkflowGraphInstance)
  assert isinstance(creator, User)
  assert isinstance(watcher, User)

  rebuild = WorkflowProjectionRebuildService(db_session)
  await rebuild.rebuild_task(task.id)
  await rebuild.rebuild_task(task.id)

  task_item = await db_session.scalar(
    select(TaskCenterItem).where(TaskCenterItem.task_id == task.id)
  )
  assert task_item is not None
  assert task_item.subject_type == "work_item"
  assert task_item.item_kind == "approval"
  assert task_item.current_action_owner_user_id == creator.id
  assert set(task_item.audience_user_ids) >= {str(creator.id), str(watcher.id)}
  assert await db_session.scalar(
    select(func.count(NodeTimelineEntry.id)).where(
      NodeTimelineEntry.task_id == task.id,
      NodeTimelineEntry.source_type.in_(["task_log", "task_comment"]),
    )
  ) == 2

  await rebuild.rebuild_run(run.id)
  await rebuild.rebuild_run(run.id)
  summary = await db_session.scalar(
    select(ProcessRunSummary).where(ProcessRunSummary.process_run_id == run.id)
  )
  assert summary is not None
  assert summary.total_node_count == 1
  assert summary.active_node_count == 1
  assert summary.current_stage_label == "负责人验收"
  assert await db_session.scalar(
    select(func.count(NodeTimelineEntry.id)).where(
      NodeTimelineEntry.process_run_id == run.id,
      NodeTimelineEntry.source_type == "workflow_run_event",
    )
  ) == 1


@pytest.mark.asyncio
async def test_incremental_consume_uses_independent_stable_checkpoints(
  db_session: AsyncSession,
) -> None:
  seeded = await _seed_projection_sources(db_session)
  service = WorkflowProjectionService(db_session)

  first_counts = {}
  for stream_name in (
    STREAM_WORKFLOW_RUN_EVENTS,
    STREAM_TASK_LOGS,
    STREAM_TASK_COMMENTS,
  ):
    result = await service.consume_stream(stream_name=stream_name, batch_size=1)
    first_counts[stream_name] = result.processed_count
  assert first_counts == {
    STREAM_WORKFLOW_RUN_EVENTS: 1,
    STREAM_TASK_LOGS: 1,
    STREAM_TASK_COMMENTS: 1,
  }

  for stream_name in first_counts:
    assert (await service.consume_stream(stream_name=stream_name, batch_size=10)).processed_count == 0

  checkpoints = list(
    await db_session.scalars(
      select(ProjectionCheckpoint).where(
        ProjectionCheckpoint.projection_name == PROJECTION_NAME
      )
    )
  )
  assert {checkpoint.stream_name for checkpoint in checkpoints} == set(first_counts)
  assert all(checkpoint.status == "idle" for checkpoint in checkpoints)
  assert all(checkpoint.processed_count == 1 for checkpoint in checkpoints)
  assert all(checkpoint.cursor_occurred_at is not None for checkpoint in checkpoints)
  assert all(checkpoint.cursor_source_id is not None for checkpoint in checkpoints)

  task = seeded["task"]
  assert isinstance(task, Task)
  assert await db_session.scalar(
    select(func.count(TaskCenterItem.id)).where(TaskCenterItem.task_id == task.id)
  ) == 1


@pytest.mark.asyncio
async def test_older_revision_cannot_overwrite_without_explicit_rebuild(
  db_session: AsyncSession,
) -> None:
  seeded = await _seed_projection_sources(db_session)
  task = seeded["task"]
  assert isinstance(task, Task)
  service = WorkflowProjectionService(db_session)
  item = await service.project_task(task_id=task.id)
  assert item is not None
  item.title = "较新的投影"
  item.source_revision = 9_999_999_999_999_999
  await db_session.flush()

  assert (await service.project_task(task_id=task.id)).title == "较新的投影"
  refreshed = await service.project_task(task_id=task.id, force=True)
  assert refreshed is not None
  assert refreshed.title == task.title


@pytest.mark.asyncio
async def test_full_rebuild_removes_stale_rows_and_anchors_high_watermarks(
  db_session: AsyncSession,
) -> None:
  seeded = await _seed_projection_sources(db_session)
  now = datetime.now(UTC)
  stale = TaskCenterItem(
    subject_type="system_alert",
    item_kind="system_alert",
    subject_id=seeded["watcher"].id,
    title="应被全量重建移除",
    raw_status="open",
    source_created_at=now,
    source_updated_at=now,
  )
  db_session.add(stale)
  await db_session.flush()

  result = await WorkflowProjectionRebuildService(db_session).rebuild_all()
  assert result.task_count == 1
  assert result.run_count == 1
  assert await db_session.get(TaskCenterItem, stale.id) is None

  checkpoints = list(
    await db_session.scalars(
      select(ProjectionCheckpoint).where(
        ProjectionCheckpoint.projection_name == PROJECTION_NAME
      )
    )
  )
  assert {checkpoint.stream_name for checkpoint in checkpoints} == {
    STREAM_WORKFLOW_RUN_EVENTS,
    STREAM_TASK_LOGS,
    STREAM_TASK_COMMENTS,
  }
  assert all(checkpoint.status == "idle" for checkpoint in checkpoints)
  assert all(checkpoint.cursor_occurred_at is not None for checkpoint in checkpoints)
  assert all(checkpoint.cursor_source_id is not None for checkpoint in checkpoints)


@pytest.mark.asyncio
async def test_iteration5e_projection_first_read_and_dynamic_fallback(
  db_session: AsyncSession,
) -> None:
  seeded = await _seed_projection_sources(db_session)
  task = seeded["task"]
  assert isinstance(task, Task)
  await WorkflowProjectionRebuildService(db_session).rebuild_all()

  item = await db_session.scalar(
    select(TaskCenterItem).where(TaskCenterItem.task_id == task.id)
  )
  assert item is not None
  item.title = "5-E 投影标题"
  await db_session.flush()

  projection_first = TaskService(
    db_session,
    settings=Settings(
      jwt_secret_key="iteration-5e-projection-read-secret-32-bytes",
      task_center_projection_reads_enabled=True,
      task_center_projection_fallback_enabled=True,
    ),
  )
  projected = await projection_first._graph_task_projection_map(tasks=[task])
  assert projected[task.id].title == "5-E 投影标题"

  item.projection_schema_version = 99
  await db_session.flush()
  fallback = await projection_first._graph_task_projection_map(tasks=[task])
  assert fallback[task.id].title is None
  assert fallback[task.id].status == TaskStatus.REVIEW


@pytest.mark.asyncio
async def test_iteration5e_can_disable_fallback_for_strict_canary(
  db_session: AsyncSession,
) -> None:
  seeded = await _seed_projection_sources(db_session)
  task = seeded["task"]
  creator = seeded["creator"]
  assert isinstance(task, Task)
  assert isinstance(creator, User)

  strict_projection = TaskService(
    db_session,
    settings=Settings(
      jwt_secret_key="iteration-5e-strict-read-secret-32-bytes",
      task_center_projection_reads_enabled=True,
      task_center_projection_fallback_enabled=False,
    ),
  )
  assert await strict_projection._graph_task_projection_map(tasks=[task]) == {}
  assert all(
    entry.task_id != task.id
    for entry in (await strict_projection.list_task_inbox(actor=creator)).items
  )

  await WorkflowProjectionRebuildService(db_session).rebuild_task(task.id)
  assert any(
    entry.task_id == task.id
    for entry in (await strict_projection.list_task_inbox(actor=creator)).items
  )
