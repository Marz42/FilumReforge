"""D2 graph template designer: edges, modes, topology validation."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.enums import WorkflowGraphTemplateStatus
from app.models import WorkflowGraphTemplate
from app.schemas.workflow_graph import (
  WorkflowGraphTemplateCreateRequest,
  WorkflowGraphTemplateDraftSaveRequest,
  WorkflowGraphTemplateEdgeDraftWrite,
  WorkflowGraphTemplateNodeDraftWrite,
)
from app.services.workflow_graph_template_admin_service import WorkflowGraphTemplateAdminService
from app.services.workflow_video_template_seed_service import WorkflowVideoTemplateSeedService
from tests.test_workflow_graph_template_designer_d1 import TEST_JWT_SECRET, _seed_batch_template


@pytest.mark.asyncio
async def test_d2_designer_includes_edges(db_session) -> None:
  admin, source = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)
  designer = await service.get_designer_detail(template_id=source.id)
  assert len(designer.edges) >= 1
  assert designer.edges[0].from_node_key == "N1_PROPOSE"
  assert designer.edges[0].to_node_key == "N2_AGGREGATE"


@pytest.mark.asyncio
async def test_d2_save_draft_persists_edges_and_modes(db_session) -> None:
  admin, source = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)
  draft = await service.create_template(
    actor=admin,
    payload=WorkflowGraphTemplateCreateRequest(clone_from_id=source.id),
  )

  nodes = [
    WorkflowGraphTemplateNodeDraftWrite(
      node_key=node.node_key,
      title=node.title,
      sort_order=node.sort_order,
      assignment_mode=node.assignment_mode,
      join_mode=node.join_mode,
      assignee_rule=node.assignee_rule,
      config=node.config,
    )
    for node in draft.nodes
  ]
  edges = [
    WorkflowGraphTemplateEdgeDraftWrite(
      from_node_key=edge.from_node_key,
      to_node_key=edge.to_node_key,
      is_reject_path=edge.is_reject_path,
      condition=edge.condition,
      priority=edge.priority,
    )
    for edge in draft.edges
  ]

  saved = await service.save_draft(
    actor=admin,
    template_id=draft.id,
    payload=WorkflowGraphTemplateDraftSaveRequest(
      name=draft.name,
      config=dict(draft.config or {}),
      nodes=nodes,
      edges=edges,
    ),
  )
  assert len(saved.edges) == len(edges)
  assert saved.nodes[0].assignment_mode == "single"


@pytest.mark.asyncio
async def test_d2_validate_production_reject_edges(db_session) -> None:
  admin, _ = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)
  production = await db_session.scalar(
    select(WorkflowGraphTemplate).where(WorkflowGraphTemplate.code == "video_production_per_topic_v1")
  )
  assert production is not None

  validation = await service.validate_template(template_id=production.id)
  assert validation.valid is True


@pytest.mark.asyncio
async def test_d2_validate_detects_missing_reject_edge(db_session) -> None:
  admin, source = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)
  draft = await service.create_template(
    actor=admin,
    payload=WorkflowGraphTemplateCreateRequest(
      clone_from_id=(
        await db_session.scalar(
          select(WorkflowGraphTemplate).where(
            WorkflowGraphTemplate.code == "video_production_per_topic_v1"
          )
        )
      ).id,
    ),
  )

  broken_edges = [
    WorkflowGraphTemplateEdgeDraftWrite(
      from_node_key=edge.from_node_key,
      to_node_key=edge.to_node_key,
      is_reject_path=False,
      condition=edge.condition,
      priority=edge.priority,
    )
    for edge in draft.edges
  ]

  await service.save_draft(
    actor=admin,
    template_id=draft.id,
    payload=WorkflowGraphTemplateDraftSaveRequest(
      name=draft.name,
      config=dict(draft.config or {}),
      nodes=[
        WorkflowGraphTemplateNodeDraftWrite(
          node_key=node.node_key,
          title=node.title,
          sort_order=node.sort_order,
          assignment_mode=node.assignment_mode,
          join_mode=node.join_mode,
          assignee_rule=node.assignee_rule,
          config=node.config,
        )
        for node in draft.nodes
      ],
      edges=broken_edges,
    ),
  )

  validation = await service.validate_template(template_id=draft.id)
  assert validation.valid is False
  assert any("reject 边" in item for item in validation.errors)
