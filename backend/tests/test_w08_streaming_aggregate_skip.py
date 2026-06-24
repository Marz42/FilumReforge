"""W-08: streaming mode N2 aggregate engine skip tests."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.enums import TaskSourceType, WorkflowNodeEngineState
from app.models import Task, WorkflowGraphInstance, WorkflowNodeInstance
from app.schemas.workflow_video import ParticipantsSnapshotEntry, TopicCaptureRow
from app.services.task_service import TaskService
from app.core.config import Settings
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_orchestration_service import WorkflowOrchestrationService
from app.services.workflow_video_form_service import WorkflowVideoFormService
from app.services.workflow_video_instantiation_service import WorkflowVideoInstantiationService
from test_workflow_video_w3_instantiation import (
  TEST_JWT_SECRET,
  _enabled_settings,
  _seed_topic_meeting_batch_template,
)


async def _instantiate_streaming_run(db_session):
  seed = await _seed_topic_meeting_batch_template(db_session)
  template = seed["template"]
  template.config = {
    **dict(template.config or {}),
    "aggregate_mode": "streaming",
  }
  await db_session.flush()

  instantiation = WorkflowVideoInstantiationService(db_session, settings=_enabled_settings())
  run = await instantiation.instantiate_graph_template(
    actor=seed["admin"],
    template_id=template.id,
    inputs={"theme": "W08 streaming", "manager_user_id": str(seed["manager"].id)},
    participants_snapshot={
      "copywriters": ParticipantsSnapshotEntry(
        mode="subset",
        user_ids=[editor.id for editor in seed["editors"]],
      )
    },
    department_id=seed["department"].id,
  )
  await db_session.commit()
  editor_tasks = {task.assignee_id: task for task in run.activated_tasks}
  return {**seed, "run": run, "editor_tasks": editor_tasks}


@pytest.mark.asyncio
async def test_w08_streaming_n2_engine_skipped_without_shell_task(db_session) -> None:
  seed = await _instantiate_streaming_run(db_session)
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
    await form.submit_capture(
      actor=editor,
      task_id=seed["editor_tasks"][editor.id].id,
      topics=[TopicCaptureRow(title=f"{editor.id}-topic")],
    )

  n2 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == seed["run"].instance.id,
      WorkflowNodeInstance.node_key == "N2_AGGREGATE",
    )
  )
  assert n2 is not None
  assert n2.engine_state == WorkflowNodeEngineState.COMPLETED
  assert (n2.config or {}).get("engine_skipped") is True
  assert (n2.config or {}).get("skip_reason") == "streaming_aggregate"

  n2_tasks = list(
    await db_session.scalars(
      select(Task).where(
        Task.source_type == TaskSourceType.TEMPLATE,
      )
    )
  )
  n2_tasks = [
    task
    for task in n2_tasks
    if str((task.extra_metadata or {}).get("workflow_node_instance_id")) == str(n2.id)
  ]
  assert n2_tasks == []
