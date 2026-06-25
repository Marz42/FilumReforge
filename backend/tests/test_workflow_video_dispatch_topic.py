"""Tests for incremental dispatch_topic (TC-P1)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.enums import TaskStatus, WorkflowNodeEngineState
from app.core.exceptions import ConflictError
from app.models import WorkflowGraphInstance, WorkflowNodeInstance
from app.schemas.workflow_video import ParticipantsSnapshotEntry, TopicCaptureRow
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_orchestration_service import WorkflowOrchestrationService
from app.services.workflow_video_fork_service import WorkflowVideoForkService
from app.services.workflow_video_form_service import WorkflowVideoFormService
from app.services.workflow_video_instantiation_service import WorkflowVideoInstantiationService
from test_workflow_video_w3_instantiation import _enabled_settings, _seed_topic_meeting_batch_template
from test_workflow_video_wfk_fork import _seed_production_template


def _build_form_service(db_session) -> WorkflowVideoFormService:
  settings = _enabled_settings()
  graph_service = WorkflowGraphService(db_session)
  orchestration = WorkflowOrchestrationService(db_session, workflow_graph_service=graph_service)
  instantiation = WorkflowVideoInstantiationService(db_session, settings=settings)
  fork = WorkflowVideoForkService(
    db_session,
    instantiation_service=instantiation,
    orchestration_service=orchestration,
  )
  return WorkflowVideoFormService(
    db_session,
    workflow_graph_service=graph_service,
    orchestration_service=orchestration,
    fork_service=fork,
  )


async def _instantiate_batch_run(db_session):
  seed = await _seed_topic_meeting_batch_template(db_session)
  await _seed_production_template(
    db_session,
    admin_id=seed["admin"].id,
    department_id=seed["department"].id,
  )
  admin = seed["admin"]
  manager = seed["manager"]
  editors = seed["editors"]
  template = seed["template"]
  department = seed["department"]

  instantiation = WorkflowVideoInstantiationService(db_session, settings=_enabled_settings())
  run = await instantiation.instantiate_graph_template(
    actor=admin,
    template_id=template.id,
    inputs={"theme": "dispatch 选题", "manager_user_id": str(manager.id)},
    participants_snapshot={
      "copywriters": ParticipantsSnapshotEntry(
        mode="subset",
        user_ids=[editor.id for editor in editors],
      )
    },
    department_id=department.id,
  )
  await db_session.commit()

  editor_tasks = {task.assignee_id: task for task in run.activated_tasks}
  return {**seed, "run": run, "editor_tasks": editor_tasks}


@pytest.mark.asyncio
async def test_dispatch_topic_after_partial_capture(db_session) -> None:
  seed = await _instantiate_batch_run(db_session)
  form = _build_form_service(db_session)

  editor = seed["editors"][0]
  task = seed["editor_tasks"][editor.id]
  submit = await form.submit_capture(
    actor=editor,
    task_id=task.id,
    topics=[TopicCaptureRow(title=f"{editor.id}-topic")],
  )
  topic_id = submit.topics[0].topic_id
  assert topic_id is not None

  n2 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == seed["run"].instance.id,
      WorkflowNodeInstance.node_key == "N2_AGGREGATE",
    )
  )
  assert n2 is not None
  assert n2.engine_state == WorkflowNodeEngineState.PENDING

  node_instance_id = submit.node_instance_id
  dispatch = await form.dispatch_topic(
    actor=seed["manager"],
    instance_id=seed["run"].instance.id,
    topic_id=topic_id,
    title=submit.topics[0].title,
    script_writer_user_id=seed["editors"][1].id,
    source_node_instance_id=node_instance_id,
  )
  assert dispatch.child_instance_id is not None
  assert dispatch.fork_status in {"completed", "partial"}

  refreshed = await db_session.get(WorkflowGraphInstance, seed["run"].instance.id)
  assert refreshed is not None
  context = refreshed.context if isinstance(refreshed.context, dict) else {}
  forked = context.get("forked_topics")
  assert isinstance(forked, dict)
  assert str(topic_id) in forked

  n2_after = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == seed["run"].instance.id,
      WorkflowNodeInstance.node_key == "N2_AGGREGATE",
    )
  )
  assert n2_after is not None
  assert n2_after.engine_state == WorkflowNodeEngineState.PENDING


@pytest.mark.asyncio
async def test_dispatch_topic_rejects_duplicate(db_session) -> None:
  seed = await _instantiate_batch_run(db_session)
  form = _build_form_service(db_session)

  editor = seed["editors"][0]
  task = seed["editor_tasks"][editor.id]
  submit = await form.submit_capture(
    actor=editor,
    task_id=task.id,
    topics=[TopicCaptureRow(title="dup-topic")],
  )
  topic_id = submit.topics[0].topic_id
  assert topic_id is not None

  await form.dispatch_topic(
    actor=seed["manager"],
    instance_id=seed["run"].instance.id,
    topic_id=topic_id,
    title="dup-topic",
    script_writer_user_id=seed["editors"][1].id,
    source_node_instance_id=submit.node_instance_id,
  )

  with pytest.raises(ConflictError):
    await form.dispatch_topic(
      actor=seed["manager"],
      instance_id=seed["run"].instance.id,
      topic_id=topic_id,
      title="dup-topic",
      script_writer_user_id=seed["editors"][1].id,
      source_node_instance_id=submit.node_instance_id,
    )


@pytest.mark.asyncio
async def test_n1_capture_marks_task_done(db_session) -> None:
  seed = await _instantiate_batch_run(db_session)
  form = _build_form_service(db_session)

  editor = seed["editors"][0]
  task = seed["editor_tasks"][editor.id]
  await form.submit_capture(
    actor=editor,
    task_id=task.id,
    topics=[TopicCaptureRow(title="done-topic")],
  )
  await db_session.refresh(task)
  assert task.status == TaskStatus.DONE
  assert task.completed_at is not None
