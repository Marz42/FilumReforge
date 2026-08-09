"""Regression gates for the 2026-08 security review."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.requests import Request

from app.api.routes.workflow_graph_engine import (
  compute_smart_notice_candidates,
  get_graph_template,
  list_department_pool_member_options,
)
from app.core.config import Settings
from app.core.enums import UserRole, WorkflowGraphTemplateStatus
from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.rate_limit import _resolve_client_identity
from app.models import Profile, WorkflowGraphTemplate
from app.schemas.workflow_graph import (
  WorkflowGraphTemplateUpdateRequest,
  WorkflowSmartNoticeCandidatesRequest,
)
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.user_service import UserService
from app.services.workflow_access_policy import WorkflowAccessPolicy
from app.services.workflow_graph_template_admin_service import WorkflowGraphTemplateAdminService


REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


async def _seed_security_scope(db_session):
  admin = await AuthService(db_session, Settings(jwt_secret_key=TEST_JWT_SECRET)).bootstrap_admin(
    email="security-admin@example.com",
    password="StrongPassword123!",
    real_name="安全管理员",
    employee_no="EMP-SEC-ADMIN",
  )
  manager = await UserService(db_session).create_user(
    actor=admin,
    email="security-manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  reader = await UserService(db_session).create_user(
    actor=admin,
    email="security-reader@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  departments = DepartmentService(db_session)
  managed = await departments.create_department(
    actor=admin,
    name="安全受管部门",
    code="security-managed",
    manager_id=manager.id,
  )
  other = await departments.create_department(
    actor=admin,
    name="安全其他部门",
    code="security-other",
  )
  db_session.add(
    Profile(
      user_id=reader.id,
      employee_no="EMP-SEC-READER",
      real_name="安全读取人",
      department_id=other.id,
      custom_fields={},
    )
  )
  managed_template = WorkflowGraphTemplate(
    code="security-managed-template",
    base_code="security-managed-template",
    version=1,
    name="受管模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    scope_mode="departments",
    scope_department_ids=[str(managed.id)],
    created_by=admin.id,
  )
  hidden_template = WorkflowGraphTemplate(
    code="security-hidden-template",
    base_code="security-hidden-template",
    version=1,
    name="其他部门模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    scope_mode="departments",
    scope_department_ids=[str(other.id)],
    created_by=admin.id,
  )
  db_session.add_all([managed_template, hidden_template])
  await db_session.commit()
  return admin, manager, reader, managed_template, hidden_template


def test_auth_rate_limit_ignores_untrusted_forwarded_header() -> None:
  request = Request(
    {
      "type": "http",
      "method": "POST",
      "path": "/api/v1/auth/login",
      "headers": [(b"x-forwarded-for", b"198.51.100.77")],
      "client": ("127.0.0.1", 41000),
    }
  )
  assert _resolve_client_identity(request) == "127.0.0.1"


def test_gateway_overwrites_forwarded_for_and_backend_default_is_loopback() -> None:
  for path in (
    REPO_ROOT / "infra/nginx/default.conf",
    REPO_ROOT / "infra/nginx/nginx.prod.conf",
    REPO_ROOT / "infra/nginx/nginx.compose.prod.conf",
  ):
    content = path.read_text(encoding="utf-8")
    assert "$proxy_add_x_forwarded_for" not in content
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in content

  start_script = (REPO_ROOT / "backend/scripts/start-prod.sh").read_text(encoding="utf-8")
  assert 'FORWARDED_ALLOW_IPS="${FORWARDED_ALLOW_IPS:-127.0.0.1}"' in start_script
  assert '--forwarded-allow-ips "$FORWARDED_ALLOW_IPS"' in start_script
  compose = (REPO_ROOT / "infra/docker/docker-compose.prod.yml").read_text(encoding="utf-8")
  assert 'FORWARDED_ALLOW_IPS: "*"' not in compose
  assert "FORWARDED_ALLOW_IPS: ${NGINX_INTERNAL_IP:-172.30.0.10}" in compose


@pytest.mark.asyncio
async def test_department_manager_cannot_modify_template_outside_scope(db_session) -> None:
  _admin, manager, _reader, managed_template, hidden_template = await _seed_security_scope(
    db_session
  )
  policy = WorkflowAccessPolicy(db_session)
  await policy.ensure_can_manage_templates(actor=manager, template_id=managed_template.id)

  with pytest.raises(NotFoundError):
    await WorkflowGraphTemplateAdminService(db_session).update_tags(
      actor=manager,
      template_id=hidden_template.id,
      tags=["越权修改"],
    )

  managed_template.status = WorkflowGraphTemplateStatus.DRAFT
  await db_session.commit()
  with pytest.raises(AuthorizationError):
    await WorkflowGraphTemplateAdminService(db_session).update_template(
      actor=manager,
      template_id=managed_template.id,
      payload=WorkflowGraphTemplateUpdateRequest(
        scope_mode="departments",
        scope_department_ids=hidden_template.scope_department_ids,
      ),
    )


@pytest.mark.asyncio
async def test_template_detail_and_pool_options_conceal_unreadable_scope(db_session) -> None:
  _admin, _manager, reader, managed_template, _hidden_template = await _seed_security_scope(
    db_session
  )

  with pytest.raises(NotFoundError):
    await get_graph_template(
      template_id=managed_template.id,
      actor=reader,
      session=db_session,
      admin_service=WorkflowGraphTemplateAdminService(db_session),
    )

  with pytest.raises(NotFoundError):
    await list_department_pool_member_options(
      template_id=managed_template.id,
      pool_key="copywriters",
      actor=reader,
      session=db_session,
      participant_service=None,  # type: ignore[arg-type]
      instance_id=None,
    )


@pytest.mark.asyncio
async def test_smart_notice_rejects_unrelated_user_id_probe(db_session) -> None:
  admin, manager, reader, _managed_template, _hidden_template = await _seed_security_scope(
    db_session
  )
  payload = WorkflowSmartNoticeCandidatesRequest(
    initiator_user_id=reader.id,
    target_user_id=manager.id,
  )

  with pytest.raises(NotFoundError):
    await compute_smart_notice_candidates(
      payload=payload,
      actor=reader,
      session=db_session,
      organization_relation_service=None,  # type: ignore[arg-type]
    )
