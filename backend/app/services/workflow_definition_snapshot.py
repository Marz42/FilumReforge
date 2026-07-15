from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.enums import WorkflowGraphNodeType
from app.core.exceptions import ConflictError
from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode

SNAPSHOT_FORMAT_VERSION = 2
SNAPSHOT_ENGINE_VERSION = "graph-v3"
PATH_SEMANTICS_ENGINE_VERSION = "graph-v3"
SNAPSHOT_EXECUTOR_KIND = "snapshot"
LEGACY_ENGINE_VERSION = "legacy-v1"
LEGACY_EXECUTOR_KIND = "legacy"


@dataclass(frozen=True, slots=True)
class RuntimeDefinitionNode:
  id: UUID
  node_key: str
  title: str
  node_type: WorkflowGraphNodeType
  assignment_mode: str
  join_mode: str
  routing_mode: str
  assignee_rule: dict[str, Any]
  config: dict[str, Any]
  sort_order: int


@dataclass(frozen=True, slots=True)
class RuntimeDefinitionEdge:
  from_node_id: UUID
  to_node_id: UUID
  from_node_key: str
  to_node_key: str
  is_reject_path: bool
  condition: dict[str, Any]
  priority: int


@dataclass(frozen=True, slots=True)
class RuntimeDefinitionTemplate:
  id: UUID
  code: str
  base_code: str
  version: int
  name: str
  config: dict[str, Any]
  context_schema: dict[str, Any]
  scope_mode: str
  scope_department_ids: list[str]


def normalize_scope(
  *,
  scope_mode: str | None,
  scope_department_ids: list[Any] | None,
) -> tuple[str, list[str]]:
  normalized_id_set: set[str] = set()
  for item in scope_department_ids or []:
    if not item:
      continue
    try:
      normalized_id_set.add(str(UUID(str(item).strip())))
    except (ValueError, AttributeError) as exc:
      raise ConflictError("scope_department_ids 必须全部为有效 UUID。") from exc
  normalized_ids = sorted(normalized_id_set)
  normalized_mode = (scope_mode or ("departments" if normalized_ids else "global")).strip().lower()
  if normalized_mode not in {"global", "departments"}:
    raise ConflictError("模板 scope_mode 仅支持 global 或 departments。")
  if normalized_mode == "global":
    if normalized_ids:
      raise ConflictError("global 模板不能同时配置 scope_department_ids。")
    return normalized_mode, []
  if not normalized_ids:
    raise ConflictError("departments 模板至少需要一个 scope_department_id。")
  return normalized_mode, normalized_ids


def ensure_template_scope_allows_department(
  *,
  template: WorkflowGraphTemplate,
  department_id: UUID | None,
) -> None:
  mode, department_ids = normalize_scope(
    scope_mode=getattr(template, "scope_mode", None),
    scope_department_ids=template.scope_department_ids,
  )
  if mode == "global":
    return
  if department_id is None or str(department_id) not in set(department_ids):
    raise ConflictError("所选部门不在该模板的作用范围内，请联系管理员。")


def build_definition_snapshot(
  *,
  template: WorkflowGraphTemplate,
  nodes: list[WorkflowGraphTemplateNode],
  edges: list[WorkflowGraphTemplateEdge],
) -> dict[str, Any]:
  node_by_id = {node.id: node for node in nodes}
  scope_mode, scope_department_ids = normalize_scope(
    scope_mode=getattr(template, "scope_mode", None),
    scope_department_ids=template.scope_department_ids,
  )
  ordered_nodes = sorted(nodes, key=lambda item: (item.sort_order, item.node_key))
  ordered_edges = sorted(
    edges,
    key=lambda item: (
      node_by_id[item.from_node_id].node_key,
      item.priority,
      node_by_id[item.to_node_id].node_key,
    ),
  )
  forward_edges = [edge for edge in edges if not edge.is_reject_path]
  incoming_keys = {edge.to_node_id for edge in forward_edges}
  outgoing_keys = {edge.from_node_id for edge in forward_edges}
  return {
    "format_version": SNAPSHOT_FORMAT_VERSION,
    "template": {
      "id": str(template.id),
      "code": template.code,
      "base_code": template.base_code,
      "version": template.version,
      "name": template.name,
      "config": dict(template.config or {}),
      "context_schema": dict(template.context_schema or {}),
      "scope_mode": scope_mode,
      "scope_department_ids": scope_department_ids,
    },
    "compatibility": {
      "start_node_keys": [node.node_key for node in ordered_nodes if node.id not in incoming_keys],
      "end_node_keys": [node.node_key for node in ordered_nodes if node.id not in outgoing_keys],
    },
    "nodes": [
      {
        "id": str(node.id),
        "node_key": node.node_key,
        "title": node.title,
        "node_type": node.node_type.value,
        "assignment_mode": node.assignment_mode,
        "join_mode": node.join_mode,
        "routing_mode": getattr(node, "routing_mode", "inclusive") or "inclusive",
        "assignee_rule": dict(node.assignee_rule or {}),
        "config": dict(node.config or {}),
        "sort_order": node.sort_order,
      }
      for node in ordered_nodes
    ],
    "edges": [
      {
        "from_node_key": node_by_id[edge.from_node_id].node_key,
        "to_node_key": node_by_id[edge.to_node_id].node_key,
        "is_reject_path": edge.is_reject_path,
        "condition": dict(edge.condition or {}),
        "priority": edge.priority,
      }
      for edge in ordered_edges
    ],
  }


