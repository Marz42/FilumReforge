"""Unit tests for workflow node config merge helpers."""

from __future__ import annotations

from app.models import WorkflowGraphTemplateNode, WorkflowNodeInstance
from app.services.workflow_node_config_helpers import (
  reconcile_node_instance_config_from_template,
  resolve_completion_policy,
)


def test_resolve_completion_policy_prefers_template_over_stale_snapshot() -> None:
  node_instance = WorkflowNodeInstance(
    node_key="N3_SCRIPT_WRITE",
    config={"completion_policy": "on_capture_submitted"},
  )
  template_node = WorkflowGraphTemplateNode(
    node_key="N3_SCRIPT_WRITE",
    config={"completion_policy": "on_submit_deliverable"},
  )

  assert (
    resolve_completion_policy(node_instance=node_instance, template_node=template_node)
    == "on_submit_deliverable"
  )


def test_reconcile_node_instance_config_from_template_updates_stale_policy() -> None:
  node_instance = WorkflowNodeInstance(
    node_key="N3_SCRIPT_WRITE",
    config={"completion_policy": "on_capture_submitted", "ui_profile": "legacy"},
  )
  template_node = WorkflowGraphTemplateNode(
    node_key="N3_SCRIPT_WRITE",
    config={
      "completion_policy": "on_submit_deliverable",
      "ui_profile": "video_production_step",
    },
  )

  changed = reconcile_node_instance_config_from_template(
    node_instance=node_instance,
    template_node=template_node,
  )

  assert changed is True
  assert node_instance.config["completion_policy"] == "on_submit_deliverable"
  assert node_instance.config["ui_profile"] == "video_production_step"
