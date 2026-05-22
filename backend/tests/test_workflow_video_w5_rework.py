"""W5 tests: targeted capture rejection and production deep reject."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.enums import (
  TaskSourceType,
  TaskStatus,
  WorkflowGraphTemplateStatus,
  WorkflowNodeEngineState,
)
from app.core.exceptions import ConflictError
from app.models import Task, WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode, WorkflowNodeInstance, WorkflowRunEvent
from app.schemas.workflow_video import ParticipantsSnapshotEntry, RejectedCaptureItem, TopicCaptureRow
from app.services.task_service import TaskService
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_orchestration_service import WorkflowOrchestrationService
from app.services.workflow_video_form_service import WorkflowVideoFormService
from app.services.workflow_video_instantiation_service import WorkflowVideoInstantiationService
from app.services.workflow_video_rework_service import WorkflowVideoReworkService
from test_workflow_video_w3_instantiation import (
  TEST_JWT_SECRET,
  _enabled_settings,
  _seed_topic_meeting_batch_template,
)
from test_workflow_video_w4_orchestration import _instantiate_batch_run


@pytest.mark.asyncio
async def test_w5_reject_topic_reopens_only_submitter(db_session) -> None:
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

  editors = seed["editors"]
  topic_ids: dict = {}
  for editor in editors:
    task = seed["editor_tasks"][editor.id]
    result = await form.submit_capture(
      actor=editor,
      task_id=task.id,
      topics=[TopicCaptureRow(title=f"{editor.id}-topic")],
    )
    topic_ids[editor.id] = result.topics[0].topic_id

  editor_a = editors[0]
  editor_b = editors[1]
  rejected_topic_id = topic_ids[editor_a.id]

  reject_result = await rework.apply_capture_rejections(
    actor=seed["manager"],
    instance_id=seed["run"].instance.id,
    rejections=[RejectedCaptureItem(topic_id=rejected_topic_id, reason="选题方向需调整")],
  )
  assert reject_result.reopened_count == 1
  assert reject_result.reopened_instance_keys == [str(editor_a.id)]

  n1_nodes = await rework._list_latest_propose_nodes(
    instance_id=seed["run"].instance.id,
    source_node_key="N1_PROPOSE",
  )
  by_key = {node.instance_key: node for node in n1_nodes}
  assert by_key[str(editor_a.id)].engine_state == WorkflowNodeEngineState.ACTIVATED
  assert by_key[str(editor_b.id)].engine_state == WorkflowNodeEngineState.COMPLETED
  assert by_key[str(editors[2].id)].engine_state == WorkflowNodeEngineState.COMPLETED

  task_a = seed["editor_tasks"][editor_a.id]
  task_b = seed["editor_tasks"][editor_b.id]
  await db_session.refresh(task_a)
  await db_session.refresh(task_b)
  assert task_a.status == TaskStatus.DOING
  assert task_b.status == TaskStatus.REVIEW

  n2 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == seed["run"].instance.id,
      WorkflowNodeInstance.node_key == "N2_AGGREGATE",
    )
  )
  assert n2 is not None
  assert n2.engine_state == WorkflowNodeEngineState.PENDING

  events = list(
    await db_session.scalars(
      select(WorkflowRunEvent).where(WorkflowRunEvent.instance_id == seed["run"].instance.id)
    )
  )
  assert any(event.event_type == "capture_rejected" for event in events)


@pytest.mark.asyncio
async def test_w5_reject_requires_reason() -> None:
  from pydantic import ValidationError
  from uuid import uuid4

  with pytest.raises(ValidationError):
    RejectedCaptureItem(topic_id=uuid4(), reason="")


@pytest.mark.asyncio
async def test_w5_production_deep_reject_via_acceptance_spec(db_session) -> None:
  from app.services.auth_service import AuthService
  from app.services.user_service import UserService
  from app.core.enums import UserRole

  auth = AuthService(db_session, Settings(jwt_secret_key=TEST_JWT_SECRET))
  admin = await auth.bootstrap_admin(
    email="w5-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-W5-ROOT",
  )
  author = await UserService(db_session).create_user(
    actor=admin,
    email="w5-author@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  reviewer = await UserService(db_session).create_user(
    actor=admin,
    email="w5-reviewer@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  template = WorkflowGraphTemplate(
    code="production_reject_test_v1",
    base_code="production_reject_test_v1",
    version=1,
    name="制作打回测试",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_write = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="N3_SCRIPT_WRITE",
    title="写脚本",
    sort_order=1,
  )
  node_review = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="N4_SCRIPT_REVIEW",
    title="审脚本",
    sort_order=2,
    assignee_rule={"type": "user_ids", "user_ids": [str(reviewer.id)]},
    config={"acceptance_spec": {"reject_to": {"node_key": "N3_SCRIPT_WRITE"}}},
  )
  db_session.add_all([node_write, node_review])
  await db_session.flush()
  db_session.add(
    WorkflowGraphTemplateEdge(
      template_id=template.id,
      from_node_id=node_write.id,
      to_node_id=node_review.id,
    )
  )
  await db_session.flush()

  graph_service = WorkflowGraphService(db_session)
  result = await graph_service.create_multi_node_instance(
    template_id=template.id,
    initiator_id=admin.id,
    context={"script_author_id": str(author.id)},
  )
  ni_write = next(ni for ni in result.node_instances if ni.node_key == "N3_SCRIPT_WRITE")
  ni_review = next(ni for ni in result.node_instances if ni.node_key == "N4_SCRIPT_REVIEW")
  ni_write.assignee_user_id = author.id
  ni_review.assignee_user_id = reviewer.id
  await graph_service.complete_node_instance(node_instance_id=ni_write.id, actor_id=author.id)
  await db_session.commit()
  await db_session.refresh(ni_review)
  assert ni_review.engine_state == WorkflowNodeEngineState.ACTIVATED

  task_service = TaskService(db_session, settings=Settings(jwt_secret_key=TEST_JWT_SECRET))
  orchestration = WorkflowOrchestrationService(db_session, workflow_graph_service=graph_service, task_service=task_service)
  review_task = await orchestration._create_projection_task(
    actor=admin,
    template=template,
    instance=result.instance,
    node_instance=ni_review,
  )
  ni_review.config = {**dict(ni_review.config or {}), "task_id": str(review_task.id)}
  await db_session.commit()

  rework = WorkflowVideoReworkService(db_session, workflow_graph_service=graph_service, orchestration_service=orchestration)
  reject_result = await rework.reject_production_step(
    actor=reviewer,
    task_id=review_task.id,
    reason="脚本结构需重写",
  )
  assert reject_result.target_node_key == "N3_SCRIPT_WRITE"
  assert reject_result.iteration >= 2
