"""TemplateCapabilities matrix (spec Appendix A)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.enums import WorkflowGraphTemplateStatus
from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode
from app.services.workflow_graph_template_capabilities import compute_template_capabilities


def _template(*, status: WorkflowGraphTemplateStatus, config: dict) -> WorkflowGraphTemplate:
  return WorkflowGraphTemplate(
    id=uuid4(),
    code="test_tpl_v1",
    base_code="test_tpl",
    version=1,
    name="Test",
    status=status,
    config=config,
    created_by=uuid4(),
  )


def _start_node() -> WorkflowGraphTemplateNode:
  node = WorkflowGraphTemplateNode(
    id=uuid4(),
    template_id=uuid4(),
    node_key="N1_START",
    title="Start",
    sort_order=1,
    config={"kind": "single"},
  )
  return node


@pytest.mark.parametrize(
  ("status", "config", "node_config", "fork_codes", "expect_direct", "expect_schedule", "expect_launch_entry"),
  [
    (
      WorkflowGraphTemplateStatus.DRAFT,
      {},
      {"kind": "single"},
      set(),
      False,
      False,
      True,
    ),
    (
      WorkflowGraphTemplateStatus.ACTIVE,
      {"schedulable": True, "launch_schema": {"fields": []}, "aggregate_mode": "batch"},
      {"kind": "multi_instance", "expand_from": "copywriters"},
      set(),
      True,
      True,
      True,
    ),
    (
      WorkflowGraphTemplateStatus.ACTIVE,
      {"run_kind": "production"},
      {"kind": "single"},
      set(),
      False,
      False,
      True,
    ),
    (
      WorkflowGraphTemplateStatus.ACTIVE,
      {"launch_schema": {"fields": []}},
      {"kind": "single"},
      set(),
      True,
      False,
      True,
    ),
    (
      WorkflowGraphTemplateStatus.ACTIVE,
      {"schedulable": True, "launch_schema": {"fields": []}, "aggregate_mode": "streaming"},
      {"kind": "multi_instance", "expand_from": "copywriters"},
      set(),
      True,
      False,
      True,
    ),
    (
      WorkflowGraphTemplateStatus.ACTIVE,
      {},
      None,
      set(),
      False,
      False,
      False,
    ),
  ],
)
def test_capabilities_matrix(
  status,
  config,
  node_config,
  fork_codes,
  expect_direct,
  expect_schedule,
  expect_launch_entry,
) -> None:
  template = _template(status=status, config=config)
  if node_config is None:
    nodes: list[WorkflowGraphTemplateNode] = []
  else:
    node = _start_node()
    node.config = node_config
    nodes = [node]
  edges: list[WorkflowGraphTemplateEdge] = []
  caps = compute_template_capabilities(
    template=template,
    nodes=nodes,
    edges=edges,
    fork_target_codes=fork_codes,
  )
  assert caps.can_instantiate_directly is expect_direct
  assert caps.can_schedule is expect_schedule
  assert caps.has_launch_entry is expect_launch_entry
