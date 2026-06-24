"""Video workflow v1 policy helpers (W0+).

Graph template instantiation (batch / production runs) is gated by
``workflow_graph_template_engine_enabled``. Legacy task-template E instantiation was removed in B-12 (TC-Transform Phase 0).

Environment variables (W9-3):
- ``WORKFLOW_GRAPH_ENGINE_ENABLED`` → ``workflow_graph_engine_enabled`` (default true)
- ``WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED`` → ``workflow_graph_template_engine_enabled`` (default false)
- ``TASK_CENTER_V2_ENABLED`` → ``task_center_v2_enabled`` (default true)
- ``WORKFLOW_WAIT_ANY_ENABLED`` → ``workflow_wait_any_enabled`` (default false)
- ``WORKFLOW_DEEP_REJECTION_ENABLED`` → ``workflow_deep_rejection_enabled`` (default false)
"""

from __future__ import annotations

from app.core.config import Settings, get_settings


def use_graph_template_instantiation(settings: Settings | None = None) -> bool:
  """Return True when new graph-template run APIs should be used."""
  resolved = settings or get_settings()
  return resolved.workflow_graph_template_engine_enabled


def use_legacy_task_template_instantiation(settings: Settings | None = None) -> bool:
  """Return True when Legacy E ``TaskTemplateService`` APIs are available (removed in B-12)."""
  _ = settings or get_settings()
  return False


def use_workflow_graph_engine(settings: Settings | None = None) -> bool:
  """Return True when manual-task graph dual-write and node APIs are active."""
  resolved = settings or get_settings()
  return resolved.workflow_graph_engine_enabled


def workflow_feature_flags(settings: Settings | None = None) -> dict[str, bool]:
  """Snapshot of workflow-related feature flags for clients and ops."""
  resolved = settings or get_settings()
  return {
    "workflow_graph_engine_enabled": resolved.workflow_graph_engine_enabled,
    "workflow_graph_template_engine_enabled": resolved.workflow_graph_template_engine_enabled,
    "task_center_v2_enabled": resolved.task_center_v2_enabled,
    "workflow_wait_any_enabled": resolved.workflow_wait_any_enabled,
    "workflow_deep_rejection_enabled": resolved.workflow_deep_rejection_enabled,
    "legacy_task_template_instantiation_enabled": use_legacy_task_template_instantiation(resolved),
  }
