"""Upsert workflow video v1 graph templates (W6)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import WorkflowGraphTemplateStatus
from app.models import User, WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode
from app.services.workflow_video_template_seed_data import (
  SEED_VERSION,
  TOPIC_MEETING_BATCH_CODE,
  VIDEO_PRODUCTION_CODE,
  build_production_edges,
  build_production_nodes,
  build_production_template_config,
  build_topic_meeting_batch_config,
  build_topic_meeting_edges,
  build_topic_meeting_nodes,
)

VIDEO_DEPARTMENT_CODES = ("video-copywriting", "video-voice", "video-post")


@dataclass(frozen=True, slots=True)
class WorkflowVideoTemplateSeedResult:
  batch_template_id: UUID
  production_template_id: UUID
  batch_created: bool
  production_created: bool
  batch_nodes_rebuilt: bool
  production_nodes_rebuilt: bool


class WorkflowVideoTemplateSeedService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def seed_templates(
    self,
    *,
    actor: User,
    departments: dict[str, object],
  ) -> WorkflowVideoTemplateSeedResult:
    missing = [code for code in VIDEO_DEPARTMENT_CODES if code not in departments]
    if missing:
      raise ValueError(
        f"缺少视频工作流部门种子：{', '.join(missing)}。请先运行 seed_sample_data 或补齐 sample 部门。"
      )

    copywriting_id = departments["video-copywriting"].id
    voice_id = departments["video-voice"].id
    post_id = departments["video-post"].id

    batch_result = await self._upsert_template(
      actor=actor,
      code=TOPIC_MEETING_BATCH_CODE,
      name="选题会（批次）",
      config=build_topic_meeting_batch_config(copywriting_department_id=copywriting_id),
      nodes=build_topic_meeting_nodes(),
      edges=build_topic_meeting_edges(),
    )
    production_result = await self._upsert_template(
      actor=actor,
      code=VIDEO_PRODUCTION_CODE,
      name="单题视频制作",
      config=build_production_template_config(
        copywriting_department_id=copywriting_id,
        voice_department_id=voice_id,
        post_department_id=post_id,
      ),
      nodes=build_production_nodes(),
      edges=build_production_edges(),
    )
    await self._session.commit()
    return WorkflowVideoTemplateSeedResult(
      batch_template_id=batch_result.template_id,
      production_template_id=production_result.template_id,
      batch_created=batch_result.created,
      production_created=production_result.created,
      batch_nodes_rebuilt=batch_result.nodes_rebuilt,
      production_nodes_rebuilt=production_result.nodes_rebuilt,
    )

  @dataclass(frozen=True, slots=True)
  class _UpsertResult:
    template_id: UUID
    created: bool
    nodes_rebuilt: bool

  async def _upsert_template(
    self,
    *,
    actor: User,
    code: str,
    name: str,
    config: dict,
    nodes: list[dict],
    edges: list[tuple[str, str, bool]],
  ) -> _UpsertResult:
    template = await self._session.scalar(select(WorkflowGraphTemplate).where(WorkflowGraphTemplate.code == code))
    created = template is None
    nodes_rebuilt = False

    if template is None:
      template = WorkflowGraphTemplate(
        code=code,
        base_code=code,
        version=1,
        name=name,
        status=WorkflowGraphTemplateStatus.ACTIVE,
        config=config,
        context_schema={},
        created_by=actor.id,
      )
      self._session.add(template)
      await self._session.flush()
      nodes_rebuilt = True
    else:
      current_version = int(template.config.get("seed_version") or 0)
      if current_version != SEED_VERSION:
        await self._session.execute(
          delete(WorkflowGraphTemplateEdge).where(WorkflowGraphTemplateEdge.template_id == template.id)
        )
        await self._session.execute(
          delete(WorkflowGraphTemplateNode).where(WorkflowGraphTemplateNode.template_id == template.id)
        )
        nodes_rebuilt = True
      template.name = name
      template.status = WorkflowGraphTemplateStatus.ACTIVE
      template.config = config

    if nodes_rebuilt or created:
      node_by_key = await self._create_nodes(template_id=template.id, node_specs=nodes)
      await self._create_edges(template_id=template.id, edge_specs=edges, node_by_key=node_by_key)

    await self._session.flush()
    return self._UpsertResult(template_id=template.id, created=created, nodes_rebuilt=nodes_rebuilt)

  async def _create_nodes(self, *, template_id: UUID, node_specs: list[dict]) -> dict[str, WorkflowGraphTemplateNode]:
    node_by_key: dict[str, WorkflowGraphTemplateNode] = {}
    for spec in node_specs:
      node = WorkflowGraphTemplateNode(
        template_id=template_id,
        node_key=spec["node_key"],
        title=spec["title"],
        sort_order=spec["sort_order"],
        assignee_rule=spec.get("assignee_rule") or {},
        config=spec.get("config") or {},
      )
      self._session.add(node)
      node_by_key[spec["node_key"]] = node
    await self._session.flush()
    return node_by_key

  async def _create_edges(
    self,
    *,
    template_id: UUID,
    edge_specs: list[tuple[str, str, bool]],
    node_by_key: dict[str, WorkflowGraphTemplateNode],
  ) -> None:
    for from_key, to_key, is_reject in edge_specs:
      from_node = node_by_key[from_key]
      to_node = node_by_key[to_key]
      self._session.add(
        WorkflowGraphTemplateEdge(
          template_id=template_id,
          from_node_id=from_node.id,
          to_node_id=to_node.id,
          is_reject_path=is_reject,
        )
      )
    await self._session.flush()
