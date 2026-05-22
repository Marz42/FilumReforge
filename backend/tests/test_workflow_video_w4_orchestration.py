"""W4 tests: orchestration hooks for capture submit and aggregate confirm."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.enums import (
  TaskSourceType,
  TaskStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.models import Task, WorkflowNodeInstance
from app.schemas.workflow_video import ParticipantsSnapshotEntry, TopicCaptureRow
from app.services.task_service import TaskService
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_orchestration_service import WorkflowOrchestrationService
from app.services.workflow_video_form_service import WorkflowVideoFormService
from app.services.workflow_video_instantiation_service import WorkflowVideoInstantiationService
from test_workflow_video_w3_instantiation import (
  TEST_JWT_SECRET,
  _enabled_settings,
  _seed_topic_meeting_batch_template,
)


async def _instantiate_batch_run(db_session):
  seed = await _seed_topic_meeting_batch_template(db_session)
  admin = seed["admin"]
  manager = seed["manager"]
  editors = seed["editors"]
  template = seed["template"]
  department = seed["department"]

  instantiation = WorkflowVideoInstantiationService(db_session, settings=_enabled_settings())
  run = await instantiation.instantiate_graph_template(
    actor=admin,
    template_id=template.id,
    inputs={"theme": "W4 选题", "manager_user_id": str(manager.id)},
    participants_snapshot={
      "copywriters": ParticipantsSnapshotEntry(
        mode="subset",
        user_ids=[editor.id for editor in editors],
      )
    },
    department_id=department.id,
  )
  await db_session.commit()

  editor_tasks = {
    task.assignee_id: task
    for task in run.activated_tasks
  }
  return {**seed, "run": run, "editor_tasks": editor_tasks}


@pytest.mark.asyncio
async def test_w4_two_captures_keep_n2_pending(db_session) -> None:
  seed = await _instantiate_batch_run(db_session)
  graph_service = WorkflowGraphService(db_session)
  orchestration = WorkflowOrchestrationService(db_session, workflow_graph_service=graph_service)
  form = WorkflowVideoFormService(
    db_session,
    workflow_graph_service=graph_service,
    orchestration_service=orchestration,
  )

  editors = seed["editors"]
  for editor in editors[:2]:
    task = seed["editor_tasks"][editor.id]
    await form.submit_capture(
      actor=editor,
      task_id=task.id,
      topics=[TopicCaptureRow(title=f"{editor.id}-topic")],
    )

  n2 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == seed["run"].instance.id,
      WorkflowNodeInstance.node_key == "N2_AGGREGATE",
    )
  )
  assert n2 is not None
  assert n2.engine_state == WorkflowNodeEngineState.PENDING

  manager_tasks = list(
    await db_session.scalars(
      select(Task).where(
        Task.assignee_id == seed["manager"].id,
        Task.source_type == TaskSourceType.TEMPLATE,
      )
    )
  )
  n2_tasks = [
    task
    for task in manager_tasks
    if str((task.extra_metadata or {}).get("workflow_node_instance_id")) == str(n2.id)
  ]
  assert n2_tasks == []


@pytest.mark.asyncio
async def test_w4_third_capture_activates_n2_and_manager_task(db_session) -> None:
  seed = await _instantiate_batch_run(db_session)
  graph_service = WorkflowGraphService(db_session)
  task_service = TaskService(db_session, settings=Settings(jwt_secret_key=TEST_JWT_SECRET))
  orchestration = WorkflowOrchestrationService(
    db_session,
    workflow_graph_service=graph_service,
    task_service=task_service,
  )
  form = WorkflowVideoFormService(
    db_session,
    workflow_graph_service=graph_service,
    orchestration_service=orchestration,
  )

  for editor in seed["editors"]:
    task = seed["editor_tasks"][editor.id]
    await form.submit_capture(
      actor=editor,
      task_id=task.id,
      topics=[TopicCaptureRow(title=f"{editor.id}-topic")],
    )

  n2 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == seed["run"].instance.id,
      WorkflowNodeInstance.node_key == "N2_AGGREGATE",
    )
  )
  assert n2 is not None
  assert n2.engine_state == WorkflowNodeEngineState.ACTIVATED

  manager_tasks = list(
    await db_session.scalars(
      select(Task).where(
        Task.assignee_id == seed["manager"].id,
        Task.source_type == TaskSourceType.TEMPLATE,
      )
    )
  )
  manager_task = next(
    (
      task
      for task in manager_tasks
      if str((task.extra_metadata or {}).get("workflow_node_instance_id")) == str(n2.id)
    ),
    None,
  )
  assert manager_task is not None
  assert manager_task.status in {TaskStatus.DOING, TaskStatus.TODO}


@pytest.mark.asyncio
async def test_w4_upstream_join_requires_all_multi_instance_peers(db_session) -> None:
  from datetime import UTC, datetime

  from app.models import WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode

  seed = await _instantiate_batch_run(db_session)
  graph_service = WorkflowGraphService(db_session)

  n1_nodes = list(
    await db_session.scalars(
      select(WorkflowNodeInstance).where(
        WorkflowNodeInstance.instance_id == seed["run"].instance.id,
        WorkflowNodeInstance.node_key == "N1_PROPOSE",
      )
    )
  )
  n2 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == seed["run"].instance.id,
      WorkflowNodeInstance.node_key == "N2_AGGREGATE",
    )
  )
  assert n2 is not None and n2.template_node_id is not None

  n2_template_node = await db_session.get(WorkflowGraphTemplateNode, n2.template_node_id)
  assert n2_template_node is not None
  incoming_edges = list(
    await db_session.scalars(
      select(WorkflowGraphTemplateEdge).where(
        WorkflowGraphTemplateEdge.to_node_id == n2.template_node_id,
        WorkflowGraphTemplateEdge.is_reject_path.is_(False),
      )
    )
  )

  now = datetime.now(UTC)
  n1_nodes[0].engine_state = WorkflowNodeEngineState.COMPLETED
  n1_nodes[0].business_state = WorkflowNodeBusinessState.PENDING_REVIEW
  n1_nodes[0].completed_at = now
  await db_session.flush()

  assert await graph_service._upstream_join_satisfied(
    instance_id=seed["run"].instance.id,
    downstream_template_node=n2_template_node,
    incoming_edges=incoming_edges,
  ) is False

  for node in n1_nodes[1:]:
    node.engine_state = WorkflowNodeEngineState.COMPLETED
    node.completed_at = now
  await db_session.flush()

  assert await graph_service._upstream_join_satisfied(
    instance_id=seed["run"].instance.id,
    downstream_template_node=n2_template_node,
    incoming_edges=incoming_edges,
  ) is True
