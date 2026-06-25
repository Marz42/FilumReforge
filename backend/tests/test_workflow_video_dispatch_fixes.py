"""Regression tests for video dispatch UX fixes (streaming, root shell, dedupe)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.enums import TaskSourceType, TaskStatus, WorkflowNodeEngineState
from app.core.exceptions import ConflictError
from app.models import Task, WorkflowGraphInstance, WorkflowNodeInstance
from app.schemas.workflow_video import ApprovedTopic, ParticipantsSnapshotEntry, TopicCaptureRow
from app.services.task_service import TaskService
from app.services.workflow_video_form_service import WorkflowVideoFormService
from test_workflow_video_dispatch_topic import _build_form_service, _instantiate_batch_run


async def _dispatch_single_topic(db_session, *, title: str = "脚本提交题") -> dict:
  seed = await _instantiate_batch_run(db_session)
  form = _build_form_service(db_session)
  editor = seed["editors"][0]
  task = seed["editor_tasks"][editor.id]
  submit = await form.submit_capture(
    actor=editor,
    task_id=task.id,
    topics=[TopicCaptureRow(title=title)],
  )
  topic_id = submit.topics[0].topic_id
  assert topic_id is not None

  dispatch = await form.dispatch_topic(
    actor=seed["manager"],
    instance_id=seed["run"].instance.id,
    topic_id=topic_id,
    title=title,
    script_writer_user_id=editor.id,
    source_node_instance_id=submit.node_instance_id,
  )
  assert dispatch.child_instance_id is not None

  child_instance = await db_session.get(WorkflowGraphInstance, dispatch.child_instance_id)
  assert child_instance is not None
  n3_task = await db_session.scalar(
    select(Task).where(
      Task.assignee_id == editor.id,
      Task.source_type == TaskSourceType.TEMPLATE,
    )
  )
  n3_tasks = list(
    await db_session.scalars(
      select(Task).where(
        Task.assignee_id == editor.id,
        Task.source_type == TaskSourceType.TEMPLATE,
      )
    )
  )
  n3_task = next(
    (t for t in n3_tasks if (t.extra_metadata or {}).get("template_node_key") == "N3_SCRIPT_WRITE"),
    None,
  )
  assert n3_task is not None
  return {
    **seed,
    "editor": editor,
    "child_instance": child_instance,
    "n3_task": n3_task,
  }


@pytest.mark.asyncio
async def test_n3_submit_deliverable_advances_to_script_review(db_session) -> None:
  ctx = await _dispatch_single_topic(db_session, title="n3-submit-advance")
  task_service = TaskService(db_session)

  completed = await task_service.submit_task_deliverable(
    actor=ctx["editor"],
    task_id=ctx["n3_task"].id,
    summary="脚本文稿",
    attachment_ids=[],
  )
  assert completed.status == TaskStatus.DONE

  n3_node = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == ctx["child_instance"].id,
      WorkflowNodeInstance.node_key == "N3_SCRIPT_WRITE",
    )
  )
  n4_node = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == ctx["child_instance"].id,
      WorkflowNodeInstance.node_key == "N4_SCRIPT_REVIEW",
    )
  )
  assert n3_node is not None
  assert n4_node is not None
  assert n3_node.engine_state == WorkflowNodeEngineState.COMPLETED
  assert n4_node.engine_state == WorkflowNodeEngineState.ACKNOWLEDGED

  n4_tasks = list(
    await db_session.scalars(
      select(Task).where(
        Task.source_type == TaskSourceType.TEMPLATE,
      )
    )
  )
  n4_task = next(
    (t for t in n4_tasks if (t.extra_metadata or {}).get("template_node_key") == "N4_SCRIPT_REVIEW"),
    None,
  )
  assert n4_task is not None
  assert n4_task.status == TaskStatus.REVIEW


@pytest.mark.asyncio
async def test_n3_submit_with_stale_capture_policy_still_advances(db_session) -> None:
  """Simulate production runs forked before N3 redesign (on_capture_submitted snapshot)."""
  ctx = await _dispatch_single_topic(db_session, title="stale-policy")
  n3_node = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == ctx["child_instance"].id,
      WorkflowNodeInstance.node_key == "N3_SCRIPT_WRITE",
    )
  )
  assert n3_node is not None
  n3_node.config = {
    **dict(n3_node.config or {}),
    "completion_policy": "on_capture_submitted",
  }
  await db_session.flush()

  task_service = TaskService(db_session)
  completed = await task_service.submit_task_deliverable(
    actor=ctx["editor"],
    task_id=ctx["n3_task"].id,
    summary="脚本文稿",
    attachment_ids=[],
  )
  assert completed.status == TaskStatus.DONE

  await db_session.refresh(n3_node)
  assert n3_node.config.get("completion_policy") == "on_submit_deliverable"
  assert n3_node.engine_state == WorkflowNodeEngineState.COMPLETED

  n4_node = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == ctx["child_instance"].id,
      WorkflowNodeInstance.node_key == "N4_SCRIPT_REVIEW",
    )
  )
  assert n4_node is not None
  assert n4_node.engine_state == WorkflowNodeEngineState.ACKNOWLEDGED


@pytest.mark.asyncio
async def test_production_root_assignee_is_manager_not_script_author(db_session) -> None:
  seed = await _instantiate_batch_run(db_session)
  form = _build_form_service(db_session)
  editor = seed["editors"][0]
  task = seed["editor_tasks"][editor.id]
  submit = await form.submit_capture(
    actor=editor,
    task_id=task.id,
    topics=[TopicCaptureRow(title="负责人派发题")],
  )
  topic_id = submit.topics[0].topic_id
  assert topic_id is not None

  dispatch = await form.dispatch_topic(
    actor=seed["manager"],
    instance_id=seed["run"].instance.id,
    topic_id=topic_id,
    title="负责人派发题",
    script_writer_user_id=editor.id,
    source_node_instance_id=submit.node_instance_id,
  )
  assert dispatch.child_instance_id is not None

  child_instance = await db_session.get(WorkflowGraphInstance, dispatch.child_instance_id)
  assert child_instance is not None
  assert child_instance.source_id is not None
  child_root = await db_session.get(Task, child_instance.source_id)
  assert child_root is not None
  assert child_root.assignee_id == seed["manager"].id
  assert child_root.assignee_id != editor.id

  n3_tasks = list(
    await db_session.scalars(
      select(Task).where(
        Task.assignee_id == editor.id,
        Task.source_type == TaskSourceType.TEMPLATE,
      )
    )
  )
  n3_task = next(
    (t for t in n3_tasks if (t.extra_metadata or {}).get("template_node_key") == "N3_SCRIPT_WRITE"),
    None,
  )
  assert n3_task is not None
  assert n3_task.department_id is not None
  assert n3_task.department_id == child_instance.department_id
  assert child_root.department_id == child_instance.department_id


@pytest.mark.asyncio
async def test_submit_deliverable_blocked_on_production_root_shell(db_session) -> None:
  seed = await _instantiate_batch_run(db_session)
  form = _build_form_service(db_session)
  editor = seed["editors"][0]
  task = seed["editor_tasks"][editor.id]
  submit = await form.submit_capture(
    actor=editor,
    task_id=task.id,
    topics=[TopicCaptureRow(title="root-shell-block")],
  )
  topic_id = submit.topics[0].topic_id
  assert topic_id is not None

  await form.dispatch_topic(
    actor=seed["manager"],
    instance_id=seed["run"].instance.id,
    topic_id=topic_id,
    title="root-shell-block",
    script_writer_user_id=editor.id,
    source_node_instance_id=submit.node_instance_id,
  )

  child_instance = await db_session.scalar(
    select(WorkflowGraphInstance).where(
      WorkflowGraphInstance.parent_instance_id == seed["run"].instance.id
    )
  )
  assert child_instance is not None
  child_root = await db_session.get(Task, child_instance.source_id)
  assert child_root is not None

  task_service = TaskService(db_session)
  with pytest.raises(ConflictError, match="具体步骤任务"):
    await task_service.submit_task_deliverable(
      actor=seed["manager"],
      task_id=child_root.id,
      summary="不应在 ROOT 提交",
      attachment_ids=[],
    )


@pytest.mark.asyncio
async def test_manager_tracking_includes_department_projection_tasks(db_session) -> None:
  seed = await _instantiate_batch_run(db_session)
  form = _build_form_service(db_session)
  editor = seed["editors"][0]
  task = seed["editor_tasks"][editor.id]
  submit = await form.submit_capture(
    actor=editor,
    task_id=task.id,
    topics=[TopicCaptureRow(title="manager-tracking")],
  )
  topic_id = submit.topics[0].topic_id
  assert topic_id is not None

  await form.dispatch_topic(
    actor=seed["manager"],
    instance_id=seed["run"].instance.id,
    topic_id=topic_id,
    title="manager-tracking",
    script_writer_user_id=editor.id,
    source_node_instance_id=submit.node_instance_id,
  )

  n3_tasks = list(
    await db_session.scalars(
      select(Task).where(
        Task.assignee_id == editor.id,
        Task.source_type == TaskSourceType.TEMPLATE,
      )
    )
  )
  n3_task = next(
    (t for t in n3_tasks if (t.extra_metadata or {}).get("template_node_key") == "N3_SCRIPT_WRITE"),
    None,
  )
  assert n3_task is not None

  task_service = TaskService(db_session)
  tracking = await task_service.list_task_tracking(actor=seed["manager"], limit=50)
  tracking_ids = {entry.task_id for entry in tracking.items}
  assert n3_task.id in tracking_ids


@pytest.mark.asyncio
async def test_graph_root_shell_excluded_from_inbox(db_session) -> None:
  seed = await _instantiate_batch_run(db_session)
  task_service = TaskService(db_session)
  manager = seed["manager"]

  inbox = await task_service.list_task_inbox(actor=manager, limit=50)
  inbox_ids = {entry.task_id for entry in inbox.items}
  assert seed["run"].root_task.id not in inbox_ids


@pytest.mark.asyncio
async def test_finalize_topics_skips_already_forked(db_session) -> None:
  seed = await _instantiate_batch_run(db_session)
  form = _build_form_service(db_session)
  editor = seed["editors"][0]
  task = seed["editor_tasks"][editor.id]
  submit = await form.submit_capture(
    actor=editor,
    task_id=task.id,
    topics=[TopicCaptureRow(title="dedupe-topic")],
  )
  topic_id = submit.topics[0].topic_id
  assert topic_id is not None

  await form.dispatch_topic(
    actor=seed["manager"],
    instance_id=seed["run"].instance.id,
    topic_id=topic_id,
    title="dedupe-topic",
    script_writer_user_id=editor.id,
    source_node_instance_id=submit.node_instance_id,
  )

  result = await form.finalize_topics(
    actor=seed["manager"],
    instance_id=seed["run"].instance.id,
    approved_topics=[
      ApprovedTopic(topic_id=topic_id, title="dedupe-topic", script_author_id=editor.id),
    ],
  )
  assert "均已派发" in result.message or result.fork_status == "completed"
