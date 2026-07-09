"""Shared assignee resolution for workflow graph template nodes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models import User, WorkflowGraphTemplate, WorkflowGraphTemplateNode, WorkflowNodeInstance
from app.services.participant_resolution_service import resolve_assignee_from_rule


def parse_department_pools(template: WorkflowGraphTemplate) -> dict[str, UUID]:
  config = template.config if isinstance(template.config, dict) else {}
  pools = config.get("department_pools")
  if not isinstance(pools, dict):
    return {}
  parsed: dict[str, UUID] = {}
  for key, value in pools.items():
    if value is None:
      continue
    try:
      parsed[str(key)] = UUID(str(value))
    except (ValueError, AttributeError):
      continue
  return parsed


def build_production_department_pools(
  *,
  template_pools: dict[str, Any] | None,
  launch_department_id: UUID | None,
) -> dict[str, UUID]:
  """F-28: merge template pools; copywriters follows batch launch department."""
  parsed: dict[str, UUID] = {}
  if isinstance(template_pools, dict):
    for key, value in template_pools.items():
      if value is None:
        continue
      parsed[str(key)] = UUID(str(value))
  if launch_department_id is not None:
    parsed["copywriters"] = launch_department_id
  return parsed


def resolve_department_pools(
  template: WorkflowGraphTemplate,
  context: dict[str, Any] | None = None,
) -> dict[str, UUID]:
  """Template pools overridden by instance context department_pools (string UUIDs)."""
  pools = parse_department_pools(template)
  if not isinstance(context, dict):
    return pools
  ctx_pools = context.get("department_pools")
  if not isinstance(ctx_pools, dict):
    return pools
  for key, value in ctx_pools.items():
    if value is None:
      continue
    pools[str(key)] = UUID(str(value))
  return pools


async def resolve_node_assignee_id(
  session: AsyncSession,
  *,
  actor: User,
  template: WorkflowGraphTemplate,
  template_node: WorkflowGraphTemplateNode,
  node_instance: WorkflowNodeInstance | None = None,
  context: dict[str, Any] | None = None,
  department_id: UUID | None = None,
) -> UUID:
  assignee_rule = (
    template_node.assignee_rule
    if isinstance(template_node.assignee_rule, dict) and template_node.assignee_rule
    else None
  )
  node_config: dict[str, Any] = {}
  if node_instance is not None and isinstance(node_instance.config, dict):
    node_config = node_instance.config
  elif isinstance(template_node.config, dict):
    node_config = template_node.config

  assignee_ref = node_config.get("assignee_ref")
  if isinstance(assignee_ref, dict):
    assignee_rule = assignee_ref

  if not assignee_rule:
    return actor.id

  resolved_context = context if context is not None else {}
  users = await resolve_assignee_from_rule(
    session,
    actor=actor,
    assignee_rule=assignee_rule,
    department_id=department_id,
    allow_multiple=False,
    context=resolved_context,
    department_pools=resolve_department_pools(template, resolved_context),
  )
  if not users:
    raise ConflictError(f"节点 {template_node.node_key} 无法解析受理人。")
  return users[0].id
