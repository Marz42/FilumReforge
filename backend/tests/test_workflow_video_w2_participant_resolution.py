"""W2 tests: participant resolution and assignee rule extensions."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.core.enums import UserRole, WorkflowGraphTemplateStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.models import Profile, User, WorkflowGraphTemplate
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.participant_resolution_service import ParticipantResolutionService
from app.services.profile_service import ProfileService
from app.services.user_service import UserService
from app.services.workflow_rule_resolver import resolve_user_targets_from_rule
from app.schemas.workflow_video import ParticipantsSnapshotEntry

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


async def _bootstrap_copywriting_team(db_session) -> tuple[User, User, User, User, object]:
  from app.core.config import Settings

  auth = AuthService(db_session, Settings(jwt_secret_key=TEST_JWT_SECRET))
  admin = await auth.bootstrap_admin(
    email="w2-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-W2-ROOT",
  )
  user_service = UserService(db_session)
  dept_service = DepartmentService(db_session)
  profile_service = ProfileService(db_session)

  manager = await user_service.create_user(
    actor=admin,
    email="w2-manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  editor_a = await user_service.create_user(
    actor=admin,
    email="w2-editor-a@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  editor_b = await user_service.create_user(
    actor=admin,
    email="w2-editor-b@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await dept_service.create_department(
    actor=admin,
    name="文案部",
    code="w2-copywriting",
    manager_id=manager.id,
  )
  for user, employee_no, real_name in (
    (manager, "EMP-W2-MGR", "文案负责人"),
    (editor_a, "EMP-W2-A", "编辑甲"),
    (editor_b, "EMP-W2-B", "编辑乙"),
  ):
    await profile_service.create_profile(
      actor=admin,
      user_id=user.id,
      employee_no=employee_no,
      real_name=real_name,
      department_id=department.id,
      custom_fields={},
    )

  template = WorkflowGraphTemplate(
    code="topic_meeting_batch_v1",
    base_code="topic_meeting_batch_v1",
    version=1,
    name="选题会",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    config={
      "participant_policies": {
        "copywriters": {"type": "department_members", "department_id": str(department.id)},
      },
      "department_pools": {
        "voice_over": str(department.id),
      },
    },
    context_schema={},
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()
  return admin, manager, editor_a, editor_b, template


@pytest.mark.asyncio
async def test_w2_resolve_department_members_all_mode(db_session) -> None:
  admin, manager, editor_a, editor_b, template = await _bootstrap_copywriting_team(db_session)
  service = ParticipantResolutionService(db_session)

  users = await service.resolve_policy_for_template(
    actor=admin,
    template=template,
    policy_ref="copywriters",
    mode="all",
  )
  resolved_ids = {user.id for user in users}
  assert {manager.id, editor_a.id, editor_b.id}.issubset(resolved_ids)


@pytest.mark.asyncio
async def test_w2_resolve_subset_requires_members_in_department(db_session) -> None:
  admin, _manager, editor_a, editor_b, template = await _bootstrap_copywriting_team(db_session)
  service = ParticipantResolutionService(db_session)

  users = await service.resolve_policy_for_template(
    actor=admin,
    template=template,
    policy_ref="copywriters",
    mode="subset",
    selected_user_ids=[editor_a.id],
  )
  assert [user.id for user in users] == [editor_a.id]

  outsider_id = uuid4()
  with pytest.raises(ConflictError, match="不在该策略允许"):
    await service.resolve_policy_for_template(
      actor=admin,
      template=template,
      policy_ref="copywriters",
      mode="subset",
      selected_user_ids=[outsider_id],
    )


@pytest.mark.asyncio
async def test_w2_subset_without_user_ids_raises(db_session) -> None:
  admin, *_rest, template = await _bootstrap_copywriting_team(db_session)
  service = ParticipantResolutionService(db_session)

  with pytest.raises(ConflictError, match="至少一名参与人"):
    await service.resolve_policy_for_template(
      actor=admin,
      template=template,
      policy_ref="copywriters",
      mode="subset",
      selected_user_ids=[],
    )


@pytest.mark.asyncio
async def test_w2_frozen_snapshot_ignores_later_department_changes(db_session) -> None:
  admin, manager, editor_a, editor_b, template = await _bootstrap_copywriting_team(db_session)
  service = ParticipantResolutionService(db_session)

  initial_users = await service.resolve_policy_for_template(
    actor=admin,
    template=template,
    policy_ref="copywriters",
    mode="all",
  )
  frozen = service.build_snapshot_entry(users=initial_users, mode="all")
  frozen_entry = ParticipantsSnapshotEntry.model_validate(frozen.model_dump())

  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  new_editor = await user_service.create_user(
    actor=admin,
    email="w2-editor-c@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department_id = UUID(str(template.config["participant_policies"]["copywriters"]["department_id"]))
  await profile_service.create_profile(
    actor=admin,
    user_id=new_editor.id,
    employee_no="EMP-W2-C",
    real_name="编辑丙",
    department_id=department_id,
    custom_fields={},
  )

  later_users = await service.resolve_policy_for_template(
    actor=admin,
    template=template,
    policy_ref="copywriters",
    mode="all",
  )
  assert new_editor.id in {user.id for user in later_users}
  assert new_editor.id not in set(frozen_entry.user_ids)
  assert len(frozen_entry.user_ids) == len(initial_users)


@pytest.mark.asyncio
async def test_w2_context_var_assignee_rule(db_session) -> None:
  admin, manager, editor_a, _editor_b, _template = await _bootstrap_copywriting_team(db_session)
  author_id = editor_a.id
  users = await resolve_user_targets_from_rule(
    db_session,
    actor=admin,
    assignee_rule={"type": "context_var", "var": "script_author_id"},
    context={"script_author_id": str(author_id)},
  )
  assert len(users) == 1
  assert users[0].id == author_id


@pytest.mark.asyncio
async def test_w2_department_pool_manager_rule(db_session) -> None:
  admin, manager, _editor_a, _editor_b, template = await _bootstrap_copywriting_team(db_session)
  pools = {
    "voice_over": template.config["department_pools"]["voice_over"],
  }
  if isinstance(pools["voice_over"], str):
    pools["voice_over"] = UUID(str(pools["voice_over"]))

  users = await resolve_user_targets_from_rule(
    db_session,
    actor=admin,
    assignee_rule={"type": "department_pool", "pool_key": "voice_over", "assignee_role": "manager"},
    department_pools=pools,
  )
  assert len(users) == 1
  assert users[0].id == manager.id


@pytest.mark.asyncio
async def test_w2_missing_policy_ref_raises(db_session) -> None:
  admin, *_rest, template = await _bootstrap_copywriting_team(db_session)
  service = ParticipantResolutionService(db_session)
  with pytest.raises(NotFoundError, match="unknown_policy"):
    await service.resolve_policy_for_template(
      actor=admin,
      template=template,
      policy_ref="unknown_policy",
      mode="all",
    )


@pytest.mark.asyncio
async def test_w2_preview_for_template_returns_snapshot(db_session) -> None:
  admin, _manager, editor_a, editor_b, template = await _bootstrap_copywriting_team(db_session)
  service = ParticipantResolutionService(db_session)
  snapshot, users = await service.preview_for_template(
    actor=admin,
    template=template,
    policy_ref="copywriters",
    mode="subset",
    selected_user_ids=[editor_a.id, editor_b.id],
  )
  assert snapshot.mode == "subset"
  assert set(snapshot.user_ids) == {editor_a.id, editor_b.id}
  assert len(users) == 2
