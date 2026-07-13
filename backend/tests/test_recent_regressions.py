from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.api.routes.workflow_graph_engine import list_graph_templates
from app.core.config import Settings
from app.core.enums import (
  AttachmentTargetType,
  TaskPriority,
  TaskSourceType,
  TaskStatus,
  UserRole,
  WorkflowGraphInstanceStatus,
  WorkflowGraphTemplateStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.core.exceptions import AuthorizationError, ConflictError
from app.models import (
  Attachment,
  AttachmentLink,
  Task,
  WorkflowDeliverable,
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateEdge,
  WorkflowGraphTemplateNode,
  WorkflowNodeInstance,
)
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.user_service import UserService
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_graph_template_admin_service import WorkflowGraphTemplateAdminService
from app.services.workflow_orchestration_service import WorkflowOrchestrationService


TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


async def _admin(db_session):
  return await AuthService(db_session, Settings(jwt_secret_key=TEST_JWT_SECRET)).bootstrap_admin(
    email="recent-regressions-admin@example.com",
    password="StrongPassword123!",
    real_name="回归管理员",
    employee_no="EMP-REG",
  )


@pytest.mark.asyncio
async def test_graph_template_department_scope_filters_active_templates(db_session) -> None:
  admin = await _admin(db_session)
  manager = await UserService(db_session).create_user(
    actor=admin,
    email="scope-manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  departments = DepartmentService(db_session)
  managed = await departments.create_department(
    actor=admin,
    name="管理部门",
    code="scope-managed",
    manager_id=manager.id,
  )
  other = await departments.create_department(actor=admin, name="其他部门", code="scope-other")

  db_session.add_all(
    [
      WorkflowGraphTemplate(
        code="scope-open",
        base_code="scope-open",
        version=1,
        name="开放模板",
        status=WorkflowGraphTemplateStatus.ACTIVE,
        scope_mode="global",
        scope_department_ids=[],
        created_by=admin.id,
      ),
      WorkflowGraphTemplate(
        code="scope-managed",
        base_code="scope-managed",
        version=1,
        name="管理部门模板",
        status=WorkflowGraphTemplateStatus.ACTIVE,
        scope_mode="departments",
        scope_department_ids=[str(managed.id)],
        created_by=admin.id,
      ),
      WorkflowGraphTemplate(
        code="scope-hidden",
        base_code="scope-hidden",
        version=1,
        name="其他部门模板",
        status=WorkflowGraphTemplateStatus.ACTIVE,
        scope_mode="departments",
        scope_department_ids=[str(other.id)],
        created_by=admin.id,
      ),
    ]
  )
  await db_session.commit()

  summaries = await list_graph_templates(
    actor=manager,
    session=db_session,
    workflow_graph_service=WorkflowGraphService(db_session),
    admin_service=WorkflowGraphTemplateAdminService(db_session),
  )
  codes = {item.code for item in summaries}
  assert {"scope-open", "scope-managed"}.issubset(codes)
  assert "scope-hidden" not in codes


@pytest.mark.asyncio
async def test_graph_template_delete_guards_permissions_and_existing_runs(db_session) -> None:
  admin = await _admin(db_session)
  employee = await UserService(db_session).create_user(
    actor=admin,
    email="delete-employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  service = WorkflowGraphTemplateAdminService(db_session)
  deletable = WorkflowGraphTemplate(
    code="delete-empty",
    base_code="delete-empty",
    version=1,
    name="可删除模板",
    status=WorkflowGraphTemplateStatus.DRAFT,
    created_by=admin.id,
  )
  protected = WorkflowGraphTemplate(
    code="delete-protected",
    base_code="delete-protected",
    version=1,
    name="有实例模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add_all([deletable, protected])
  await db_session.flush()
  db_session.add(
    WorkflowGraphInstance(
      template_id=protected.id,
      initiator_user_id=admin.id,
      status=WorkflowGraphInstanceStatus.ACTIVE,
      context={},
    )
  )
  await db_session.commit()

  with pytest.raises(AuthorizationError):
    await service.delete_template(actor=employee, template_id=deletable.id)
  with pytest.raises(ConflictError, match="已发布版本只能归档"):
    await service.delete_template(actor=admin, template_id=protected.id)
  assert await service.delete_template(actor=admin, template_id=deletable.id) is True
  assert await db_session.get(WorkflowGraphTemplate, deletable.id) is None


@pytest.mark.asyncio
async def test_upstream_deliverable_attachments_are_inherited_once(db_session) -> None:
  admin = await _admin(db_session)
  template = WorkflowGraphTemplate(
    code="inherit-attachments",
    base_code="inherit-attachments",
    version=1,
    name="附件继承模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()
  upstream_template = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="upstream",
    title="上游",
    sort_order=1,
  )
  downstream_template = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="downstream",
    title="下游",
    sort_order=2,
  )
  db_session.add_all([upstream_template, downstream_template])
  await db_session.flush()
  db_session.add(
    WorkflowGraphTemplateEdge(
      template_id=template.id,
      from_node_id=upstream_template.id,
      to_node_id=downstream_template.id,
    )
  )
  instance = WorkflowGraphInstance(
    template_id=template.id,
    initiator_user_id=admin.id,
    status=WorkflowGraphInstanceStatus.ACTIVE,
    context={},
  )
  db_session.add(instance)
  await db_session.flush()
  upstream = WorkflowNodeInstance(
    instance_id=instance.id,
    template_node_id=upstream_template.id,
    node_key="upstream",
    title="上游",
    engine_state=WorkflowNodeEngineState.COMPLETED,
    business_state=WorkflowNodeBusinessState.DONE,
  )
  downstream = WorkflowNodeInstance(
    instance_id=instance.id,
    template_node_id=downstream_template.id,
    node_key="downstream",
    title="下游",
    engine_state=WorkflowNodeEngineState.ACTIVATED,
    business_state=WorkflowNodeBusinessState.DOING,
  )
  db_session.add_all([upstream, downstream])
  await db_session.flush()
  attachment = Attachment(
    storage_provider="local",
    bucket="test",
    object_key="inherit/file.md",
    original_filename="file.md",
    mime_type="text/markdown",
    size_bytes=4,
    checksum_sha256="0" * 64,
    uploader_id=admin.id,
  )
  target_task = Task(
    title="下游任务",
    creator_id=admin.id,
    assignee_id=admin.id,
    status=TaskStatus.TODO,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.TEMPLATE,
  )
  db_session.add_all([attachment, target_task])
  await db_session.flush()
  db_session.add(
    WorkflowDeliverable(
      node_instance_id=upstream.id,
      submitted_by_user_id=admin.id,
      submitted_at=datetime.now(UTC),
      payload={"latest_submission": {"attachment_ids": [str(attachment.id), "invalid"]}},
    )
  )
  await db_session.flush()

  orchestration = WorkflowOrchestrationService(db_session)
  await orchestration._inherit_upstream_deliverable_attachments(
    instance=instance,
    node_instance=downstream,
    target_task=target_task,
  )
  await db_session.flush()
  await orchestration._inherit_upstream_deliverable_attachments(
    instance=instance,
    node_instance=downstream,
    target_task=target_task,
  )
  await db_session.flush()

  links = list(
    await db_session.scalars(
      select(AttachmentLink).where(
        AttachmentLink.target_type == AttachmentTargetType.TASK,
        AttachmentLink.target_id == target_task.id,
      )
    )
  )
  assert len(links) == 1
  assert links[0].attachment_id == attachment.id
  assert links[0].relation == "inherited_deliverable"
  assert links[0].created_by == admin.id
