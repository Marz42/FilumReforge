"""Topology and routing validation for WorkflowGraphTemplate designer (D2)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from app.services.condition_evaluator import is_else_condition


@dataclass(frozen=True, slots=True)
class GraphTemplateNodeSpec:
  node_key: str
  assignment_mode: str
  join_mode: str
  config: dict[str, Any]


@dataclass(frozen=True, slots=True)
class GraphTemplateEdgeSpec:
  from_node_key: str
  to_node_key: str
  is_reject_path: bool
  condition: dict[str, Any]
  priority: int


def validate_graph_template_topology(
  *,
  nodes: list[GraphTemplateNodeSpec],
  edges: list[GraphTemplateEdgeSpec],
) -> list[str]:
  errors: list[str] = []
  node_keys = {node.node_key for node in nodes}
  if not node_keys:
    return ["模板至少需要一个节点。"]

  for node in nodes:
    errors.extend(_validate_node_modes(node))
    errors.extend(_validate_routing_rules(node, node_keys))

  edge_errors, forward_adj, reverse_adj, entry_keys = _validate_edges(nodes=nodes, edges=edges, node_keys=node_keys)
  errors.extend(edge_errors)

  if not entry_keys:
    errors.append("至少需要一个无入边的起始节点（forward 边）。")

  errors.extend(_validate_reachability(node_keys=node_keys, entry_keys=entry_keys, forward_adj=forward_adj))
  errors.extend(_validate_forward_acyclic(forward_adj=forward_adj))
  errors.extend(_validate_reject_targets(nodes=nodes, edges=edges, node_keys=node_keys))

  return errors


def _validate_node_modes(node: GraphTemplateNodeSpec) -> list[str]:
  errors: list[str] = []
  assignment_mode = (node.assignment_mode or "single").strip().lower()
  join_mode = (node.join_mode or "all").strip().lower()
  if assignment_mode not in {"single", "fan_out"}:
    errors.append(f"{node.node_key}: assignment_mode 必须是 single 或 fan_out。")
  if join_mode not in {"all", "any"}:
    errors.append(f"{node.node_key}: join_mode 必须是 all 或 any。")
  if assignment_mode == "single" and join_mode != "all":
    errors.append(f"{node.node_key}: assignment_mode=single 时 join_mode 必须为 all。")
  return errors


def _validate_routing_rules(node: GraphTemplateNodeSpec, node_keys: set[str]) -> list[str]:
  routing_rules = (node.config or {}).get("routing_rules")
  if not routing_rules:
    return []
  if not isinstance(routing_rules, list):
    return [f"{node.node_key}: routing_rules 必须是数组。"]

  errors: list[str] = []
  has_else = False
  for index, rule in enumerate(routing_rules, start=1):
    if not isinstance(rule, dict):
      errors.append(f"{node.node_key}: routing_rules[{index}] 必须是对象。")
      continue
    target_key = rule.get("target_node_key") or rule.get("target_step_key")
    if not isinstance(target_key, str) or not target_key.strip():
      errors.append(f"{node.node_key}: routing_rules[{index}] 缺少 target_node_key。")
    elif target_key not in node_keys:
      errors.append(f"{node.node_key}: routing_rules[{index}] 指向未知节点「{target_key}」。")
    if is_else_condition(rule):
      has_else = True
      continue
    condition = rule.get("condition")
    if not isinstance(condition, dict) or not condition:
      errors.append(f"{node.node_key}: routing_rules[{index}] 的非 ELSE 规则必须包含 condition。")

  conditional_rules = [
    rule
    for rule in routing_rules
    if isinstance(rule, dict) and not is_else_condition(rule)
  ]
  if conditional_rules and not has_else:
    errors.append(f"{node.node_key}: routing_rules 含条件分支时必须包含 ELSE 规则。")
  return errors


def _validate_edges(
  *,
  nodes: list[GraphTemplateNodeSpec],
  edges: list[GraphTemplateEdgeSpec],
  node_keys: set[str],
) -> tuple[list[str], dict[str, set[str]], dict[str, set[str]], set[str]]:
  errors: list[str] = []
  forward_adj: dict[str, set[str]] = defaultdict(set)
  reverse_adj: dict[str, set[str]] = defaultdict(set)
  seen_paths: set[tuple[str, str, bool]] = set()

  incoming_forward: dict[str, int] = defaultdict(int)
  outgoing_forward_conditions: dict[str, list[GraphTemplateEdgeSpec]] = defaultdict(list)
  outgoing_forward_else: dict[str, int] = defaultdict(int)

  for edge in edges:
    if edge.from_node_key not in node_keys:
      errors.append(f"边起点「{edge.from_node_key}」不存在。")
      continue
    if edge.to_node_key not in node_keys:
      errors.append(f"边终点「{edge.to_node_key}」不存在。")
      continue
    if edge.from_node_key == edge.to_node_key:
      errors.append(f"边 {edge.from_node_key} → {edge.to_node_key} 不能指向自身。")

    path_key = (edge.from_node_key, edge.to_node_key, edge.is_reject_path)
    if path_key in seen_paths:
      errors.append(f"重复边：{edge.from_node_key} → {edge.to_node_key}（reject={edge.is_reject_path}）。")
    seen_paths.add(path_key)

    if edge.is_reject_path:
      continue

    forward_adj[edge.from_node_key].add(edge.to_node_key)
    reverse_adj[edge.to_node_key].add(edge.from_node_key)
    incoming_forward[edge.to_node_key] += 1

    condition = dict(edge.condition or {})
    if is_else_condition(condition):
      outgoing_forward_else[edge.from_node_key] += 1
    elif condition:
      outgoing_forward_conditions[edge.from_node_key].append(edge)
    else:
      outgoing_forward_conditions[edge.from_node_key].append(edge)

  for node in nodes:
    if incoming_forward[node.node_key] == 0:
      pass  # candidate entry

  entry_keys = {node.node_key for node in nodes if incoming_forward[node.node_key] == 0}

  for from_key, conditional_edges in outgoing_forward_conditions.items():
    if not conditional_edges:
      continue
    has_unconditional = any(not dict(edge.condition or {}) for edge in conditional_edges)
    has_else = outgoing_forward_else[from_key] > 0
    has_explicit_condition = any(
      dict(edge.condition or {}) and not is_else_condition(dict(edge.condition or {}))
      for edge in conditional_edges
    )
    if has_explicit_condition and not has_else and not has_unconditional:
      errors.append(f"节点 {from_key} 的条件边必须包含 ELSE 边或无条件的默认边。")

  return errors, forward_adj, reverse_adj, entry_keys


def _validate_reachability(
  *,
  node_keys: set[str],
  entry_keys: set[str],
  forward_adj: dict[str, set[str]],
) -> list[str]:
  if not entry_keys:
    return []

  reachable: set[str] = set()
  stack = list(entry_keys)
  while stack:
    current = stack.pop()
    if current in reachable:
      continue
    reachable.add(current)
    stack.extend(forward_adj.get(current, ()))

  orphans = sorted(node_keys - reachable)
  if orphans:
    return [f"不可达节点（forward 边）：{', '.join(orphans)}。"]
  return []


def _validate_forward_acyclic(*, forward_adj: dict[str, set[str]]) -> list[str]:
  visiting: set[str] = set()
  visited: set[str] = set()

  def dfs(node_key: str) -> bool:
    if node_key in visiting:
      return True
    if node_key in visited:
      return False
    visiting.add(node_key)
    for downstream in forward_adj.get(node_key, ()):
      if dfs(downstream):
        return True
    visiting.remove(node_key)
    visited.add(node_key)
    return False

  for node_key in forward_adj:
    if dfs(node_key):
      return ["forward 边存在环路。"]
  return []


def _validate_reject_targets(
  *,
  nodes: list[GraphTemplateNodeSpec],
  edges: list[GraphTemplateEdgeSpec],
  node_keys: set[str],
) -> list[str]:
  errors: list[str] = []
  reject_edge_targets = {
    (edge.from_node_key, edge.to_node_key)
    for edge in edges
    if edge.is_reject_path
  }

  for node in nodes:
    acceptance_spec = (node.config or {}).get("acceptance_spec")
    if not isinstance(acceptance_spec, dict):
      continue
    reject_to = acceptance_spec.get("reject_to")
    if not isinstance(reject_to, dict):
      continue
    target_key = reject_to.get("node_key")
    if not isinstance(target_key, str) or not target_key.strip():
      errors.append(f"{node.node_key}: acceptance_spec.reject_to.node_key 无效。")
      continue
    if target_key not in node_keys:
      errors.append(f"{node.node_key}: reject_to 指向未知节点「{target_key}」。")
      continue
    if (node.node_key, target_key) not in reject_edge_targets:
      errors.append(
        f"{node.node_key}: reject_to「{target_key}」须存在对应的 reject 边（is_reject_path=true）。"
      )
  return errors
