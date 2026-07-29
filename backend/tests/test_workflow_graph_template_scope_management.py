"""Published workflow template availability scope governance."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.enums import UserRole, WorkflowGraphTemplateStatus
from app.core.exceptions import AuthorizationError, ConflictError
from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateScopeEvent
from app.schemas.workflow_graph import WorkflowGraphTemplateAvailabilityScopeUpdateRequest
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.user_service import UserService
from app.services.workflow_graph_template_admin_service import WorkflowGraphTemplateAdminService


TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


async def _seed_scope_fixture(db_session):
  admin = await AuthService(db_session, Settings(jwt_secret_key=TEST_JWT_SECRET)).bootstrap_admin(
    email="scope-admin@example.com",
    password="StrongPassword123!",
    real_name="模板管理员",
    employee_no="EMP-SCOPE-ADMIN",
  )
  departments = DepartmentService(db_session)
  first = await departments.create_department(actor=admin, name="业务一部", code="scope-first")
  second = await departments.create_department(actor=admin, name="业务二部", code="scope-second")
  disabled = await departments.create_department(actor=admin, name="停用部门", code="scope-disabled")
  disabled.is_active = False
  template = WorkflowGraphTemplate(
    code="generic_collection_scope_v1",
    base_code="generic_collection_scope_v1",
    version=1,
    name="通用材料收集",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    config={"instantiation_mode": "direct"},
    context_schema={},
    scope_mode="departments",
    scope_department_ids=[str(first.id)],
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.commit()
  return admin, template, first, second, disabled


@pytest.mark.asyncio
async def test_active_template_scope_can_expand_without_new_version_and_is_audited(db_session) -> None:
  admin, template, first, second, _disabled = await _seed_scope_fixture(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)

  result = await service.expand_availability_scope(
    actor=admin,
    template_id=template.id,
    payload=WorkflowGraphTemplateAvailabilityScopeUpdateRequest(
      scope_mode="departments",
      scope_department_ids=[first.id, second.id],
      reason="新增业务二部试用",
    ),
  )

  assert result.template_id == template.id
  assert set(result.scope_department_ids) == {str(first.id), str(second.id)}
  assert result.change.action == "departments_added"
  assert result.change.added_department_ids == [str(second.id)]
  persisted = await db_session.get(WorkflowGraphTemplate, template.id)
  assert persisted is not None
  assert persisted.version == 1
  assert set(persisted.scope_department_ids) == {str(first.id), str(second.id)}
  assert await db_session.scalar(select(func.count()).select_from(WorkflowGraphTemplateScopeEvent)) == 1

  history = await service.list_availability_scope_events(actor=admin, template_id=template.id)
  assert len(history) == 1
  assert history[0].reason == "新增业务二部试用"


@pytest.mark.asyncio
async def test_active_template_scope_cannot_remove_existing_department(db_session) -> None:
  admin, template, _first, second, _disabled = await _seed_scope_fixture(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)

  with pytest.raises(ConflictError, match="不可移除已有部门"):
    await service.expand_availability_scope(
      actor=admin,
      template_id=template.id,
      payload=WorkflowGraphTemplateAvailabilityScopeUpdateRequest(
        scope_mode="departments",
        scope_department_ids=[second.id],
        reason="错误地替换范围",
      ),
    )

  assert await db_session.scalar(select(func.count()).select_from(WorkflowGraphTemplateScopeEvent)) == 0


@pytest.mark.asyncio
async def test_active_template_scope_rejects_disabled_department(db_session) -> None:
  admin, template, first, _second, disabled = await _seed_scope_fixture(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)

  with pytest.raises(ConflictError, match="不存在或已停用"):
    await service.expand_availability_scope(
      actor=admin,
      template_id=template.id,
      payload=WorkflowGraphTemplateAvailabilityScopeUpdateRequest(
        scope_mode="departments",
        scope_department_ids=[first.id, disabled.id],
        reason="不应授权停用部门",
      ),
    )


@pytest.mark.asyncio
async def test_active_template_scope_can_expand_to_global(db_session) -> None:
  admin, template, _first, _second, _disabled = await _seed_scope_fixture(db_session)
  result = await WorkflowGraphTemplateAdminService(db_session).expand_availability_scope(
    actor=admin,
    template_id=template.id,
    payload=WorkflowGraphTemplateAvailabilityScopeUpdateRequest(
      scope_mode="global",
      scope_department_ids=[],
      reason="批准全公司使用",
    ),
  )

  assert result.scope_mode == "global"
  assert result.scope_department_ids == []
  assert result.change.action == "expanded_to_global"


@pytest.mark.asyncio
async def test_department_manager_cannot_expand_template_to_global(db_session) -> None:
  admin, template, first, _second, _disabled = await _seed_scope_fixture(db_session)
  manager = await UserService(db_session).create_user(
    actor=admin,
    email="scope-manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  first.manager_id = manager.id
  await db_session.commit()

  with pytest.raises(AuthorizationError, match="全局管理角色"):
    await WorkflowGraphTemplateAdminService(db_session).expand_availability_scope(
      actor=manager,
      template_id=template.id,
      payload=WorkflowGraphTemplateAvailabilityScopeUpdateRequest(
        scope_mode="global",
        scope_department_ids=[],
        reason="越权扩大为全局",
      ),
    )
