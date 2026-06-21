"""TCE Phase 4 (B-16): instance department overrides template participant policy."""

from __future__ import annotations

from uuid import UUID

import pytest

from app.core.config import Settings
from app.core.enums import UserRole, WorkflowGraphTemplateStatus
from app.core.exceptions import ConflictError
from app.models import WorkflowGraphTemplate
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.participant_resolution_service import ParticipantResolutionService
from app.services.profile_service import ProfileService
from app.services.user_service import UserService

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


async def _seed_two_copywriting_departments(db_session):
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth = AuthService(db_session, settings)
  admin = await auth.bootstrap_admin(
    email="tce-b16-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-TCE-B16",
  )
  user_service = UserService(db_session)
  dept_service = DepartmentService(db_session)
  profile_service = ProfileService(db_session)

  dept_a = await dept_service.create_department(actor=admin, name="文案部 A", code="copy-a", manager_id=admin.id)
  dept_b = await dept_service.create_department(actor=admin, name="文案部 B", code="copy-b", manager_id=admin.id)

  async def add_member(email: str, employee_no: str, department_id: UUID) -> object:
    user = await user_service.create_user(
      actor=admin,
      email=email,
      password="StrongPassword123!",
      role=UserRole.EMPLOYEE,
    )
    await profile_service.create_profile(
      actor=admin,
      user_id=user.id,
      employee_no=employee_no,
      real_name=employee_no,
      department_id=department_id,
      custom_fields={},
    )
    return user

  member_a = await add_member("tce-b16-a@example.com", "EMP-B16-A", dept_a.id)
  member_b = await add_member("tce-b16-b@example.com", "EMP-B16-B", dept_b.id)

  template = WorkflowGraphTemplate(
    code="topic_meeting_batch_v1",
    base_code="topic_meeting_batch_v1",
    version=1,
    name="选题会",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    config={
      "participant_policies": {
        "copywriters": {
          "type": "department_members",
          "department_id": str(dept_a.id),
          "scope": "instance_department",
        },
      },
    },
    context_schema={},
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()
  return admin, dept_a, dept_b, member_a, member_b, template


@pytest.mark.asyncio
async def test_tce_b16_instance_department_overrides_template_policy(db_session) -> None:
  admin, dept_a, dept_b, member_a, member_b, template = await _seed_two_copywriting_departments(db_session)
  service = ParticipantResolutionService(db_session)

  users_for_a = await service.resolve_policy_for_template(
    actor=admin,
    template=template,
    policy_ref="copywriters",
    department_id=dept_a.id,
    mode="subset",
    selected_user_ids=[member_a.id],
  )
  assert {user.id for user in users_for_a} == {member_a.id}

  users_for_b = await service.resolve_policy_for_template(
    actor=admin,
    template=template,
    policy_ref="copywriters",
    department_id=dept_b.id,
    mode="subset",
    selected_user_ids=[member_b.id],
  )
  assert {user.id for user in users_for_b} == {member_b.id}

  with pytest.raises(ConflictError, match="不在该策略允许"):
    await service.resolve_policy_for_template(
      actor=admin,
      template=template,
      policy_ref="copywriters",
      department_id=dept_b.id,
      mode="subset",
      selected_user_ids=[member_a.id],
    )


@pytest.mark.asyncio
async def test_tce_b16_template_department_scope_keeps_seed_department(db_session) -> None:
  admin, dept_a, dept_b, member_a, member_b, template = await _seed_two_copywriting_departments(db_session)
  template.config["participant_policies"]["copywriters"]["scope"] = "template_department"
  service = ParticipantResolutionService(db_session)

  users = await service.resolve_policy_for_template(
    actor=admin,
    template=template,
    policy_ref="copywriters",
    department_id=dept_b.id,
    mode="subset",
    selected_user_ids=[member_a.id],
  )
  assert {user.id for user in users} == {member_a.id}
  _ = member_b
