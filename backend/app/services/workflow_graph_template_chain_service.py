"""Generic workflow graph template chain on instance completion (F-23)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import WorkflowGraphTemplateStatus
from app.models import User, WorkflowGraphInstance, WorkflowGraphTemplate
from app.schemas.workflow_video import (
  OnCompleteTemplateChainSchema,
  parse_on_complete_config,
  validate_on_complete_config,
)
from app.services.workflow_definition_snapshot import (
  RuntimeDefinitionTemplate,
  SNAPSHOT_EXECUTOR_KIND,
  runtime_template,
)
from pydantic import ValidationError as PydanticValidationError


async def load_active_on_complete_edges(session: AsyncSession) -> dict[str, str]:
  templates = list(
    await session.scalars(
      select(WorkflowGraphTemplate).where(
        WorkflowGraphTemplate.status == WorkflowGraphTemplateStatus.ACTIVE,
      )
    )
  )
  edges: dict[str, str] = {}
  for template in templates:
    on_complete = parse_on_complete_config(template.config if isinstance(template.config, dict) else {})
    if on_complete is None:
      continue
    source_code = template.base_code or template.code
    edges[source_code] = on_complete.next_template_code
  return edges


def would_create_template_chain_cycle(
  *,
  start_code: str,
  next_code: str,
  edges: dict[str, str],
) -> bool:
  if start_code == next_code:
    return True

  visited: set[str] = set()
  stack = [next_code]
  while stack:
    current = stack.pop()
    if current == start_code:
      return True
    if current in visited:
      continue
    visited.add(current)
    downstream = edges.get(current)
    if downstream:
      stack.append(downstream)
  return False


async def validate_on_complete_for_publish(
  session: AsyncSession,
  *,
  template: WorkflowGraphTemplate,
) -> list[str]:
  config = template.config if isinstance(template.config, dict) else {}
  raw_on_complete = config.get("on_complete")
  if raw_on_complete is None:
    return []
  if not isinstance(raw_on_complete, dict):
    return ["on_complete 必须是对象。"]

  try:
    parsed = validate_on_complete_config(raw_on_complete)
  except PydanticValidationError as exc:
    return [f"on_complete: {exc.errors()[0]['msg']}"]

  start_code = template.base_code or template.code
  errors: list[str] = []
  if parsed.next_template_code == start_code:
    errors.append("on_complete.next_template_code 不能指向当前模板。")

  target_exists = await session.scalar(
    select(WorkflowGraphTemplate.id).where(
      WorkflowGraphTemplate.base_code == parsed.next_template_code,
      WorkflowGraphTemplate.status == WorkflowGraphTemplateStatus.ACTIVE,
    )
  )
  if target_exists is None:
    errors.append(f"on_complete 目标模板「{parsed.next_template_code}」不存在或未 active。")

  edges = await load_active_on_complete_edges(session)
  edges[start_code] = parsed.next_template_code
  if would_create_template_chain_cycle(
    start_code=start_code,
    next_code=parsed.next_template_code,
    edges=edges,
  ):
    errors.append("on_complete 模板链存在环路，无法发布。")

  return errors


async def _resolve_next_active_template(
  session: AsyncSession,
  *,
  template_code: str,
) -> WorkflowGraphTemplate | None:
  return await session.scalar(
    select(WorkflowGraphTemplate)
    .where(
      WorkflowGraphTemplate.base_code == template_code,
      WorkflowGraphTemplate.status == WorkflowGraphTemplateStatus.ACTIVE,
    )
    .order_by(WorkflowGraphTemplate.version.desc())
    .limit(1)
  )


def _build_chained_context(
  *,
  parent_instance: WorkflowGraphInstance,
  parent_template: WorkflowGraphTemplate | RuntimeDefinitionTemplate,
  on_complete: OnCompleteTemplateChainSchema,
) -> dict[str, Any]:
  parent_context = parent_instance.context if isinstance(parent_instance.context, dict) else {}
  ancestor_codes = list(parent_context.get("template_chain_ancestor_codes") or [])
  parent_code = parent_template.base_code or parent_template.code
  if parent_code not in ancestor_codes:
    ancestor_codes.append(parent_code)

  child_context: dict[str, Any] = {
    "template_chain_ancestor_codes": ancestor_codes,
    "chained_from_instance_id": str(parent_instance.id),
    "chained_from_template_code": parent_code,
  }
  if on_complete.carry_inputs:
    inputs = parent_context.get("inputs")
    if isinstance(inputs, dict):
      child_context["inputs"] = dict(inputs)
  return child_context


async def maybe_trigger_template_chain(
  session: AsyncSession,
  *,
  instance: WorkflowGraphInstance,
) -> WorkflowGraphInstance | None:
  """When a run completes, instantiate the configured next template if present."""
  if instance.template_id is None:
    return None

  parent_template: WorkflowGraphTemplate | RuntimeDefinitionTemplate | None
  if instance.executor_kind == SNAPSHOT_EXECUTOR_KIND:
    parent_template = runtime_template(instance.definition_snapshot)
  else:
    parent_template = await session.get(WorkflowGraphTemplate, instance.template_id)
  if parent_template is None:
    return None

  on_complete = parse_on_complete_config(
    parent_template.config if isinstance(parent_template.config, dict) else {},
  )
  if on_complete is None:
    return None

  parent_context = dict(instance.context or {})
  if parent_context.get("on_complete_triggered"):
    return None

  parent_code = parent_template.base_code or parent_template.code
  ancestor_codes = set(parent_context.get("template_chain_ancestor_codes") or [])
  if on_complete.next_template_code in ancestor_codes or on_complete.next_template_code == parent_code:
    return None

  next_template = await _resolve_next_active_template(session, template_code=on_complete.next_template_code)
  if next_template is None:
    return None

  initiator = await session.get(User, instance.initiator_user_id)
  if initiator is None:
    return None

  child_context = _build_chained_context(
    parent_instance=instance,
    parent_template=parent_template,
    on_complete=on_complete,
  )

  parent_context["on_complete_triggered"] = True
  parent_context["chained_to_template_code"] = on_complete.next_template_code
  instance.context = parent_context
  await session.flush()

  from app.services.workflow_graph_service import WorkflowGraphService

  graph_service = WorkflowGraphService(session)
  result = await graph_service.create_multi_node_instance(
    template_id=next_template.id,
    initiator_id=initiator.id,
    department_id=instance.department_id,
    context=child_context,
  )
  result.instance.parent_instance_id = instance.id
  await session.flush()
  return result.instance
