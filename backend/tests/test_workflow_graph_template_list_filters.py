import pytest

from app.core.enums import WorkflowGraphTemplateStatus
from app.schemas.workflow_graph import WorkflowGraphTemplateStatusUpdateRequest
from app.services.workflow_graph_template_admin_service import WorkflowGraphTemplateAdminService
from test_workflow_graph_template_designer_d1 import _seed_batch_template


@pytest.mark.asyncio
async def test_list_includes_archived_when_requested(db_session) -> None:
  admin, source = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)
  await service.update_status(
    actor=admin,
    template_id=source.id,
    payload=WorkflowGraphTemplateStatusUpdateRequest(status=WorkflowGraphTemplateStatus.ARCHIVED),
  )
  default_list = await service.list_manageable_templates()
  assert all(t.status != WorkflowGraphTemplateStatus.ARCHIVED for t in default_list)
  with_archived = await service.list_manageable_templates(
    status_filter=[
      WorkflowGraphTemplateStatus.DRAFT,
      WorkflowGraphTemplateStatus.ACTIVE,
      WorkflowGraphTemplateStatus.ARCHIVED,
    ],
  )
  assert any(t.id == source.id and t.status == WorkflowGraphTemplateStatus.ARCHIVED for t in with_archived)


@pytest.mark.asyncio
async def test_list_q_matches_name_or_code(db_session) -> None:
  admin, source = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)
  hits = await service.list_manageable_templates(q="topic_meeting")
  assert any(t.id == source.id for t in hits)
  misses = await service.list_manageable_templates(q="zzzz-no-match-zzzz")
  assert not any(t.id == source.id for t in misses)
