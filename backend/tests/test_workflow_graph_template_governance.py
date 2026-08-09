"""Template scope and dependency governance audit."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.enums import WorkflowGraphTemplateStatus
from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.workflow_graph_template_governance_service import (
  WorkflowGraphTemplateGovernanceService,
)


TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


async def _admin(db_session):
  return await AuthService(db_session, Settings(jwt_secret_key=TEST_JWT_SECRET)).bootstrap_admin(
    email="governance-admin@example.com",
    password="StrongPassword123!",
    real_name="模板治理管理员",
    employee_no="EMP-GOVERNANCE-ADMIN",
  )


def _template(
  *,
  actor_id,
  code: str,
  base_code: str | None = None,
  version: int = 1,
  status: WorkflowGraphTemplateStatus = WorkflowGraphTemplateStatus.ACTIVE,
  scope_mode: str = "global",
  scope_department_ids: list[str] | None = None,
  config: dict | None = None,
) -> WorkflowGraphTemplate:
  return WorkflowGraphTemplate(
    code=code,
    base_code=base_code or code,
    version=version,
    name=code,
    status=status,
    config=config or {},
    context_schema={},
    scope_mode=scope_mode,
    scope_department_ids=scope_department_ids or [],
    created_by=actor_id,
  )


@pytest.mark.asyncio
async def test_audit_flags_global_review_and_ignored_department_ids(db_session) -> None:
  admin = await _admin(db_session)
  department = await DepartmentService(db_session).create_department(
    actor=admin,
    name="业务部",
    code="governance-business",
  )
  template = _template(
    actor_id=admin.id,
    code="global_template_v1",
    scope_department_ids=[str(department.id)],
  )
  db_session.add(template)
  await db_session.commit()

  report = await WorkflowGraphTemplateGovernanceService(db_session).audit_manageable_templates(
    actor=admin
  )

  assert report.template_count == 1
  assert report.warning_count == 1
  assert report.review_count == 1
  assert {issue.issue_code for issue in report.issues} == {
    "global_scope_has_department_ids",
    "global_scope_review_required",
  }
  action_by_code = {issue.issue_code: issue.repair_action for issue in report.issues}
  assert action_by_code["global_scope_has_department_ids"] == "create_new_version"
  assert action_by_code["global_scope_review_required"] == "review_configuration"


@pytest.mark.asyncio
async def test_audit_flags_empty_missing_and_inactive_department_scope(db_session) -> None:
  admin = await _admin(db_session)
  departments = DepartmentService(db_session)
  inactive = await departments.create_department(
    actor=admin,
    name="停用业务部",
    code="governance-inactive",
  )
  inactive.is_active = False
  empty = _template(
    actor_id=admin.id,
    code="empty_scope_v1",
    status=WorkflowGraphTemplateStatus.DRAFT,
    scope_mode="departments",
  )
  invalid = _template(
    actor_id=admin.id,
    code="invalid_scope_v1",
    scope_mode="departments",
    scope_department_ids=[str(inactive.id), "00000000-0000-0000-0000-000000000099"],
  )
  db_session.add_all([empty, invalid])
  await db_session.commit()

  report = await WorkflowGraphTemplateGovernanceService(db_session).audit_manageable_templates(
    actor=admin
  )

  issue_by_code = {issue.issue_code: issue for issue in report.issues}
  assert report.error_count == 3
  assert issue_by_code["department_scope_empty"].repair_action == "edit_draft"
  assert issue_by_code["scope_department_missing"].affected_department_ids == [
    "00000000-0000-0000-0000-000000000099"
  ]
  assert issue_by_code["scope_department_inactive"].affected_department_ids == [str(inactive.id)]


@pytest.mark.asyncio
async def test_audit_finds_stale_child_reference_and_scope_mismatch(db_session) -> None:
  admin = await _admin(db_session)
  departments = DepartmentService(db_session)
  first = await departments.create_department(
    actor=admin,
    name="第一业务部",
    code="governance-first",
  )
  second = await departments.create_department(
    actor=admin,
    name="第二业务部",
    code="governance-second",
  )
  old_child = _template(
    actor_id=admin.id,
    code="child_flow_v1",
    base_code="child_flow_v1",
    status=WorkflowGraphTemplateStatus.ARCHIVED,
    scope_mode="departments",
    scope_department_ids=[str(first.id)],
  )
  new_child = _template(
    actor_id=admin.id,
    code="child_flow_v2",
    base_code="child_flow_v1",
    version=2,
    scope_mode="departments",
    scope_department_ids=[str(first.id)],
  )
  parent = _template(
    actor_id=admin.id,
    code="parent_flow_v1",
    scope_mode="departments",
    scope_department_ids=[str(first.id), str(second.id)],
    config={"child_template_code": "child_flow_v1"},
  )
  db_session.add_all([old_child, new_child, parent])
  await db_session.commit()

  report = await WorkflowGraphTemplateGovernanceService(db_session).audit_manageable_templates(
    actor=admin
  )

  parent_issues = [issue for issue in report.issues if issue.template_id == parent.id]
  assert {issue.issue_code for issue in parent_issues} == {
    "stale_child_template_reference",
    "dependency_scope_mismatch",
  }
  stale = next(issue for issue in parent_issues if issue.issue_code == "stale_child_template_reference")
  assert stale.suggested_template_code == "child_flow_v2"
  mismatch = next(issue for issue in parent_issues if issue.issue_code == "dependency_scope_mismatch")
  assert mismatch.affected_department_ids == [str(second.id)]


@pytest.mark.asyncio
async def test_audit_reads_nested_child_and_on_complete_references(db_session) -> None:
  admin = await _admin(db_session)
  parent = _template(
    actor_id=admin.id,
    code="nested_parent_v1",
    status=WorkflowGraphTemplateStatus.DRAFT,
    scope_mode="departments",
    scope_department_ids=["00000000-0000-0000-0000-000000000001"],
    config={"on_complete": {"next_template_code": "missing_chain"}},
  )
  db_session.add(parent)
  await db_session.flush()
  db_session.add(
    WorkflowGraphTemplateNode(
      template_id=parent.id,
      node_key="N1",
      title="汇总",
      config={
        "aggregate_schema": {
          "on_confirm": {
            "action": "finalize_topics_and_fork",
            "child_template_code": "missing_child_v1",
          }
        }
      },
      sort_order=1,
    )
  )
  await db_session.commit()

  report = await WorkflowGraphTemplateGovernanceService(db_session).audit_manageable_templates(
    actor=admin
  )

  references = {
    issue.referenced_template_code
    for issue in report.issues
    if issue.issue_code == "missing_template_dependency"
  }
  assert references == {"missing_chain", "missing_child_v1"}
  assert all(
    issue.repair_action == "edit_draft"
    for issue in report.issues
    if issue.referenced_template_code in references
  )
