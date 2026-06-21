"""Graph template read/update and D1 designer authoring."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import WorkflowGraphTemplateStatus
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models import (
  User,
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateEdge,
  WorkflowGraphTemplateNode,
)
from app.schemas.workflow_graph import (
  WorkflowGraphTemplateCreateRequest,
  WorkflowGraphTemplateDesignerRead,
  WorkflowGraphTemplateDetailRead,
  WorkflowGraphTemplateDraftSaveRequest,
  WorkflowGraphTemplateEdgeDetailRead,
  WorkflowGraphTemplateNodeDetailRead,
  WorkflowGraphTemplateNodeSummaryRead,
  WorkflowGraphTemplateStatusUpdateRequest,
  WorkflowGraphTemplateUpdateRequest,
  WorkflowGraphTemplateValidateResponse,
)
from app.schemas.workflow_video import validate_launch_schema, validate_node_config
from app.services.access_control import can_manage_task_templates, ensure_active_user
from app.services.workflow_graph_template_topology import (
  GraphTemplateEdgeSpec,
  GraphTemplateNodeSpec,
  validate_graph_template_topology,
)

_CODE_VERSION_SUFFIX = re.compile(r"_v(\d+)$")


class WorkflowGraphTemplateAdminService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def list_manageable_templates(self) -> list[WorkflowGraphTemplate]:
    return list(
      await self._session.scalars(
        select(WorkflowGraphTemplate)
        .where(
          WorkflowGraphTemplate.status.in_(
            (WorkflowGraphTemplateStatus.DRAFT, WorkflowGraphTemplateStatus.ACTIVE)
          )
        )
        .order_by(WorkflowGraphTemplate.base_code.asc(), WorkflowGraphTemplate.version.desc())
      )
    )

  async def get_template_detail(self, *, template_id: UUID) -> WorkflowGraphTemplateDetailRead:
    template = await self._get_template_or_raise(template_id=template_id)
    nodes = await self._load_node_summaries(template_id=template_id)
    return self._build_detail_read(template=template, nodes=nodes)

  async def get_designer_detail(self, *, template_id: UUID) -> WorkflowGraphTemplateDesignerRead:
    template = await self._get_template_or_raise(template_id=template_id)
    nodes = await self._load_node_details(template_id=template_id)
    edges = await self._load_edge_details(template_id=template_id)
    has_instances = await self._has_instances(template_id=template_id)
    return self._build_designer_read(
      template=template,
      nodes=nodes,
      edges=edges,
      has_instances=has_instances,
    )

  async def create_template(
    self,
    *,
    actor: User,
    payload: WorkflowGraphTemplateCreateRequest,
  ) -> WorkflowGraphTemplateDesignerRead:
    await self._ensure_manage(actor)
    source = await self._get_template_or_raise(template_id=payload.clone_from_id)
    return await self._fork_template(
      actor=actor,
      source=source,
      name=payload.name.strip() if payload.name else f"{source.name}（副本）",
    )

  async def fork_template_version(
    self,
    *,
    actor: User,
    template_id: UUID,
  ) -> WorkflowGraphTemplateDesignerRead:
    await self._ensure_manage(actor)
    source = await self._get_template_or_raise(template_id=template_id)
    return await self._fork_template(actor=actor, source=source, name=source.name)

  async def save_draft(
    self,
    *,
    actor: User,
    template_id: UUID,
    payload: WorkflowGraphTemplateDraftSaveRequest,
  ) -> WorkflowGraphTemplateDesignerRead:
    await self._ensure_manage(actor)
    template = await self._get_template_or_raise(template_id=template_id)
    if template.status != WorkflowGraphTemplateStatus.DRAFT:
      raise ConflictError("仅 draft 模板可整包保存。")

    has_instances = await self._has_instances(template_id=template_id)
    structure_locked = has_instances

    template.name = payload.name.strip()
    template.description = payload.description.strip() if payload.description else None
    template.config = dict(payload.config or {})

    if not structure_locked:
      if not payload.nodes:
        raise ConflictError("模板至少需要一个节点。")
      await self._replace_structure(
        template=template,
        node_payloads=payload.nodes,
        edge_payloads=payload.edges,
      )
    elif payload.nodes or payload.edges:
      raise ConflictError("已有运行实例的模板不可修改节点结构。")

    await self._session.flush()
    return await self.get_designer_detail(template_id=template_id)

  async def update_template(
    self,
    *,
    actor: User,
    template_id: UUID,
    payload: WorkflowGraphTemplateUpdateRequest,
  ) -> WorkflowGraphTemplateDetailRead:
    await self._ensure_manage(actor)
    template = await self._get_template_or_raise(template_id=template_id)

    if payload.name is not None:
      template.name = payload.name.strip()
    if payload.description is not None:
      template.description = payload.description.strip() or None
    if payload.config is not None:
      template.config = {**dict(template.config or {}), **payload.config}

    await self._session.flush()
    return await self.get_template_detail(template_id=template_id)

  async def update_status(
    self,
    *,
    actor: User,
    template_id: UUID,
    payload: WorkflowGraphTemplateStatusUpdateRequest,
  ) -> WorkflowGraphTemplateDesignerRead:
    await self._ensure_manage(actor)
    template = await self._get_template_or_raise(template_id=template_id)
    target_status = payload.status

    if target_status == WorkflowGraphTemplateStatus.ACTIVE:
      validation = await self.validate_template(template_id=template_id)
      if not validation.valid:
        raise ConflictError("模板校验未通过，无法发布。" + "；".join(validation.errors[:3]))
      if template.status != WorkflowGraphTemplateStatus.DRAFT:
        raise ConflictError("仅 draft 模板可发布为 active。")
      await self._archive_sibling_active_templates(template=template)
      template.status = WorkflowGraphTemplateStatus.ACTIVE
    elif target_status == WorkflowGraphTemplateStatus.ARCHIVED:
      template.status = WorkflowGraphTemplateStatus.ARCHIVED
    elif target_status == WorkflowGraphTemplateStatus.DRAFT:
      if template.status == WorkflowGraphTemplateStatus.ACTIVE:
        raise ConflictError("已发布的 active 模板请通过另存新版本编辑，不可回退为 draft。")
      template.status = WorkflowGraphTemplateStatus.DRAFT
    else:
      template.status = target_status

    await self._session.flush()
    return await self.get_designer_detail(template_id=template_id)

  async def validate_template(self, *, template_id: UUID) -> WorkflowGraphTemplateValidateResponse:
    template = await self._get_template_or_raise(template_id=template_id)
    nodes = await self._load_node_details(template_id=template_id)
    edges = await self._load_edge_details(template_id=template_id)
    errors = self._collect_validation_errors(template=template, nodes=nodes, edges=edges)
    return WorkflowGraphTemplateValidateResponse(valid=not errors, errors=errors)

  async def _fork_template(
    self,
    *,
    actor: User,
    source: WorkflowGraphTemplate,
    name: str,
  ) -> WorkflowGraphTemplateDesignerRead:
    version = await self._get_next_template_version(base_code=source.base_code)
    code = self._derive_template_code(base_code=source.base_code, version=version)
    if await self._session.scalar(select(WorkflowGraphTemplate.id).where(WorkflowGraphTemplate.code == code)):
      raise ConflictError("模板编码冲突，请稍后重试。")

    source_nodes = list(
      await self._session.scalars(
        select(WorkflowGraphTemplateNode)
        .where(WorkflowGraphTemplateNode.template_id == source.id)
        .order_by(WorkflowGraphTemplateNode.sort_order.asc())
      )
    )
    source_edges = list(
      await self._session.scalars(
        select(WorkflowGraphTemplateEdge).where(WorkflowGraphTemplateEdge.template_id == source.id)
      )
    )

    template = WorkflowGraphTemplate(
      code=code,
      base_code=source.base_code,
      version=version,
      name=name.strip(),
      description=source.description,
      status=WorkflowGraphTemplateStatus.DRAFT,
      context_schema=dict(source.context_schema or {}),
      config=dict(source.config or {}),
      created_by=actor.id,
      source_template_id=source.id,
    )
    self._session.add(template)
    await self._session.flush()

    node_by_key: dict[str, WorkflowGraphTemplateNode] = {}
    for node in source_nodes:
      cloned = WorkflowGraphTemplateNode(
        template_id=template.id,
        node_key=node.node_key,
        title=node.title,
        description=node.description,
        node_type=node.node_type,
        assignment_mode=node.assignment_mode,
        join_mode=node.join_mode,
        assignee_rule=dict(node.assignee_rule or {}),
        config=dict(node.config or {}),
        sort_order=node.sort_order,
      )
      self._session.add(cloned)
      node_by_key[node.node_key] = cloned
    await self._session.flush()

    old_id_to_key = {node.id: node.node_key for node in source_nodes}
    for edge in source_edges:
      from_key = old_id_to_key.get(edge.from_node_id)
      to_key = old_id_to_key.get(edge.to_node_id)
      if from_key is None or to_key is None:
        continue
      from_node = node_by_key.get(from_key)
      to_node = node_by_key.get(to_key)
      if from_node is None or to_node is None:
        continue
      self._session.add(
        WorkflowGraphTemplateEdge(
          template_id=template.id,
          from_node_id=from_node.id,
          to_node_id=to_node.id,
          is_reject_path=edge.is_reject_path,
          condition=dict(edge.condition or {}),
          priority=int(edge.priority or 0),
        )
      )
    await self._session.flush()
    return await self.get_designer_detail(template_id=template.id)

  async def _replace_structure(
    self,
    *,
    template: WorkflowGraphTemplate,
    node_payloads: list[Any],
    edge_payloads: list[Any] | None,
  ) -> None:
    preserved_edge_specs: list[tuple[str, str, bool, dict[str, Any], int]] = []
    if edge_payloads is None:
      existing_edges = list(
        await self._session.scalars(
          select(WorkflowGraphTemplateEdge).where(WorkflowGraphTemplateEdge.template_id == template.id)
        )
      )
      existing_nodes = list(
        await self._session.scalars(
          select(WorkflowGraphTemplateNode).where(WorkflowGraphTemplateNode.template_id == template.id)
        )
      )
      old_id_to_key = {node.id: node.node_key for node in existing_nodes}
      for edge in existing_edges:
        from_key = old_id_to_key.get(edge.from_node_id)
        to_key = old_id_to_key.get(edge.to_node_id)
        if from_key and to_key:
          preserved_edge_specs.append(
            (
              from_key,
              to_key,
              bool(edge.is_reject_path),
              dict(edge.condition or {}),
              int(edge.priority or 0),
            )
          )
    else:
      for edge_payload in edge_payloads:
        preserved_edge_specs.append(
          (
            edge_payload.from_node_key.strip(),
            edge_payload.to_node_key.strip(),
            bool(edge_payload.is_reject_path),
            dict(edge_payload.condition or {}),
            int(edge_payload.priority or 0),
          )
        )

    await self._session.execute(
      delete(WorkflowGraphTemplateEdge).where(WorkflowGraphTemplateEdge.template_id == template.id)
    )
    await self._session.execute(
      delete(WorkflowGraphTemplateNode).where(WorkflowGraphTemplateNode.template_id == template.id)
    )
    await self._session.flush()

    node_by_key: dict[str, WorkflowGraphTemplateNode] = {}
    seen_keys: set[str] = set()
    for index, node_payload in enumerate(node_payloads, start=1):
      node_key = node_payload.node_key.strip()
      if node_key in seen_keys:
        raise ConflictError(f"节点键重复：{node_key}")
      seen_keys.add(node_key)

      assignment_mode = str(node_payload.assignment_mode or "single").strip().lower()
      join_mode = str(node_payload.join_mode or "all").strip().lower()
      if assignment_mode not in {"single", "fan_out"}:
        raise ConflictError(f"节点 {node_key} 的 assignment_mode 无效。")
      if join_mode not in {"all", "any"}:
        raise ConflictError(f"节点 {node_key} 的 join_mode 无效。")
      if assignment_mode == "single":
        join_mode = "all"

      node = WorkflowGraphTemplateNode(
        template_id=template.id,
        node_key=node_key,
        title=node_payload.title.strip(),
        assignment_mode=assignment_mode,
        join_mode=join_mode,
        assignee_rule=dict(node_payload.assignee_rule or {}),
        config=dict(node_payload.config or {}),
        sort_order=int(node_payload.sort_order if node_payload.sort_order else index),
      )
      self._session.add(node)
      node_by_key[node_key] = node
    await self._session.flush()

    for from_key, to_key, is_reject, condition, priority in preserved_edge_specs:
      from_node = node_by_key.get(from_key)
      to_node = node_by_key.get(to_key)
      if from_node is None or to_node is None:
        continue
      if from_node.id == to_node.id:
        raise ConflictError(f"边 {from_key} → {to_key} 不能指向自身。")
      self._session.add(
        WorkflowGraphTemplateEdge(
          template_id=template.id,
          from_node_id=from_node.id,
          to_node_id=to_node.id,
          is_reject_path=is_reject,
          condition=condition,
          priority=priority,
        )
      )
    await self._session.flush()

  async def _archive_sibling_active_templates(self, *, template: WorkflowGraphTemplate) -> None:
    siblings = list(
      await self._session.scalars(
        select(WorkflowGraphTemplate).where(
          WorkflowGraphTemplate.base_code == template.base_code,
          WorkflowGraphTemplate.status == WorkflowGraphTemplateStatus.ACTIVE,
          WorkflowGraphTemplate.id != template.id,
        )
      )
    )
    for sibling in siblings:
      sibling.status = WorkflowGraphTemplateStatus.ARCHIVED

  async def _has_instances(self, *, template_id: UUID) -> bool:
    existing_id = await self._session.scalar(
      select(WorkflowGraphInstance.id)
      .where(WorkflowGraphInstance.template_id == template_id)
      .limit(1)
    )
    return existing_id is not None

  async def _get_next_template_version(self, *, base_code: str) -> int:
    latest_version = await self._session.scalar(
      select(func.max(WorkflowGraphTemplate.version)).where(WorkflowGraphTemplate.base_code == base_code)
    )
    return int(latest_version or 0) + 1

  @staticmethod
  def _derive_template_code(*, base_code: str, version: int) -> str:
    match = _CODE_VERSION_SUFFIX.search(base_code)
    if match:
      prefix = base_code[: match.start()]
      return f"{prefix}_v{version}"
    return f"{base_code}_v{version}"

  async def _get_template_or_raise(self, *, template_id: UUID) -> WorkflowGraphTemplate:
    template = await self._session.get(WorkflowGraphTemplate, template_id)
    if template is None:
      raise NotFoundError("工作流图模板不存在。")
    return template

  async def _ensure_manage(self, actor: User) -> None:
    ensure_active_user(actor)
    if not await can_manage_task_templates(self._session, actor):
      raise AuthorizationError("当前账号无权维护图模板。")

  async def _load_node_summaries(self, *, template_id: UUID) -> list[WorkflowGraphTemplateNodeSummaryRead]:
    nodes = list(
      await self._session.scalars(
        select(WorkflowGraphTemplateNode)
        .where(WorkflowGraphTemplateNode.template_id == template_id)
        .order_by(WorkflowGraphTemplateNode.sort_order.asc())
      )
    )
    return [
      WorkflowGraphTemplateNodeSummaryRead(
        id=node.id,
        node_key=node.node_key,
        title=node.title,
        sort_order=node.sort_order,
      )
      for node in nodes
    ]

  async def _load_node_details(self, *, template_id: UUID) -> list[WorkflowGraphTemplateNodeDetailRead]:
    nodes = list(
      await self._session.scalars(
        select(WorkflowGraphTemplateNode)
        .where(WorkflowGraphTemplateNode.template_id == template_id)
        .order_by(WorkflowGraphTemplateNode.sort_order.asc())
      )
    )
    return [
      WorkflowGraphTemplateNodeDetailRead(
        id=node.id,
        node_key=node.node_key,
        title=node.title,
        sort_order=node.sort_order,
        node_type=node.node_type,
        assignment_mode=node.assignment_mode,
        join_mode=node.join_mode,
        assignee_rule=dict(node.assignee_rule or {}),
        config=dict(node.config or {}),
      )
      for node in nodes
    ]

  async def _load_edge_details(self, *, template_id: UUID) -> list[WorkflowGraphTemplateEdgeDetailRead]:
    nodes = list(
      await self._session.scalars(
        select(WorkflowGraphTemplateNode).where(WorkflowGraphTemplateNode.template_id == template_id)
      )
    )
    id_to_key = {node.id: node.node_key for node in nodes}
    edges = list(
      await self._session.scalars(
        select(WorkflowGraphTemplateEdge).where(WorkflowGraphTemplateEdge.template_id == template_id)
      )
    )
    return [
      WorkflowGraphTemplateEdgeDetailRead(
        id=edge.id,
        from_node_key=id_to_key[edge.from_node_id],
        to_node_key=id_to_key[edge.to_node_id],
        is_reject_path=bool(edge.is_reject_path),
        condition=dict(edge.condition or {}),
        priority=int(edge.priority or 0),
      )
      for edge in edges
      if edge.from_node_id in id_to_key and edge.to_node_id in id_to_key
    ]

  @staticmethod
  def _build_detail_read(
    *,
    template: WorkflowGraphTemplate,
    nodes: list[WorkflowGraphTemplateNodeSummaryRead],
  ) -> WorkflowGraphTemplateDetailRead:
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
      nodes=nodes,
    )

  @staticmethod
  def _build_designer_read(
    *,
    template: WorkflowGraphTemplate,
    nodes: list[WorkflowGraphTemplateNodeDetailRead],
    edges: list[WorkflowGraphTemplateEdgeDetailRead],
    has_instances: bool,
  ) -> WorkflowGraphTemplateDesignerRead:
    config = dict(template.config or {})
    return WorkflowGraphTemplateDesignerRead(
      id=template.id,
      code=template.code,
      base_code=template.base_code,
      source_template_id=template.source_template_id,
      name=template.name,
      description=template.description,
      status=template.status,
      version=template.version,
      run_kind=str(config.get("run_kind") or "") or None,
      config=config,
      has_instances=has_instances,
      structure_locked=has_instances,
      nodes=nodes,
      edges=edges,
    )

  @staticmethod
  def _collect_validation_errors(
    *,
    template: WorkflowGraphTemplate,
    nodes: list[WorkflowGraphTemplateNodeDetailRead],
    edges: list[WorkflowGraphTemplateEdgeDetailRead],
  ) -> list[str]:
    errors: list[str] = []
    config = dict(template.config or {})

    launch_schema_raw = config.get("launch_schema")
    if isinstance(launch_schema_raw, dict):
      try:
        validate_launch_schema(launch_schema_raw)
      except PydanticValidationError as exc:
        errors.append(f"launch_schema: {exc.errors()[0]['msg']}")

    node_keys = {node.node_key for node in nodes}
    aggregate_node_key = config.get("aggregate_node_key")
    if aggregate_node_key and str(aggregate_node_key) not in node_keys:
      errors.append(f"aggregate_node_key「{aggregate_node_key}」在节点表中不存在。")

    for node in nodes:
      try:
        validate_node_config(dict(node.config or {}))
      except PydanticValidationError as exc:
        errors.append(f"{node.node_key}: {exc.errors()[0]['msg']}")
      except ValueError as exc:
        errors.append(f"{node.node_key}: {exc}")

    errors.extend(
      validate_graph_template_topology(
        nodes=[
          GraphTemplateNodeSpec(
            node_key=node.node_key,
            assignment_mode=node.assignment_mode,
            join_mode=node.join_mode,
            config=dict(node.config or {}),
          )
          for node in nodes
        ],
        edges=[
          GraphTemplateEdgeSpec(
            from_node_key=edge.from_node_key,
            to_node_key=edge.to_node_key,
            is_reject_path=edge.is_reject_path,
            condition=dict(edge.condition or {}),
            priority=edge.priority,
          )
          for edge in edges
        ],
      )
    )
    return errors
