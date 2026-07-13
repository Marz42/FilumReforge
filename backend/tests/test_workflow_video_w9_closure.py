"""W9 tests: outbox activation notifications and graph template admin API."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.enums import WorkflowOutboxEventStatus
from app.models import WorkflowGraphTemplate, WorkflowOutboxEvent
from app.schemas.workflow_graph import WorkflowGraphTemplateUpdateRequest
from app.schemas.workflow_video import ParticipantsSnapshotEntry, TopicCaptureRow
from app.services.workflow_graph_template_admin_service import WorkflowGraphTemplateAdminService
from app.services.workflow_video_template_seed_service import WorkflowVideoTemplateSeedService
from app.services.workflow_video_form_service import WorkflowVideoFormService
from app.services.workflow_video_instantiation_service import WorkflowVideoInstantiationService
from test_workflow_video_w3_instantiation import TEST_JWT_SECRET, _enabled_settings, _seed_topic_meeting_batch_template
from test_workflow_video_w4_orchestration import _instantiate_batch_run
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_orchestration_service import WorkflowOrchestrationService


@pytest.mark.asyncio
async def test_w9_instantiate_enqueues_node_activated_outbox(db_session) -> None:
  seed = await _seed_topic_meeting_batch_template(db_session)
  service = WorkflowVideoInstantiationService(db_session, settings=_enabled_settings())
  await service.instantiate_graph_template(
    actor=seed["admin"],
    template_id=seed["template"].id,
    inputs={"theme": "W9", "manager_user_id": str(seed["manager"].id)},
    participants_snapshot={
      "copywriters": ParticipantsSnapshotEntry(
        mode="subset",
        user_ids=[editor.id for editor in seed["editors"]],
      )
    },
    department_id=seed["department"].id,
  )
  await db_session.commit()

  events = list(
    await db_session.scalars(
      select(WorkflowOutboxEvent).where(
        WorkflowOutboxEvent.event_type == "workflow_node_activated",
        WorkflowOutboxEvent.status == WorkflowOutboxEventStatus.PENDING,
      )
    )
  )
  assert len(events) >= len(seed["editors"])


@pytest.mark.asyncio
async def test_w9_orchestration_downstream_enqueues_outbox(db_session) -> None:
  seed = await _instantiate_batch_run(db_session)
  graph_service = WorkflowGraphService(db_session)
  orchestration = WorkflowOrchestrationService(db_session, workflow_graph_service=graph_service)
  form = WorkflowVideoFormService(
    db_session,
    workflow_graph_service=graph_service,
    orchestration_service=orchestration,
  )
  run = seed["run"]

  for editor in seed["editors"]:
    task = seed["editor_tasks"][editor.id]
    await form.submit_capture(actor=editor, task_id=task.id, topics=[TopicCaptureRow(title=f"{editor.id}-topic")])
  await db_session.commit()

  events = list(
    await db_session.scalars(
      select(WorkflowOutboxEvent).where(
        WorkflowOutboxEvent.instance_id == run.instance.id,
        WorkflowOutboxEvent.event_type == "workflow_node_activated",
      )
    )
  )
  assert any(
    event.payload.get("node_key") == "N2_AGGREGATE"
    for event in events
    if isinstance(event.payload, dict)
  )


@pytest.mark.asyncio
async def test_w9_graph_template_patch_config(db_session) -> None:
  from app.services.auth_service import AuthService
  from app.services.department_service import DepartmentService
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET, workflow_graph_template_engine_enabled=True)
  auth = AuthService(db_session, settings)
  admin = await auth.bootstrap_admin(
    email="w9-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-W9",
  )
  dept_service = DepartmentService(db_session)
  root = await dept_service.create_department(actor=admin, name="根", code="root-w9", parent_id=None)
  copy = await dept_service.create_department(
    actor=admin,
    name="文案",
    code="video-copywriting",
    parent_id=root.id,
  )
  await WorkflowVideoTemplateSeedService(db_session).seed_templates(
    actor=admin,
    departments={"video-copywriting": copy, "video-voice": copy, "video-post": copy},
  )
  await db_session.commit()

  template = await db_session.scalar(
    select(WorkflowGraphTemplate).where(WorkflowGraphTemplate.code == "topic_meeting_batch_v1")
  )
  assert template is not None

  admin_service = WorkflowGraphTemplateAdminService(db_session)
  draft = await admin_service.fork_template_version(actor=admin, template_id=template.id)
  detail = await admin_service.update_template(
    actor=admin,
    template_id=draft.id,
    payload=WorkflowGraphTemplateUpdateRequest(description="W9 维护说明"),
  )
  assert detail.description == "W9 维护说明"
  assert len(detail.nodes) >= 2
