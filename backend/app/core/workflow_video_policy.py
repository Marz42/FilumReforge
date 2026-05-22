"""Video workflow v1 policy helpers (W0+).

Graph template instantiation (batch / production runs) is gated by
``workflow_graph_template_engine_enabled``. Task-template E instantiation
remains the legacy default path until W3+ routes call the graph engine.
"""

from __future__ import annotations

from app.core.config import Settings, get_settings


def use_graph_template_instantiation(settings: Settings | None = None) -> bool:
  """Return True when new graph-template run APIs should be used."""
  resolved = settings or get_settings()
  return resolved.workflow_graph_template_engine_enabled


def use_legacy_task_template_instantiation(settings: Settings | None = None) -> bool:
  """Return True when ``TaskTemplateService.instantiate_template`` remains available.

  Legacy instantiation stays enabled regardless of the graph template flag until
  an explicit deprecation phase (see workflow-video-v1 W10).
  """
  _ = settings or get_settings()
  return True
