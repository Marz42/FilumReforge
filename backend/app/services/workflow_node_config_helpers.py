"""Helpers for reading merged workflow graph node configuration."""

from __future__ import annotations

from app.models import WorkflowGraphInstance, WorkflowGraphTemplateNode, WorkflowNodeInstance


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


def is_streaming_aggregate_node(
  *,
  instance: WorkflowGraphInstance,
  node_instance: WorkflowNodeInstance,
  template_node: WorkflowGraphTemplateNode | None = None,
) -> bool:
  """W-08: streaming runs skip N2 aggregate projection tasks."""
  context = instance.context if isinstance(instance.context, dict) else {}
  if context.get("aggregate_mode") != "streaming":
    return False
  for config in merged_node_config_sources(node_instance=node_instance, template_node=template_node):
    if config.get("aggregate_schema"):
      return True
  return False


# Template seed upgrades rewrite template nodes in place; node_instance.config snapshots
# can lag behind. These keys follow the published template definition.
_TEMPLATE_SYNCED_CONFIG_KEYS = (
  "completion_policy",
  "ui_profile",
  "handshake_required",
  "max_deliverable_attachments",
)


def reconcile_node_instance_config_from_template(
  *,
  node_instance: WorkflowNodeInstance,
  template_node: WorkflowGraphTemplateNode | None,
) -> bool:
  """Align stale node_instance.config with the current template node after seed upgrades."""
  if template_node is None or not isinstance(template_node.config, dict):
    return False

  instance_config = dict(node_instance.config or {})
  template_config = template_node.config
  changed = False
  for key in _TEMPLATE_SYNCED_CONFIG_KEYS:
    if key not in template_config:
      continue
    template_value = template_config.get(key)
    if instance_config.get(key) != template_value:
      instance_config[key] = template_value
      changed = True
  if changed:
    node_instance.config = instance_config
  return changed


def resolve_completion_policy(
  *,
  node_instance: WorkflowNodeInstance,
  template_node: WorkflowGraphTemplateNode | None = None,
) -> str | None:
  # Prefer template definition so seed upgrades are not blocked by stale snapshots.
  if template_node is not None and isinstance(template_node.config, dict):
    policy = template_node.config.get("completion_policy")
    if isinstance(policy, str) and policy.strip():
      return policy.strip()

  if isinstance(node_instance.config, dict):
    policy = node_instance.config.get("completion_policy")
    if isinstance(policy, str) and policy.strip():
      return policy.strip()
  return None
