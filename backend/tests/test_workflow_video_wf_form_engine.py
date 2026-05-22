"""WF tests: form engine capture, submissions list, finalize topics."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.enums import (
  TaskSourceType,
  TaskStatus,
  UserRole,
  WorkflowGraphInstanceStatus,
  WorkflowGraphTemplateStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.core.exceptions import ConflictError
from app.models import Task, WorkflowGraphInstance, WorkflowGraphTemplate, WorkflowGraphTemplateNode, WorkflowNodeInstance
from app.schemas.workflow_video import ApprovedTopic, TopicCaptureRow
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.profile_service import ProfileService
from app.services.user_service import UserService
from app.services.workflow_video_form_service import WorkflowVideoFormService

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"
CAPTURE_SCHEMA = {
  "mode": "row_table",
  "min_rows": 1,
  "max_rows": 5,
  "columns": [
    {"key": "title", "label": "标题", "type": "text", "required": True},
    {"key": "content", "label": "内容", "type": "textarea"},
  ],
  "completion_policy": "on_capture_submitted",
}


async def _seed_capture_flow(db_session):
  auth = AuthService(db_session, Settings(jwt_secret_key=TEST_JWT_SECRET))
  admin = await auth.bootstrap_admin(
    email="wf-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-WF-ROOT",
  )
  user_service = UserService(db_session)
  dept_service = DepartmentService(db_session)
  profile_service = ProfileService(db_session)

  manager = await user_service.create_user(
    actor=admin,
    email="wf-manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  editor = await user_service.create_user(
    actor=admin,
    email="wf-editor@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await dept_service.create_department(
    actor=admin,
    name="文案部",
    code="wf-copy",
    manager_id=manager.id,
  )
  for user, no, name in ((manager, "EMP-WF-M", "负责人"), (editor, "EMP-WF-E", "编辑")):
    await profile_service.create_profile(
      actor=admin,
      user_id=user.id,
      employee_no=no,
      real_name=name,
      department_id=department.id,
      custom_fields={},
    )

  template = WorkflowGraphTemplate(
    code="topic_meeting_batch_v1",
    base_code="topic_meeting_batch_v1",
    version=1,
    name="选题会",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    config={"aggregate_node_key": "N2_AGGREGATE"},
    context_schema={},
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  tpl_node_propose = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="N1_PROPOSE",
    title="提交选题",
    config={"capture_schema": CAPTURE_SCHEMA},
    sort_order=1,
  )
  tpl_node_agg = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="N2_AGGREGATE",
    title="汇总派发",
    config={"aggregate_schema": {"source_node_key": "N1_PROPOSE"}},
    sort_order=2,
  )
  db_session.add_all([tpl_node_propose, tpl_node_agg])
  await db_session.flush()

  instance = WorkflowGraphInstance(
    template_id=template.id,
    initiator_user_id=manager.id,
    department_id=department.id,
    status=WorkflowGraphInstanceStatus.ACTIVE,
    context={"run_kind": "batch"},
    context_version=1,
    max_iterations=5,
  )
  db_session.add(instance)
  await db_session.flush()

  propose_node = WorkflowNodeInstance(
    instance_id=instance.id,
    template_node_id=tpl_node_propose.id,
    node_key="N1_PROPOSE",
    instance_key=str(editor.id),
    title="提交选题",
    assignee_user_id=editor.id,
    engine_state=WorkflowNodeEngineState.ACTIVATED,
    business_state=WorkflowNodeBusinessState.DOING,
    config={"capture_schema": CAPTURE_SCHEMA},
  )
  aggregate_node = WorkflowNodeInstance(
    instance_id=instance.id,
    template_node_id=tpl_node_agg.id,
    node_key="N2_AGGREGATE",
    instance_key="singleton",
    title="汇总派发",
    assignee_user_id=manager.id,
    engine_state=WorkflowNodeEngineState.PENDING,
    business_state=WorkflowNodeBusinessState.ASSIGNED,
    config={},
  )
  db_session.add_all([propose_node, aggregate_node])
  await db_session.flush()

  task = Task(
    title="选题会 / 提交选题",
    creator_id=manager.id,
    assignee_id=editor.id,
    department_id=department.id,
    status=TaskStatus.DOING,
    source_type=TaskSourceType.TEMPLATE,
    extra_metadata={
      "workflow_graph_instance_id": str(instance.id),
      "workflow_node_instance_id": str(propose_node.id),
      "template_node_key": "N1_PROPOSE",
    },
  )
  db_session.add(task)
  await db_session.flush()

  return {
    "admin": admin,
    "manager": manager,
    "editor": editor,
    "instance": instance,
    "propose_node": propose_node,
    "aggregate_node": aggregate_node,
    "task": task,
  }


@pytest.mark.asyncio
async def test_wf_submit_capture_persists_topics_and_marks_review(db_session) -> None:
  seed = await _seed_capture_flow(db_session)
  service = WorkflowVideoFormService(db_session)

  result = await service.submit_capture(
    actor=seed["editor"],
    task_id=seed["task"].id,
    topics=[TopicCaptureRow(title="选题A", content="说明A")],
  )
  assert result.topic_count == 1
  assert result.topics[0].topic_id is not None

  await db_session.refresh(seed["task"])
  await db_session.refresh(seed["propose_node"])
  assert seed["task"].status == TaskStatus.REVIEW
  assert seed["propose_node"].engine_state == WorkflowNodeEngineState.COMPLETED


@pytest.mark.asyncio
async def test_wf_submit_capture_enforces_min_rows(db_session) -> None:
  seed = await _seed_capture_flow(db_session)
  service = WorkflowVideoFormService(db_session)
  with pytest.raises(ConflictError, match="至少需要"):
    await service.submit_capture(
      actor=seed["editor"],
      task_id=seed["task"].id,
      topics=[],
    )


@pytest.mark.asyncio
async def test_wf_submit_capture_rejects_duplicate_submit(db_session) -> None:
  seed = await _seed_capture_flow(db_session)
  service = WorkflowVideoFormService(db_session)
  await service.submit_capture(
    actor=seed["editor"],
    task_id=seed["task"].id,
    topics=[TopicCaptureRow(title="选题A")],
  )
  with pytest.raises(ConflictError, match="已提交"):
    await service.submit_capture(
      actor=seed["editor"],
      task_id=seed["task"].id,
      topics=[TopicCaptureRow(title="选题B")],
    )


@pytest.mark.asyncio
async def test_wf_list_instance_submissions_returns_all_rows(db_session) -> None:
  seed = await _seed_capture_flow(db_session)
  service = WorkflowVideoFormService(db_session)
  await service.submit_capture(
    actor=seed["editor"],
    task_id=seed["task"].id,
    topics=[TopicCaptureRow(title="选题A"), TopicCaptureRow(title="选题B", content="x")],
  )

  listing = await service.list_instance_submissions(
    instance_id=seed["instance"].id,
    node_key="N1_PROPOSE",
  )
  assert listing.node_key == "N1_PROPOSE"
  assert len(listing.submissions) == 1
  assert len(listing.submissions[0].topics) == 2


@pytest.mark.asyncio
async def _seed_production_template_for_wf(db_session, *, admin_id):
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode
  from app.core.enums import WorkflowGraphTemplateStatus

  template = WorkflowGraphTemplate(
    code="video_production_per_topic_v1",
    base_code="video_production_per_topic_v1",
    version=1,
    name="单题制作",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    config={"run_kind": "production"},
    created_by=admin_id,
  )
  db_session.add(template)
  await db_session.flush()
  db_session.add(
    WorkflowGraphTemplateNode(
      template_id=template.id,
      node_key="N3_SCRIPT_WRITE",
      title="写脚本",
      sort_order=1,
      assignee_rule={"type": "context_var", "var": "script_author_id"},
    )
  )
  await db_session.flush()


@pytest.mark.asyncio
async def test_wf_finalize_topics_writes_context_and_completes_aggregate(db_session) -> None:
  from app.core.config import Settings
  from app.services.workflow_video_fork_service import WorkflowVideoForkService
  from app.services.workflow_video_instantiation_service import WorkflowVideoInstantiationService

  seed = await _seed_capture_flow(db_session)
  await _seed_production_template_for_wf(db_session, admin_id=seed["admin"].id)
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET, workflow_graph_template_engine_enabled=True)
  fork = WorkflowVideoForkService(
    db_session,
    instantiation_service=WorkflowVideoInstantiationService(db_session, settings=settings),
  )
  service = WorkflowVideoFormService(db_session, fork_service=fork)
  submit = await service.submit_capture(
    actor=seed["editor"],
    task_id=seed["task"].id,
    topics=[TopicCaptureRow(title="选题A")],
  )
  topic_id = submit.topics[0].topic_id
  assert topic_id is not None

  result = await service.finalize_topics(
    actor=seed["manager"],
    instance_id=seed["instance"].id,
    approved_topics=[
      ApprovedTopic(
        topic_id=topic_id,
        title="选题A",
        script_author_id=seed["editor"].id,
      )
    ],
  )
  assert result.approved_count == 1
  assert result.fork_status == "completed"
  assert result.fork_deferred is False
  assert len(result.child_instance_ids) == 1

  await db_session.refresh(seed["instance"])
  await db_session.refresh(seed["aggregate_node"])
  context = seed["instance"].context
  assert len(context.get("approved_topics", [])) == 1
  assert context.get("fork_status") == "completed"
  assert seed["aggregate_node"].engine_state == WorkflowNodeEngineState.COMPLETED
