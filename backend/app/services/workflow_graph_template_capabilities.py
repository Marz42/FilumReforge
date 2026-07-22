"""Derive TemplateCapabilities from graph structure + explicit opt-in flags (ADR-017)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.enums import WorkflowGraphTemplateStatus
from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode


@dataclass(frozen=True, slots=True)
class TemplateCapabilities:
  can_instantiate_directly: bool
  can_schedule: bool
  is_fork_target: bool
  has_multi_instance: bool
  has_launch_entry: bool
  derived_hints: list[str]


def normalize_template_tags(raw: list[str] | None) -> list[str]:
  seen: set[str] = set()
  normalized: list[str] = []
  for item in raw or []:
    tag = str(item).strip()
    if not tag or tag in seen:
      continue
    seen.add(tag)
    normalized.append(tag)
  return normalized


def _has_multi_instance(nodes: list[WorkflowGraphTemplateNode]) -> bool:
  return any(
    isinstance(node.config, dict)
    and node.config.get("kind") == "multi_instance"
    and node.config.get("expand_from")
    for node in nodes
  )


def _has_launch_entry(
  nodes: list[WorkflowGraphTemplateNode],
  edges: list[WorkflowGraphTemplateEdge],
) -> bool:
  if not nodes:
    return False
  id_to_key = {node.id: node.node_key for node in nodes}
  incoming: dict[str, int] = {node.node_key: 0 for node in nodes}
  for edge in edges:
    if edge.is_reject_path:
      continue
    to_key = id_to_key.get(edge.to_node_id)
    if to_key in incoming:
      incoming[to_key] += 1
  return any(degree == 0 for degree in incoming.values())


def _has_direct_launch_surface(config: dict[str, Any], *, has_multi_instance: bool) -> bool:
  launch_schema = config.get("launch_schema")
  has_launch_schema = isinstance(launch_schema, (dict, list)) and bool(launch_schema)
  return has_launch_schema or config.get("schedulable") is True or has_multi_instance


def _legacy_blocks_direct_instantiation(config: dict[str, Any]) -> bool:
  return str(config.get("run_kind") or "") == "production"


def compute_template_capabilities(
  *,
  template: WorkflowGraphTemplate,
  nodes: list[WorkflowGraphTemplateNode],
  edges: list[WorkflowGraphTemplateEdge],
  fork_target_codes: set[str],
) -> TemplateCapabilities:
  config = template.config if isinstance(template.config, dict) else {}
  template_code = str(template.code or "")
  template_base = str(template.base_code or "")
  has_mi = _has_multi_instance(nodes)
  has_entry = _has_launch_entry(nodes, edges)
  is_fork_target = template_code in fork_target_codes or template_base in fork_target_codes
  has_surface = _has_direct_launch_surface(config, has_multi_instance=has_mi)
  is_fork_only = is_fork_target and not has_surface

  can_instantiate = (
    template.status == WorkflowGraphTemplateStatus.ACTIVE
    and has_entry
    and not is_fork_only
  )
  if _legacy_blocks_direct_instantiation(config):
    can_instantiate = False

  can_schedule = (
    config.get("schedulable") is True
    and has_mi
    and can_instantiate
    and config.get("aggregate_mode") != "streaming"
  )

  hints: list[str] = []
  if can_instantiate:
    hints.append("可直接发起")
  if can_schedule:
    hints.append("可调度")
  if is_fork_target:
    hints.append("可作为子流程目标")
  if is_fork_only:
    hints.append("仅子流程")

  return TemplateCapabilities(
    can_instantiate_directly=can_instantiate,
    can_schedule=can_schedule,
    is_fork_target=is_fork_target,
    has_multi_instance=has_mi,
    has_launch_entry=has_entry,
    derived_hints=hints,
  )


def build_fork_target_code_index(templates: list[WorkflowGraphTemplate]) -> set[str]:
  codes: set[str] = set()
  for template in templates:
    config = template.config if isinstance(template.config, dict) else {}
    child_code = config.get("child_template_code")
    if isinstance(child_code, str) and child_code.strip():
      codes.add(child_code.strip())
  return codes
