"""Iteration 4 manual-UAT prerequisite reporting."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import Settings
from app.core.enums import TaskStatus, UserRole, WorkflowGraphTemplateStatus
from app.core.exceptions import NotFoundError
from app.models import (
  Profile,
  Task,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateNode,
)
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.user_service import UserService
from app.services.workflow_iteration4_uat_preflight_service import (
  WorkflowIteration4UatPreflightService,
)
from app.services.workflow_video_template_seed_data import (
  TOPIC_MEETING_BATCH_CODE,
  VIDEO_PRODUCTION_CODE,
)


TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


async def _admin(db_session):
  return await AuthService(db_session, Settings(jwt_secret_key=TEST_JWT_SECRET)).bootstrap_admin(
    email="uat-preflight-admin@example.com",
    password="StrongPassword123!",
    real_name="验收管理员",
    employee_no="EMP-UAT-ADMIN",
  )


def _template(
  *,
  actor_id,
  code: str,
  name: str,
  status,
  base_code: str | None = None,
  version: int = 1,
  config=None,
  scope_ids=None,
):
  return WorkflowGraphTemplate(
    code=code,
    base_code=base_code or code,
    version=version,
    name=name,
    status=status,
    config=config or {},
    context_schema={},
    scope_mode="departments" if scope_ids else "global",
    scope_department_ids=scope_ids or [],
    created_by=actor_id,
  )


@pytest.mark.asyncio
async def test_preflight_reports_missing_manual_uat_prerequisites(db_session) -> None:
  admin = await _admin(db_session)

  report = await WorkflowIteration4UatPreflightService(db_session).build_report(actor=admin)

  assert report.preflight_ready is False
  assert report.manual_uat_required is True
  check_by_id = {check.check_id: check for check in report.checks}
  assert check_by_id["P-02"].status == "blocked"
  assert check_by_id["P-03"].status == "warning"
  assert check_by_id["P-04"].status == "blocked"
  assert check_by_id["P-06"].status == "warning"
  assert check_by_id["P-07"].status == "manual"


@pytest.mark.asyncio
async def test_preflight_finds_template_account_and_statistics_candidates(db_session) -> None:
  admin = await _admin(db_session)
  department = await DepartmentService(db_session).create_department(
    actor=admin,
    name="验收业务部",
    code="uat-ready-department",
  )
  users = UserService(db_session)
  manager = await users.create_user(
    actor=admin,
    email="uat-manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  member_b = await users.create_user(
    actor=admin,
    email="uat-member-b@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  member_c = await users.create_user(
    actor=admin,
    email="uat-member-c@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department.manager_id = manager.id
  db_session.add_all(
    [
      Profile(user_id=manager.id, employee_no="EMP-UAT-A", real_name="负责人 A", department_id=department.id),
      Profile(user_id=member_b.id, employee_no="EMP-UAT-B", real_name="成员 B", department_id=department.id),
      Profile(user_id=member_c.id, employee_no="EMP-UAT-C", real_name="成员 C", department_id=department.id),
    ]
  )

  generic = _template(
    actor_id=admin.id,
    code="material_collection_v1",
    name="材料收集",
    status=WorkflowGraphTemplateStatus.ACTIVE,
  )
  batch = _template(
    actor_id=admin.id,
    code="topic_meeting_batch_v2",
    base_code=TOPIC_MEETING_BATCH_CODE,
    version=2,
    name="视频选题会",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    config={"child_template_code": "video_production_per_topic_v2"},
  )
  child = _template(
    actor_id=admin.id,
    code="video_production_per_topic_v2",
    base_code=VIDEO_PRODUCTION_CODE,
    version=2,
    name="视频制作",
    status=WorkflowGraphTemplateStatus.ACTIVE,
  )
  draft = _template(
    actor_id=admin.id,
    code="designer_sample_v1",
    name="设计器验收草稿",
    status=WorkflowGraphTemplateStatus.DRAFT,
    scope_ids=[str(department.id)],
  )
  db_session.add_all([generic, batch, child, draft])
  await db_session.flush()
  db_session.add_all(
    [
      WorkflowGraphTemplateNode(
        template_id=generic.id,
        node_key="N1",
        title="收集材料",
        sort_order=1,
      ),
      WorkflowGraphTemplateNode(
        template_id=batch.id,
        node_key="N1",
        title="收集选题",
        sort_order=1,
      ),
      WorkflowGraphTemplateNode(
        template_id=child.id,
        node_key="N1",
        title="制作",
        sort_order=1,
      ),
      WorkflowGraphTemplateNode(
        template_id=draft.id,
        node_key="N1",
        title="开始",
        sort_order=1,
      ),
    ]
  )
  now = datetime.now(UTC)
  db_session.add_all(
    [
      Task(
        title="本月未完成样本",
        creator_id=manager.id,
        assignee_id=member_b.id,
        department_id=department.id,
        status=TaskStatus.DOING,
        due_date=now + timedelta(days=1),
        extra_metadata={},
      ),
      Task(
        title="本月已完成样本",
        creator_id=manager.id,
        assignee_id=member_c.id,
        department_id=department.id,
        status=TaskStatus.DONE,
        due_date=now,
        completed_at=now,
        extra_metadata={},
      ),
    ]
  )
  await db_session.commit()

  report = await WorkflowIteration4UatPreflightService(db_session).build_report(actor=admin)

  assert report.preflight_ready is True
  assert report.blocking_count == 0
  check_by_id = {check.check_id: check for check in report.checks}
  assert check_by_id["P-02"].status == "pass"
  assert check_by_id["P-03"].status == "pass"
  assert check_by_id["P-04"].status == "pass"
  assert check_by_id["P-05"].status == "pass"
  assert check_by_id["P-06"].status == "pass"
  assert {candidate.kind for candidate in report.template_candidates} == {
    "domain_neutral",
    "video_batch",
    "video_child",
    "designer_draft",
  }
  assert report.department_candidates[0].active_member_count == 3
  assert report.stats_sample.created_count == 2
  assert report.stats_sample.completed_count == 1
  assert report.stats_sample.due_count == 2
  assert report.stats_sample.current_open_count == 1


@pytest.mark.asyncio
async def test_preflight_requires_template_management_permission(db_session) -> None:
  admin = await _admin(db_session)
  employee = await UserService(db_session).create_user(
    actor=admin,
    email="uat-unprivileged@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  with pytest.raises(NotFoundError, match="模板不存在"):
    await WorkflowIteration4UatPreflightService(db_session).build_report(actor=employee)
