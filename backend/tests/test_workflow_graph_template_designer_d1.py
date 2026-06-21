"""D1 graph template designer admin APIs."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.enums import WorkflowGraphTemplateStatus
from app.models import WorkflowGraphInstance, WorkflowGraphTemplate, WorkflowGraphTemplateNode
from app.schemas.workflow_graph import (
  WorkflowGraphTemplateCreateRequest,
  WorkflowGraphTemplateDraftSaveRequest,
  WorkflowGraphTemplateNodeDraftWrite,
  WorkflowGraphTemplateStatusUpdateRequest,
  WorkflowGraphTemplateUpdateRequest,
)
from app.services.workflow_graph_template_admin_service import WorkflowGraphTemplateAdminService
from app.services.workflow_video_template_seed_service import WorkflowVideoTemplateSeedService

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


async def _seed_batch_template(db_session):
  from app.services.auth_service import AuthService
  from app.services.department_service import DepartmentService

  auth = AuthService(db_session, Settings(jwt_secret_key=TEST_JWT_SECRET))
  admin = await auth.bootstrap_admin(
    email="designer-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-D1",
  )
  dept_service = DepartmentService(db_session)
  root = await dept_service.create_department(actor=admin, name="根", code="root-d1", parent_id=None)
  copy = await dept_service.create_department(
    actor=admin,
    name="文案",
    code="video-copywriting",
    parent_id=root.id,
  )
  await WorkflowVideoTemplateSeedService(db_session).seed_templates(
    actor=admin,
    departments={"video-copywriting": copy, "video-voice": copy, "video-post": copy},
  )
  await db_session.commit()
  template = await db_session.scalar(
    select(WorkflowGraphTemplate).where(WorkflowGraphTemplate.code == "topic_meeting_batch_v1")
  )
  assert template is not None
  return admin, template


@pytest.mark.asyncio
async def test_d1_clone_template_creates_draft(db_session) -> None:
  admin, source = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)

  cloned = await service.create_template(
    actor=admin,
    payload=WorkflowGraphTemplateCreateRequest(clone_from_id=source.id, name="选题会副本"),
  )
  source_node_count = await db_session.scalar(
    select(func.count())
    .select_from(WorkflowGraphTemplateNode)
    .where(WorkflowGraphTemplateNode.template_id == source.id)
  )
  assert cloned.status == WorkflowGraphTemplateStatus.DRAFT
  assert cloned.version == source.version + 1
  assert cloned.base_code == source.base_code
  assert len(cloned.nodes) == int(source_node_count or 0)
  assert cloned.source_template_id == source.id


@pytest.mark.asyncio
async def test_d1_save_draft_updates_config_and_nodes(db_session) -> None:
  admin, source = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)
  draft = await service.create_template(
    actor=admin,
    payload=WorkflowGraphTemplateCreateRequest(clone_from_id=source.id),
  )

  first_node = draft.nodes[0]
  updated_nodes = [
    WorkflowGraphTemplateNodeDraftWrite(
      node_key=node.node_key,
      title=node.title,
      sort_order=node.sort_order,
      assignee_rule=node.assignee_rule,
      config=node.config,
    )
    for node in draft.nodes
  ]
  updated_nodes[0] = WorkflowGraphTemplateNodeDraftWrite(
    node_key=first_node.node_key,
    title=first_node.title,
    sort_order=first_node.sort_order,
    assignee_rule=first_node.assignee_rule,
    config={
      **first_node.config,
      "capture_schema": {
        **dict(first_node.config.get("capture_schema") or {}),
        "max_rows": 5,
      },
    },
  )
  config = dict(draft.config)
  config["aggregate_mode"] = "streaming"

  saved = await service.save_draft(
    actor=admin,
    template_id=draft.id,
    payload=WorkflowGraphTemplateDraftSaveRequest(
      name="选题会 streaming",
      description="D1 测试",
      config=config,
      nodes=updated_nodes,
    ),
  )
  assert saved.config.get("aggregate_mode") == "streaming"
  assert saved.nodes[0].config.get("capture_schema", {}).get("max_rows") == 5


@pytest.mark.asyncio
async def test_d1_validate_and_publish(db_session) -> None:
  admin, source = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)
  draft = await service.create_template(
    actor=admin,
    payload=WorkflowGraphTemplateCreateRequest(clone_from_id=source.id),
  )

  validation = await service.validate_template(template_id=draft.id)
  assert validation.valid is True

  published = await service.update_status(
    actor=admin,
    template_id=draft.id,
    payload=WorkflowGraphTemplateStatusUpdateRequest(status=WorkflowGraphTemplateStatus.ACTIVE),
  )
  assert published.status == WorkflowGraphTemplateStatus.ACTIVE

  archived_source = await db_session.get(WorkflowGraphTemplate, source.id)
  assert archived_source is not None
  assert archived_source.status == WorkflowGraphTemplateStatus.ARCHIVED


@pytest.mark.asyncio
async def test_d1_structure_locked_when_instances_exist(db_session) -> None:
  admin, source = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)
  db_session.add(
    WorkflowGraphInstance(
      template_id=source.id,
      initiator_user_id=admin.id,
      context={},
    )
  )
  await db_session.commit()

  designer = await service.get_designer_detail(template_id=source.id)
  assert designer.has_instances is True
  assert designer.structure_locked is True

  detail = await service.update_template(
    actor=admin,
    template_id=source.id,
    payload=WorkflowGraphTemplateUpdateRequest(description="仍有实例但可改说明"),
  )
  assert detail.description == "仍有实例但可改说明"
