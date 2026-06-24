"""W6 tests: workflow video graph template + sample department seed."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.enums import DepartmentCapability, WorkflowGraphTemplateStatus
from app.models import Department, WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode
from app.services.access_control import can_publish_org_tasks
from app.services.sample_data_service import SampleDataService
from app.services.workflow_video_template_seed_data import (
  SEED_VERSION,
  TOPIC_MEETING_BATCH_CODE,
  VIDEO_PRODUCTION_CODE,
)
from app.services.workflow_video_template_seed_service import WorkflowVideoTemplateSeedService

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


@pytest.mark.asyncio
async def test_w6_seed_templates_idempotent(db_session) -> None:
  service = SampleDataService(db_session, Settings(jwt_secret_key=TEST_JWT_SECRET))
  result = await service.seed_manual_test_workspace(default_password="StrongPassword123!")
  await db_session.commit()

  batch = await db_session.scalar(
    select(WorkflowGraphTemplate).where(WorkflowGraphTemplate.code == TOPIC_MEETING_BATCH_CODE)
  )
  production = await db_session.scalar(
    select(WorkflowGraphTemplate).where(WorkflowGraphTemplate.code == VIDEO_PRODUCTION_CODE)
  )
  assert batch is not None and batch.status == WorkflowGraphTemplateStatus.ACTIVE
  assert production is not None and production.status == WorkflowGraphTemplateStatus.ACTIVE
  assert batch.config.get("seed_version") == SEED_VERSION
  assert production.config.get("seed_version") == SEED_VERSION

  batch_nodes = (
    await db_session.scalars(
      select(WorkflowGraphTemplateNode)
      .where(WorkflowGraphTemplateNode.template_id == batch.id)
      .order_by(WorkflowGraphTemplateNode.sort_order)
    )
  ).all()
  assert [node.node_key for node in batch_nodes] == ["N1_PROPOSE", "N2_AGGREGATE"]
  assert batch_nodes[1].config.get("aggregate_schema", {}).get("assignee_column", {}).get("key") == "script_author_id"

  production_nodes = (
    await db_session.scalars(
      select(WorkflowGraphTemplateNode)
      .where(WorkflowGraphTemplateNode.template_id == production.id)
      .order_by(WorkflowGraphTemplateNode.sort_order)
    )
  ).all()
  assert len(production_nodes) == 10
  assert production_nodes[0].node_key == "N3_SCRIPT_WRITE"
  assert production_nodes[-1].node_key == "N12_COSIGN"
  assert any(node.node_key == "N5_VO_UPLOAD" for node in production_nodes)
  assert not any(node.node_key == "N6_VO_REVIEW" for node in production_nodes)

  edge_count = await db_session.scalar(
    select(func.count())
    .select_from(WorkflowGraphTemplateEdge)
    .where(WorkflowGraphTemplateEdge.template_id == production.id)
  )
  assert edge_count == 11

  copy_dept = await db_session.scalar(select(Department).where(Department.code == "video-copywriting"))
  assert copy_dept is not None
  assert DepartmentCapability.PUBLISH_ORG_TASK.value in copy_dept.capabilities
  from app.models import User

  assert any(account.email == "demo.video.copy.lead@example.com" for account in result.accounts)

  lead_user = await db_session.scalar(select(User).where(User.email == "demo.video.copy.lead@example.com"))
  assert lead_user is not None
  assert await can_publish_org_tasks(db_session, lead_user)

  policy_dept_id = batch.config["participant_policies"]["copywriters"]["department_id"]
  pools = production.config["department_pools"]
  assert policy_dept_id == str(copy_dept.id)
  assert pools["copywriters"] == str(copy_dept.id)
  assert pools["voice_over"] == str(
    (await db_session.scalar(select(Department).where(Department.code == "video-voice"))).id
  )

  second = await WorkflowVideoTemplateSeedService(db_session).seed_templates(
    actor=lead_user,
    departments={
      "video-copywriting": copy_dept,
      "video-voice": await db_session.scalar(select(Department).where(Department.code == "video-voice")),
      "video-post": await db_session.scalar(select(Department).where(Department.code == "video-post")),
    },
  )
  assert second.batch_nodes_rebuilt is False
  assert second.production_nodes_rebuilt is False
  assert second.batch_topology_synced_in_place is False
  assert second.production_topology_synced_in_place is False


@pytest.mark.asyncio
async def test_w6_seed_refresh_syncs_in_place_when_node_instances_exist(db_session) -> None:
  from app.core.enums import (
    WorkflowGraphInstanceStatus,
    WorkflowGraphNodeType,
    WorkflowNodeBusinessState,
    WorkflowNodeEngineState,
  )
  from app.models import User, WorkflowGraphInstance, WorkflowNodeInstance

  service = SampleDataService(db_session, Settings(jwt_secret_key=TEST_JWT_SECRET))
  await service.seed_manual_test_workspace(default_password="StrongPassword123!")
  await db_session.commit()

  batch = await db_session.scalar(
    select(WorkflowGraphTemplate).where(WorkflowGraphTemplate.code == TOPIC_MEETING_BATCH_CODE)
  )
  assert batch is not None
  batch_node = await db_session.scalar(
    select(WorkflowGraphTemplateNode).where(
      WorkflowGraphTemplateNode.template_id == batch.id,
      WorkflowGraphTemplateNode.node_key == "N1_PROPOSE",
    )
  )
  assert batch_node is not None
  original_node_id = batch_node.id

  lead_user = await db_session.scalar(select(User).where(User.email == "demo.video.copy.lead@example.com"))
  copy_dept = await db_session.scalar(select(Department).where(Department.code == "video-copywriting"))
  assert lead_user is not None and copy_dept is not None

  batch.config = {**(batch.config or {}), "seed_version": 1}
  graph_instance = WorkflowGraphInstance(
    template_id=batch.id,
    initiator_user_id=lead_user.id,
    department_id=copy_dept.id,
    source_type="template",
    status=WorkflowGraphInstanceStatus.ACTIVE,
    context={"run_kind": "batch"},
    context_version=1,
    max_iterations=5,
  )
  db_session.add(graph_instance)
  await db_session.flush()
  db_session.add(
    WorkflowNodeInstance(
      instance_id=graph_instance.id,
      template_node_id=batch_node.id,
      node_key="N1_PROPOSE",
      title="提交选题",
      node_type=WorkflowGraphNodeType.TASK,
      engine_state=WorkflowNodeEngineState.ACTIVATED,
      business_state=WorkflowNodeBusinessState.DOING,
      assignee_user_id=lead_user.id,
      iteration=1,
      node_instance_version=1,
      config={},
    )
  )
  await db_session.commit()

  refreshed = await WorkflowVideoTemplateSeedService(db_session).seed_templates(
    actor=lead_user,
    departments={
      "video-copywriting": copy_dept,
      "video-voice": await db_session.scalar(select(Department).where(Department.code == "video-voice")),
      "video-post": await db_session.scalar(select(Department).where(Department.code == "video-post")),
    },
  )
  assert refreshed.batch_topology_synced_in_place is True
  assert refreshed.batch_nodes_rebuilt is False

  await db_session.refresh(batch)
  assert batch.config.get("seed_version") == SEED_VERSION

  preserved_node = await db_session.scalar(
    select(WorkflowGraphTemplateNode).where(WorkflowGraphTemplateNode.id == original_node_id)
  )
  assert preserved_node is not None
  assert preserved_node.node_key == "N1_PROPOSE"
