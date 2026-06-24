"""F-23: generic workflow graph template chain tests."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.enums import WorkflowGraphInstanceStatus, WorkflowGraphTemplateStatus, WorkflowNodeEngineState
from app.models import WorkflowGraphInstance, WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode
from app.services.auth_service import AuthService
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_graph_template_admin_service import WorkflowGraphTemplateAdminService
from app.schemas.workflow_graph import WorkflowGraphTemplateStatusUpdateRequest

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


async def _seed_admin(db_session):
  auth = AuthService(db_session, Settings(jwt_secret_key=TEST_JWT_SECRET))
  return await auth.bootstrap_admin(
    email="f23-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-F23",
  )


async def _create_two_node_template(
  db_session,
  *,
  admin,
  code: str,
  name: str,
  on_complete: dict | None = None,
  status: WorkflowGraphTemplateStatus = WorkflowGraphTemplateStatus.ACTIVE,
) -> WorkflowGraphTemplate:
  config: dict = {}
  if on_complete is not None:
    config["on_complete"] = on_complete
  template = WorkflowGraphTemplate(
    code=code,
    base_code=code,
    version=1,
    name=name,
    status=status,
    config=config,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_a = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="STEP_A",
    title="步骤 A",
    sort_order=1,
  )
  node_b = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="STEP_B",
    title="步骤 B",
    sort_order=2,
  )
  db_session.add_all([node_a, node_b])
  await db_session.flush()
  db_session.add(
    WorkflowGraphTemplateEdge(
      template_id=template.id,
      from_node_id=node_a.id,
      to_node_id=node_b.id,
    )
  )
  await db_session.flush()
  return template


@pytest.mark.asyncio
async def test_f23_run_completion_triggers_next_template(db_session) -> None:
  admin = await _seed_admin(db_session)
  downstream = await _create_two_node_template(
    db_session,
    admin=admin,
    code="chain_downstream_v1",
    name="下游模板",
  )
  upstream = await _create_two_node_template(
    db_session,
    admin=admin,
    code="chain_upstream_v1",
    name="上游模板",
    on_complete={"next_template_code": downstream.base_code, "carry_inputs": True},
  )

  graph = WorkflowGraphService(db_session)
  result = await graph.create_multi_node_instance(
    template_id=upstream.id,
    initiator_id=admin.id,
    context={"inputs": {"note": "carry-me"}},
  )
  ni_a = next(ni for ni in result.node_instances if ni.node_key == "STEP_A")
  ni_b = next(ni for ni in result.node_instances if ni.node_key == "STEP_B")

  await graph.complete_node_instance(node_instance_id=ni_a.id, actor_id=admin.id)
  await db_session.refresh(ni_b)
  await graph.complete_node_instance(node_instance_id=ni_b.id, actor_id=admin.id)
  await db_session.refresh(result.instance)

  assert result.instance.status == WorkflowGraphInstanceStatus.COMPLETED
  parent_context = result.instance.context or {}
  assert parent_context.get("on_complete_triggered") is True

  child = await db_session.scalar(
    select(WorkflowGraphInstance).where(
      WorkflowGraphInstance.parent_instance_id == result.instance.id,
    )
  )
  assert child is not None
  assert child.template_id == downstream.id
  child_context = child.context or {}
  assert child_context.get("chained_from_instance_id") == str(result.instance.id)
  assert child_context.get("inputs") == {"note": "carry-me"}


@pytest.mark.asyncio
async def test_f23_publish_rejects_template_chain_cycle(db_session) -> None:
  admin = await _seed_admin(db_session)
  template_a = await _create_two_node_template(
    db_session,
    admin=admin,
    code="cycle_a_v1",
    name="模板 A",
    on_complete={"next_template_code": "cycle_b_v1"},
  )
  template_b = await _create_two_node_template(
    db_session,
    admin=admin,
    code="cycle_b_v1",
    name="模板 B",
    on_complete={"next_template_code": "cycle_a_v1"},
    status=WorkflowGraphTemplateStatus.DRAFT,
  )

  admin_service = WorkflowGraphTemplateAdminService(db_session)
  validation = await admin_service.validate_template(template_id=template_b.id)
  assert validation.valid is False
  assert any("环路" in error for error in validation.errors)

  with pytest.raises(Exception) as exc_info:
    await admin_service.update_status(
      actor=admin,
      template_id=template_b.id,
      payload=WorkflowGraphTemplateStatusUpdateRequest(status=WorkflowGraphTemplateStatus.ACTIVE),
    )
  assert "环路" in str(exc_info.value) or "校验" in str(exc_info.value)


@pytest.mark.asyncio
async def test_f23_runtime_guard_skips_cycle(db_session) -> None:
  admin = await _seed_admin(db_session)
  template = await _create_two_node_template(
    db_session,
    admin=admin,
    code="self_guard_v1",
    name="自环守卫",
    on_complete={"next_template_code": "self_guard_v1"},
  )

  graph = WorkflowGraphService(db_session)
  result = await graph.create_multi_node_instance(
    template_id=template.id,
    initiator_id=admin.id,
    context={"template_chain_ancestor_codes": ["self_guard_v1"]},
  )
  for ni in result.node_instances:
    if ni.engine_state == WorkflowNodeEngineState.ACTIVATED:
      await graph.complete_node_instance(node_instance_id=ni.id, actor_id=admin.id)
      await db_session.refresh(ni)

  children = list(
    await db_session.scalars(
      select(WorkflowGraphInstance).where(
        WorkflowGraphInstance.parent_instance_id == result.instance.id,
      )
    )
  )
  assert children == []
