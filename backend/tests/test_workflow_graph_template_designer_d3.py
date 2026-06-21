"""D3 graph template designer: export/import, dry-run, stats."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import WorkflowGraphInstance, WorkflowGraphTemplate
from app.schemas.workflow_graph import WorkflowGraphTemplateImportRequest
from app.services.workflow_graph_template_admin_service import WorkflowGraphTemplateAdminService
from tests.test_workflow_graph_template_designer_d1 import _seed_batch_template


@pytest.mark.asyncio
async def test_d3_export_import_roundtrip(db_session) -> None:
  admin, source = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)
  bundle = await service.export_template(actor=admin, template_id=source.id)
  assert bundle.format_version == 1
  assert len(bundle.template.nodes) >= 2

  imported = await service.import_template_new(
    actor=admin,
    payload=WorkflowGraphTemplateImportRequest(bundle=bundle),
    name="导入副本",
  )
  assert imported.name == "导入副本"
  assert imported.status == "draft"
  assert len(imported.nodes) == len(bundle.template.nodes)


@pytest.mark.asyncio
async def test_d3_dry_run_batch_template(db_session) -> None:
  admin, source = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)
  from app.schemas.workflow_graph import WorkflowGraphTemplateDryRunRequest

  result = await service.dry_run_template(
    actor=admin,
    template_id=source.id,
    payload=WorkflowGraphTemplateDryRunRequest(
      inputs={"theme": "试跑", "manager_user_id": str(admin.id)},
    ),
  )
  assert result.valid is True
  assert result.schema_snapshot.get("template_code") == source.code
  assert "N1_PROPOSE" in result.entry_node_keys


@pytest.mark.asyncio
async def test_d3_template_stats(db_session) -> None:
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

  stats = await service.get_template_stats(template_id=source.id)
  assert stats.run_count_total == 1
  assert stats.run_count_30d == 1
