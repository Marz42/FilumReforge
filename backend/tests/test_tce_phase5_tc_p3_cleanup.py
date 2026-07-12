"""TCE Phase 5: graph template summaries, aggregate_mode, close capture, user_facing_state."""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.enums import (
  TaskPriority,
  TaskSourceType,
  TaskStatus,
  UserRole,
  WorkflowGraphInstanceStatus,
  WorkflowGraphTemplateStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.core.exceptions import ConflictError
from app.models import (
  Task,
  User,
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateNode,
  WorkflowNodeInstance,
)
from app.services.auth_service import AuthService
from app.services.task_center_service import TaskCenterService
from app.services.task_memo_service import TaskMemoService
from app.services.task_service import TaskService
from app.services.task_user_facing_state import resolve_task_user_facing_state
from app.services.user_service import UserService
from app.services.workflow_video_form_service import WorkflowVideoFormService

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


async def _seed_batch_instance(db_session, *, aggregate_mode: str = "batch"):
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth = AuthService(db_session, settings)
  admin = await auth.bootstrap_admin(
    email="tce-p5-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-TCE-P5",
  )

  template = WorkflowGraphTemplate(
    code="topic_meeting_batch_v1",
    base_code="topic_meeting_batch_v1",
    version=1,
    name="选题会",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    config={"run_kind": "batch", "aggregate_mode": aggregate_mode},
    context_schema={},
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  db_session.add(
    WorkflowGraphTemplateNode(
      template_id=template.id,
      node_key="N1_PROPOSE",
      title="提交选题",
      sort_order=1,
      assignee_rule={},
      config={"kind": "multi_instance", "capture_schema": {"mode": "row_table", "columns": []}},
    )
  )
  db_session.add(
    WorkflowGraphTemplateNode(
      template_id=template.id,
      node_key="N2_AGGREGATE",
      title="汇总",
      sort_order=2,
      assignee_rule={},
      config={"kind": "single"},
    )
  )
  await db_session.flush()

  instance = WorkflowGraphInstance(
    template_id=template.id,
    initiator_user_id=admin.id,
    source_type="template",
    status=WorkflowGraphInstanceStatus.ACTIVE,
    run_label="第 12 周",
    context={
      "run_kind": "batch",
      "aggregate_mode": aggregate_mode,
      "manager_user_id": str(admin.id),
    },
    context_version=1,
    max_iterations=5,
  )
  db_session.add(instance)
  await db_session.flush()

  n1_template_node_id = await db_session.scalar(
    select(WorkflowGraphTemplateNode.id).where(
      WorkflowGraphTemplateNode.template_id == template.id,
      WorkflowGraphTemplateNode.node_key == "N1_PROPOSE",
    )
  )

  pending_node = WorkflowNodeInstance(
    instance_id=instance.id,
    template_node_id=n1_template_node_id,
    node_key="N1_PROPOSE",
    instance_key="user-a",
    title="提交选题",
    engine_state=WorkflowNodeEngineState.ACTIVATED,
    business_state=WorkflowNodeBusinessState.DOING,
    assignee_user_id=admin.id,
    node_instance_version=1,
  )
  db_session.add(pending_node)
  await db_session.commit()
  return settings, admin, template, instance, pending_node


@pytest.mark.asyncio
async def test_tce_b08_snapshot_uses_graph_template_summaries(db_session) -> None:
  settings, admin, template, _, _ = await _seed_batch_instance(db_session)
  task_service = TaskService(db_session, settings=settings)
  memo_service = TaskMemoService(db_session, task_service)
  center = TaskCenterService(db_session, task_service, memo_service)

  snapshot = await center.get_task_center(actor=admin)
  assert len(snapshot.template_summaries) == 1
  summary = snapshot.template_summaries[0]
  assert summary.id == template.id
  assert summary.name == "选题会"
  assert summary.category == "batch"
  assert summary.is_active is True
  assert summary.step_count == 2


@pytest.mark.asyncio
async def test_tce_b14_close_capture_blocks_submit(db_session) -> None:
  settings, admin, _, instance, pending_node = await _seed_batch_instance(db_session)

  task = Task(
    title="采集任务",
    creator_id=admin.id,
    assignee_id=admin.id,
    status=TaskStatus.DOING,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.TEMPLATE,
    extra_metadata={
      "workflow_graph_instance_id": str(instance.id),
      "workflow_node_instance_id": str(pending_node.id),
      "template_node_key": "N1_PROPOSE",
    },
  )
  db_session.add(task)
  await db_session.flush()
  pending_node.config = {**dict(pending_node.config or {}), "task_id": str(task.id)}
  await db_session.commit()

  form = WorkflowVideoFormService(db_session)
  result = await form.close_capture(actor=admin, instance_id=instance.id)
  assert result.capture_closed is True
  assert result.skipped_capture_count == 1
  await db_session.refresh(task)
  assert task.status == TaskStatus.DONE
  assert task.completed_at is not None
  assert task.extra_metadata["latest_capture_state"] == "closed_by_manager"
  assert task.extra_metadata["capture_closed_at"]

  with pytest.raises(ConflictError, match="采集已结束"):
    await form.submit_capture(
      actor=admin,
      task_id=task.id,
      topics=[{"title": "选题 A"}],
    )


@pytest.mark.asyncio
async def test_tce_b15_user_facing_state_uses_graph_business_state(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth = AuthService(db_session, settings)
  admin = await auth.bootstrap_admin(
    email="tce-b15-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-TCE-B15",
  )

  task = Task(
    title="脚本审核",
    creator_id=admin.id,
    assignee_id=admin.id,
    status=TaskStatus.REVIEW,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.TEMPLATE,
    extra_metadata={
      "workflow_graph_instance_id": str(UUID(int=1)),
      "template_node_key": "N4_SCRIPT_REVIEW",
      "ui_profile": "video_production_step",
    },
  )

  state = resolve_task_user_facing_state(
    task=task,
    status=TaskStatus.REVIEW,
    graph_business_state=WorkflowNodeBusinessState.PENDING_REVIEW,
    graph_node_key="N4_SCRIPT_REVIEW",
  )
  assert state == "awaiting_confirm"
