import pytest

from app.core.enums import WorkflowGraphTemplateStatus
from app.core.exceptions import ConflictError
from app.schemas.workflow_graph import WorkflowGraphTemplateStatusUpdateRequest
from app.services.workflow_graph_template_admin_service import WorkflowGraphTemplateAdminService
from test_workflow_graph_template_designer_d1 import _seed_batch_template


@pytest.mark.asyncio
async def test_active_template_tags_patch(db_session) -> None:
  admin, source = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)
  await service.update_tags(actor=admin, template_id=source.id, tags=["视频", "周会"])
  detail = await service.get_template_detail(template_id=source.id)
  assert detail.tags == ["视频", "周会"]


@pytest.mark.asyncio
async def test_archived_template_tags_rejected(db_session) -> None:
  admin, source = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)
  await service.update_status(
    actor=admin,
    template_id=source.id,
    payload=WorkflowGraphTemplateStatusUpdateRequest(status=WorkflowGraphTemplateStatus.ARCHIVED),
  )
  with pytest.raises(ConflictError, match="已归档"):
    await service.update_tags(actor=admin, template_id=source.id, tags=["x"])