def canonical_snapshot_json(snapshot: dict[str, Any]) -> str:
  return json.dumps(
    snapshot,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
    allow_nan=False,
  )


def definition_snapshot_hash(snapshot: dict[str, Any]) -> str:
  return hashlib.sha256(canonical_snapshot_json(snapshot).encode("utf-8")).hexdigest()


def runtime_nodes(snapshot: dict[str, Any] | None) -> list[RuntimeDefinitionNode]:
  if not isinstance(snapshot, dict):
    return []
  return [
    RuntimeDefinitionNode(
      id=UUID(str(raw["id"])),
      node_key=str(raw["node_key"]),
      title=str(raw["title"]),
      node_type=WorkflowGraphNodeType(str(raw.get("node_type") or "task")),
      assignment_mode=str(raw.get("assignment_mode") or "single"),
      join_mode=str(raw.get("join_mode") or "all"),
      routing_mode=str(raw.get("routing_mode") or "inclusive"),
      assignee_rule=dict(raw.get("assignee_rule") or {}),
      config=dict(raw.get("config") or {}),
      sort_order=int(raw.get("sort_order") or 0),
    )
    for raw in (snapshot.get("nodes") or [])
    if isinstance(raw, dict)
  ]


def runtime_edges(snapshot: dict[str, Any] | None) -> list[RuntimeDefinitionEdge]:
  if not isinstance(snapshot, dict):
    return []
  node_id_by_key = {
    str(raw["node_key"]): UUID(str(raw["id"]))
    for raw in (snapshot.get("nodes") or [])
    if isinstance(raw, dict) and raw.get("node_key") and raw.get("id")
  }
  return [
    RuntimeDefinitionEdge(
      from_node_id=node_id_by_key[str(raw["from_node_key"])],
      to_node_id=node_id_by_key[str(raw["to_node_key"])],
      from_node_key=str(raw["from_node_key"]),
      to_node_key=str(raw["to_node_key"]),
      is_reject_path=bool(raw.get("is_reject_path", False)),
      condition=dict(raw.get("condition") or {}),
      priority=int(raw.get("priority") or 0),
    )
    for raw in (snapshot.get("edges") or [])
    if (
      isinstance(raw, dict)
      and str(raw.get("from_node_key")) in node_id_by_key
      and str(raw.get("to_node_key")) in node_id_by_key
    )
  ]


def runtime_template(snapshot: dict[str, Any] | None) -> RuntimeDefinitionTemplate | None:
  if not isinstance(snapshot, dict) or not isinstance(snapshot.get("template"), dict):
    return None
  raw = snapshot["template"]
  return RuntimeDefinitionTemplate(
    id=UUID(str(raw["id"])),
    code=str(raw["code"]),
    base_code=str(raw["base_code"]),
    version=int(raw["version"]),
    name=str(raw["name"]),
    config=dict(raw.get("config") or {}),
    context_schema=dict(raw.get("context_schema") or {}),
    scope_mode=str(raw.get("scope_mode") or "global"),
    scope_department_ids=[str(item) for item in (raw.get("scope_department_ids") or [])],
  )
