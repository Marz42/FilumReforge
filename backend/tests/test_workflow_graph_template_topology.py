"""Unit tests for graph template topology validation (D2)."""

from __future__ import annotations

from app.services.workflow_graph_template_topology import (
  GraphTemplateEdgeSpec,
  GraphTemplateNodeSpec,
  validate_graph_template_topology,
)


def test_topology_requires_entry_node() -> None:
  errors = validate_graph_template_topology(
    nodes=[
      GraphTemplateNodeSpec(node_key="A", assignment_mode="single", join_mode="all", config={}),
      GraphTemplateNodeSpec(node_key="B", assignment_mode="single", join_mode="all", config={}),
    ],
    edges=[
      GraphTemplateEdgeSpec("A", "B", False, {}, 0),
      GraphTemplateEdgeSpec("B", "A", False, {}, 0),
    ],
  )
  assert any("起始节点" in item for item in errors)
  assert any("环路" in item for item in errors)


def test_topology_requires_else_for_conditional_edges() -> None:
  errors = validate_graph_template_topology(
    nodes=[
      GraphTemplateNodeSpec(node_key="A", assignment_mode="single", join_mode="all", config={}),
      GraphTemplateNodeSpec(node_key="B", assignment_mode="single", join_mode="all", config={}),
      GraphTemplateNodeSpec(node_key="C", assignment_mode="single", join_mode="all", config={}),
    ],
    edges=[
      GraphTemplateEdgeSpec("A", "B", False, {"field": "amount", "operator": "gt", "value": 1}, 0),
      GraphTemplateEdgeSpec("A", "C", False, {"else": True}, 1),
    ],
  )
  assert errors == []


def test_topology_reject_to_requires_reject_edge() -> None:
  errors = validate_graph_template_topology(
    nodes=[
      GraphTemplateNodeSpec(
        node_key="N4",
        assignment_mode="single",
        join_mode="all",
        config={"acceptance_spec": {"reject_to": {"node_key": "N3"}}},
      ),
      GraphTemplateNodeSpec(node_key="N3", assignment_mode="single", join_mode="all", config={}),
    ],
    edges=[GraphTemplateEdgeSpec("N3", "N4", False, {}, 0)],
  )
  assert any("reject 边" in item for item in errors)


def test_topology_routing_rules_else_required() -> None:
  errors = validate_graph_template_topology(
    nodes=[
      GraphTemplateNodeSpec(
        node_key="A",
        assignment_mode="single",
        join_mode="all",
        config={
          "routing_rules": [
            {"condition": {"field": "amount", "operator": "gt", "value": 1}, "target_node_key": "B"},
          ]
        },
      ),
      GraphTemplateNodeSpec(node_key="B", assignment_mode="single", join_mode="all", config={}),
    ],
    edges=[],
  )
  assert any("routing_rules" in item and "ELSE" in item for item in errors)
