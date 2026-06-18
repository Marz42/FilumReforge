"""Helpers for reading merged workflow graph node configuration."""

from __future__ import annotations

from app.models import WorkflowGraphTemplateNode, WorkflowNodeInstance


def merged_node_config_sources(
  *,
  node_instance: WorkflowNodeInstance,
  template_node: WorkflowGraphTemplateNode | None = None,
) -> list[dict]:
  sources: list[dict] = []
  if isinstance(node_instance.config, dict):
    sources.append(node_instance.config)
  if template_node is not None and isinstance(template_node.config, dict):
    sources.append(template_node.config)
  return sources


def resolve_completion_policy(
  *,
  node_instance: WorkflowNodeInstance,
  template_node: WorkflowGraphTemplateNode | None = None,
) -> str | None:
  for config in merged_node_config_sources(
    node_instance=node_instance,
    template_node=template_node,
  ):
    policy = config.get("completion_policy")
    if isinstance(policy, str) and policy.strip():
      return policy.strip()
  return None
