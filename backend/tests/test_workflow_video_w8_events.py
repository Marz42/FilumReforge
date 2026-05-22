"""W8 tests: persisted workflow run event log."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import WorkflowRunEvent
from app.services.workflow_run_event_service import WorkflowRunEventService
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_orchestration_service import WorkflowOrchestrationService
from app.services.workflow_video_rework_service import WorkflowVideoReworkService
from app.schemas.workflow_video import RejectedCaptureItem, TopicCaptureRow
from app.services.workflow_video_form_service import WorkflowVideoFormService
from test_workflow_video_w4_orchestration import _instantiate_batch_run


@pytest.mark.asyncio
async def test_w8_capture_reject_persists_event(db_session) -> None:
  seed = await _instantiate_batch_run(db_session)
  graph_service = WorkflowGraphService(db_session)
  orchestration = WorkflowOrchestrationService(db_session, workflow_graph_service=graph_service)
  rework = WorkflowVideoReworkService(db_session, workflow_graph_service=graph_service, orchestration_service=orchestration)
  form = WorkflowVideoFormService(
    db_session,
    workflow_graph_service=graph_service,
    orchestration_service=orchestration,
    rework_service=rework,
  )

  editor = seed["editors"][0]
  submit = await form.submit_capture(
    actor=editor,
    task_id=seed["editor_tasks"][editor.id].id,
    topics=[TopicCaptureRow(title="W8 选题")],
  )
  topic_id = submit.topics[0].topic_id

  await rework.apply_capture_rejections(
    actor=seed["manager"],
    instance_id=seed["run"].instance.id,
    rejections=[RejectedCaptureItem(topic_id=topic_id, reason="需补充理由")],
  )

  events = list(
    await db_session.scalars(
      select(WorkflowRunEvent).where(WorkflowRunEvent.instance_id == seed["run"].instance.id)
    )
  )
  assert any(event.event_type == "capture_rejected" for event in events)
  rejected = next(event for event in events if event.event_type == "capture_rejected")
  assert rejected.payload.get("reason") == "需补充理由"


@pytest.mark.asyncio
async def test_w8_list_events_paginated(db_session) -> None:
  seed = await _instantiate_batch_run(db_session)
  service = WorkflowRunEventService(db_session)
  for index in range(3):
    await service.append(
      instance_id=seed["run"].instance.id,
      event_type="test_event",
      actor_user_id=seed["manager"].id,
      payload={"index": index},
    )
  await db_session.commit()

  page = await service.list_for_instance(
    instance_id=seed["run"].instance.id,
    limit=2,
    offset=0,
  )
  assert page.total >= 3
  assert len(page.items) == 2
  assert page.items[0].event_type == "test_event"
