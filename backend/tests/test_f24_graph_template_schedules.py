"""F-24: graph template schedule tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.enums import UserRole, WorkflowGraphInstanceStatus, WorkflowGraphTemplateStatus
from app.core.exceptions import ConflictError
from app.models import (
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateEdge,
  WorkflowGraphTemplateNode,
  WorkflowGraphTemplateSchedule,
  WorkflowCommandReceipt,
)
from app.schemas.workflow_graph_schedule import GraphTemplateScheduleCreateRequest
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.profile_service import ProfileService
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.services.workflow_graph_template_schedule_service import WorkflowGraphTemplateScheduleService
from app.services.workflow_video_instantiation_service import WorkflowVideoInstantiationService
from app.services.workflow_command_executor import WorkflowCommandExecutor
from test_workflow_video_w3_instantiation import CAPTURE_SCHEMA, LAUNCH_SCHEMA, TEST_JWT_SECRET, _enabled_settings

AGGREGATE_SCHEMA = {
  "mode": "submission_matrix",
  "source_node_key": "N1_PROPOSE",
  "row_id_field": "topic_id",
  "row_actions": ["approve", "reject"],
  "on_confirm": {"action": "advance_only"},
}


async def _seed_schedulable_template(db_session):
  auth = AuthService(db_session, Settings(jwt_secret_key=TEST_JWT_SECRET))
  admin = await auth.bootstrap_admin(
    email="f24-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-F24",
  )
  user_service = UserService(db_session)
  dept_service = DepartmentService(db_session)
  profile_service = ProfileService(db_session)

  manager = await user_service.create_user(
    actor=admin,
    email="f24-manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  editor = await user_service.create_user(
    actor=admin,
    email="f24-editor@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await dept_service.create_department(
    actor=admin,
    name="文案部",
    code="f24-copy",
    manager_id=manager.id,
  )
  for user, employee_no, name in (
    (manager, "EMP-F24-M", "经理"),
    (editor, "EMP-F24-E", "编辑"),
  ):
    await profile_service.create_profile(
      actor=admin,
      user_id=user.id,
      employee_no=employee_no,
      real_name=name,
      department_id=department.id,
      custom_fields={},
    )

  template = WorkflowGraphTemplate(
    code="f24_capture_v1",
    base_code="f24_capture_v1",
    version=1,
    name="周期采集",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    config={
      "run_kind": "batch",
      "aggregate_mode": "batch",
      "schedulable": True,
      "launch_schema": {
        "fields": [
          {"key": "manager_user_id", "label": "负责人", "type": "user", "required": True},
        ],
      },
      "root_assignee_var": "manager_user_id",
      "participant_policies": {
        "copywriters": {"type": "department_members", "scope": "instance_department"},
      },
    },
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_n1 = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="N1_PROPOSE",
    title="提交",
    sort_order=1,
    config={
      "kind": "multi_instance",
      "expand_from": "copywriters",
      "capture_schema": CAPTURE_SCHEMA,
    },
  )
  node_n2 = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="N2_AGGREGATE",
    title="汇总",
    sort_order=2,
    assignee_rule={"type": "context_var", "var": "manager_user_id"},
    config={"kind": "single", "aggregate_schema": AGGREGATE_SCHEMA},
  )
  db_session.add_all([node_n1, node_n2])
  await db_session.flush()
  db_session.add(
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_n1.id, to_node_id=node_n2.id)
  )
  await db_session.flush()
  return {
    "admin": admin,
    "manager": manager,
    "editor": editor,
    "department": department,
    "template": template,
  }


def _schedule_service(db_session) -> WorkflowGraphTemplateScheduleService:
  settings = _enabled_settings()
  task_service = TaskService(
    db_session,
    settings=Settings(jwt_secret_key=TEST_JWT_SECRET, workflow_graph_engine_enabled=True),
  )
  instantiation = WorkflowVideoInstantiationService(db_session, task_service=task_service, settings=settings)
  return WorkflowGraphTemplateScheduleService(db_session, instantiation_service=instantiation)


@pytest.mark.asyncio
async def test_f24_create_schedule_and_run_now(db_session) -> None:
  seed = await _seed_schedulable_template(db_session)
  service = _schedule_service(db_session)
  schedule = await service.create_schedule(
    actor=seed["admin"],
    payload=GraphTemplateScheduleCreateRequest(
      template_id=seed["template"].id,
      name="每周采集",
      scope_department_id=seed["department"].id,
      scope_mode="self",
      cron_expr="0 9 * * 1",
      participant_mode="all",
      exclude_user_ids=[seed["manager"].id],
    ),
  )
  assert schedule.next_run_at is not None

  result = await service.run_schedule_now(actor=seed["admin"], schedule_id=schedule.id)
  assert result.created_count == 1

  instance = await db_session.scalar(
    select(WorkflowGraphInstance).where(
      WorkflowGraphInstance.template_id == seed["template"].id,
      WorkflowGraphInstance.department_id == seed["department"].id,
    )
  )
  assert instance is not None
  assert instance.status == WorkflowGraphInstanceStatus.ACTIVE
  assert (instance.context or {}).get("schedule_id") == str(schedule.id)


@pytest.mark.asyncio
@pytest.mark.workflow_i4_gate
async def test_i3f_schedule_run_now_command_replay_creates_one_run(db_session) -> None:  # noqa: ANN001
  seed = await _seed_schedulable_template(db_session)
  service = _schedule_service(db_session)
  schedule = await service.create_schedule(
    actor=seed["admin"],
    payload=GraphTemplateScheduleCreateRequest(
      template_id=seed["template"].id,
      name="幂等执行",
      scope_department_id=seed["department"].id,
      cron_expr="0 9 * * 1",
    ),
  )

  async def operation() -> dict[str, object]:
    result = await service.run_schedule_now(
      actor=seed["admin"],
      schedule_id=schedule.id,
      commit=False,
    )
    return result.model_dump(mode="json")

  executor = WorkflowCommandExecutor(db_session)
  first = await executor.execute(
    command_id="i3f-schedule-replay-001",
    command_type="schedule_run_now",
    payload={"schedule_id": str(schedule.id)},
    operation=operation,
    actor_user_id=seed["admin"].id,
    aggregate_type="workflow_schedule",
    aggregate_id=schedule.id,
  )
  replay = await executor.execute(
    command_id="i3f-schedule-replay-001",
    command_type="schedule_run_now",
    payload={"schedule_id": str(schedule.id)},
    operation=operation,
    actor_user_id=seed["admin"].id,
    aggregate_type="workflow_schedule",
    aggregate_id=schedule.id,
  )
  assert replay == first
  assert await db_session.scalar(
    select(func.count(WorkflowGraphInstance.id)).where(
      WorkflowGraphInstance.template_id == seed["template"].id
    )
  ) == 1
  assert await db_session.scalar(
    select(func.count(WorkflowCommandReceipt.id)).where(
      WorkflowCommandReceipt.command_id == "i3f-schedule-replay-001"
    )
  ) == 1


@pytest.mark.asyncio
async def test_f24_rejects_overlap_on_publish(db_session) -> None:
  seed = await _seed_schedulable_template(db_session)
  service = _schedule_service(db_session)
  await service.run_schedule_now(
    actor=seed["admin"],
    schedule_id=(
      await service.create_schedule(
        actor=seed["admin"],
        payload=GraphTemplateScheduleCreateRequest(
          template_id=seed["template"].id,
          name="第一次",
          scope_department_id=seed["department"].id,
          cron_expr="0 9 * * 1",
        ),
      )
    ).id,
  )

  with pytest.raises(ConflictError, match="已有进行中"):
    await service.create_schedule(
      actor=seed["admin"],
      payload=GraphTemplateScheduleCreateRequest(
        template_id=seed["template"].id,
        name="第二次",
        scope_department_id=seed["department"].id,
        cron_expr="0 10 * * 1",
      ),
    )


@pytest.mark.asyncio
async def test_f24_run_due_schedules(db_session) -> None:
  seed = await _seed_schedulable_template(db_session)
  service = _schedule_service(db_session)
  schedule = await service.create_schedule(
    actor=seed["admin"],
    payload=GraphTemplateScheduleCreateRequest(
      template_id=seed["template"].id,
      name="到期测试",
      scope_department_id=seed["department"].id,
      cron_expr="0 9 * * 1",
    ),
  )
  row = await db_session.get(WorkflowGraphTemplateSchedule, schedule.id)
  assert row is not None
  row.next_run_at = datetime.now(UTC)
  await db_session.commit()

  count = await service.run_due_schedules(now=datetime.now(UTC))
  assert count == 1
