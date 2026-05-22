"""Minimal graph template read/update for video v1 maintenance (W9-2)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.models import User, WorkflowGraphTemplate, WorkflowGraphTemplateNode
from app.schemas.workflow_graph import (
  WorkflowGraphTemplateDetailRead,
  WorkflowGraphTemplateNodeSummaryRead,
  WorkflowGraphTemplateUpdateRequest,
)
from app.services.access_control import can_manage_task_templates, ensure_active_user


class WorkflowGraphTemplateAdminService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def get_template_detail(self, *, template_id: UUID) -> WorkflowGraphTemplateDetailRead:
    template = await self._session.get(WorkflowGraphTemplate, template_id)
    if template is None:
      raise NotFoundError("工作流图模板不存在。")

    nodes = list(
      await self._session.scalars(
        select(WorkflowGraphTemplateNode)
        .where(WorkflowGraphTemplateNode.template_id == template_id)
        .order_by(WorkflowGraphTemplateNode.sort_order.asc())
      )
    )
    config = dict(template.config or {})
    return WorkflowGraphTemplateDetailRead(
      id=template.id,
      code=template.code,
      name=template.name,
      description=template.description,
      status=template.status,
      version=template.version,
      run_kind=str(config.get("run_kind") or "") or None,
      config=config,
      nodes=[
        WorkflowGraphTemplateNodeSummaryRead(
          id=node.id,
          node_key=node.node_key,
          title=node.title,
          sort_order=node.sort_order,
        )
        for node in nodes
      ],
    )

  async def update_template(
    self,
    *,
    actor: User,
    template_id: UUID,
    payload: WorkflowGraphTemplateUpdateRequest,
  ) -> WorkflowGraphTemplateDetailRead:
    ensure_active_user(actor)
    if not await can_manage_task_templates(self._session, actor):
      raise AuthorizationError("当前账号无权维护图模板。")

    template = await self._session.get(WorkflowGraphTemplate, template_id)
    if template is None:
      raise NotFoundError("工作流图模板不存在。")

    if payload.name is not None:
      template.name = payload.name.strip()
    if payload.description is not None:
      template.description = payload.description.strip() or None
    if payload.config is not None:
      template.config = {**dict(template.config or {}), **payload.config}

    await self._session.flush()
    return await self.get_template_detail(template_id=template_id)
