"""Domain-neutral template capability snapshots and legacy compatibility adapters.

The graph runtime and task projections consume this module's generic contract.
Legacy ``run_kind`` and ``video_*`` values are read only inside the adapter so
existing runs remain compatible while new templates declare capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


STRUCTURED_FORM_SUBMISSION = "structured_form_submission"
COLLECTION_FINALIZE = "collection_finalize"
AGGREGATE_CONFIRMATION = "aggregate_confirmation"
CHILD_RUN_DISPATCH = "child_run_dispatch"
DELIVERABLE_SUBMISSION = "deliverable_submission"
DELIVERABLE_ACCEPTANCE = "deliverable_acceptance"
RETURN_FOR_REWORK = "return_for_rework"

_KNOWN_CAPABILITIES = {
  STRUCTURED_FORM_SUBMISSION,
  COLLECTION_FINALIZE,
  AGGREGATE_CONFIRMATION,
  CHILD_RUN_DISPATCH,
  DELIVERABLE_SUBMISSION,
  DELIVERABLE_ACCEPTANCE,
  RETURN_FOR_REWORK,
}

_TASK_SURFACES = {
  "run_overview",
  "structured_form",
  "collection",
  "deliverable",
  "review",
  "manual",
}
_SUBMIT_MODES = {"form", "file", "form+file", "review"}
_STATE_POLICIES = {
  "default",
  "run_active",
  "submission",
  "collection",
  "deliverable",
  "review",
}
_ROOT_VISIBILITIES = {"normal", "overview", "hidden_for_non_management"}


@dataclass(frozen=True, slots=True)
class InstanceRuntimePolicy:
  notify_on_node_activation: bool = False
  archive_on_completion: bool = False
  archive_on_cancel: bool = False


def _mapping(value: object) -> dict[str, Any]:
  return dict(value) if isinstance(value, Mapping) else {}


def _legacy_kind(payload: Mapping[str, Any]) -> str:
  value = payload.get("run_kind")
  return value.strip() if isinstance(value, str) else ""


def legacy_run_kind(payload: Mapping[str, Any], *, default: str = "") -> str:
  """Read the deprecated response/storage label without granting it behavior."""
  return _legacy_kind(payload) or default


def legacy_root_ui_profile(config: Mapping[str, Any] | None) -> str | None:
  """Return the old renderer hint for dual-write compatibility only."""
  payload = dict(config or {})
  explicit = payload.get("root_ui_profile")
  if isinstance(explicit, str) and explicit.strip():
    return explicit.strip()
  run_kind = _legacy_kind(payload)
  if run_kind == "batch":
    return "video_batch_root"
  if run_kind == "production":
    return "video_production_root"
  return None


def resolve_template_category(
  config: Mapping[str, Any] | None,
  *,
  fallback: str,
) -> str:
  payload = dict(config or {})
  explicit = payload.get("category")
  if isinstance(explicit, str) and explicit.strip():
    return explicit.strip()
  return _legacy_kind(payload) or fallback


def _legacy_template_defaults(config: Mapping[str, Any]) -> dict[str, Any]:
  run_kind = _legacy_kind(config)
  if run_kind == "batch":
    return {
      "capabilities": [
        STRUCTURED_FORM_SUBMISSION,
        COLLECTION_FINALIZE,
        AGGREGATE_CONFIRMATION,
        CHILD_RUN_DISPATCH,
      ],
      "runtime": {
        "notify_on_node_activation": True,
        "archive_on_completion": False,
        "archive_on_cancel": False,
      },
      "instantiation_mode": "direct",
      "source": "legacy_run_kind",
    }
  if run_kind == "production":
    return {
      "capabilities": [
        DELIVERABLE_SUBMISSION,
        DELIVERABLE_ACCEPTANCE,
        RETURN_FOR_REWORK,
      ],
      "runtime": {
        "notify_on_node_activation": True,
        "archive_on_completion": True,
        "archive_on_cancel": True,
      },
      "instantiation_mode": "child_only",
      "source": "legacy_run_kind",
    }
  return {
    "capabilities": [],
    "runtime": {},
    "instantiation_mode": "direct",
    "source": "default",
  }


def build_template_capability_snapshot(config: Mapping[str, Any] | None) -> dict[str, Any]:
  """Build the immutable, domain-neutral capability snapshot for a Run."""
  payload = dict(config or {})
  legacy = _legacy_template_defaults(payload)
  raw_capabilities = payload.get("workflow_capabilities")
  has_explicit_capabilities = isinstance(raw_capabilities, list)
  source = "explicit" if has_explicit_capabilities else str(legacy["source"])
  capabilities = raw_capabilities if has_explicit_capabilities else legacy["capabilities"]
  normalized_capabilities = sorted({
    str(item).strip()
    for item in capabilities
    if str(item).strip() in _KNOWN_CAPABILITIES
  })

  explicit_runtime = _mapping(payload.get("runtime_policy"))
  legacy_runtime = _mapping(legacy.get("runtime"))
  runtime = {
    "notify_on_node_activation": bool(
      explicit_runtime.get(
        "notify_on_node_activation",
        legacy_runtime.get("notify_on_node_activation", False),
      )
    ),
    "archive_on_completion": bool(
      explicit_runtime.get(
        "archive_on_completion",
        legacy_runtime.get("archive_on_completion", False),
      )
    ),
    "archive_on_cancel": bool(
      explicit_runtime.get(
        "archive_on_cancel",
        legacy_runtime.get("archive_on_cancel", False),
      )
    ),
  }
  instantiation_mode = str(
    payload.get("instantiation_mode") or legacy["instantiation_mode"]
  ).strip()
  if instantiation_mode not in {"direct", "child_only"}:
    instantiation_mode = "direct"
  return {
    "schema_version": 1,
    "capabilities": normalized_capabilities,
    "runtime": runtime,
    "instantiation_mode": instantiation_mode,
    "source": source,
  }


def read_instance_capability_snapshot(context: Mapping[str, Any] | None) -> dict[str, Any]:
  payload = dict(context or {})
  snapshot = payload.get("capability_snapshot")
  if isinstance(snapshot, Mapping) and snapshot.get("schema_version") == 1:
    return dict(snapshot)
  return build_template_capability_snapshot(payload)


def instance_supports_capability(
  context: Mapping[str, Any] | None,
  capability: str,
) -> bool:
  snapshot = read_instance_capability_snapshot(context)
  return capability in set(snapshot.get("capabilities") or [])


def resolve_instance_runtime_policy(
  context: Mapping[str, Any] | None,
) -> InstanceRuntimePolicy:
  snapshot = read_instance_capability_snapshot(context)
  runtime = _mapping(snapshot.get("runtime"))
  return InstanceRuntimePolicy(
    notify_on_node_activation=runtime.get("notify_on_node_activation") is True,
    archive_on_completion=runtime.get("archive_on_completion") is True,
    archive_on_cancel=runtime.get("archive_on_cancel") is True,
  )


def resolve_template_instantiation_mode(config: Mapping[str, Any] | None) -> str:
  return str(build_template_capability_snapshot(config).get("instantiation_mode") or "direct")


def _normalize_task_capability(raw: object) -> dict[str, Any] | None:
  payload = _mapping(raw)
  surface = str(payload.get("surface") or "").strip()
  if surface not in _TASK_SURFACES:
    return None
  submit_mode_value = payload.get("submit_mode")
  submit_mode = str(submit_mode_value).strip() if submit_mode_value is not None else None
  if submit_mode not in _SUBMIT_MODES:
    submit_mode = None
  state_policy = str(payload.get("state_policy") or "default").strip()
  if state_policy not in _STATE_POLICIES:
    state_policy = "default"
  variant_value = payload.get("variant")
  variant = str(variant_value).strip() if isinstance(variant_value, str) else None
  features = _mapping(payload.get("features"))
  root_visibility = str(payload.get("root_visibility") or "normal").strip()
  if root_visibility not in _ROOT_VISIBILITIES:
    root_visibility = "normal"
  return {
    "schema_version": 1,
    "surface": surface,
    "submit_mode": submit_mode,
    "state_policy": state_policy,
    "variant": variant,
    "features": {key: value is True for key, value in features.items()},
    "root_visibility": root_visibility,
  }


def _legacy_profile_task_capability(profile: str) -> dict[str, Any] | None:
  mapping: dict[str, dict[str, Any]] = {
    "video_batch_root": {
      "surface": "run_overview",
      "state_policy": "run_active",
      "features": {"tracking": True, "run_dashboard": True},
      "root_visibility": "overview",
    },
    "video_production_root": {
      "surface": "run_overview",
      "state_policy": "run_active",
      "root_visibility": "hidden_for_non_management",
    },
    "video_n1_capture": {
      "surface": "structured_form",
      "submit_mode": "form",
      "state_policy": "submission",
      "variant": "capture",
    },
    "video_capture_assign": {
      "surface": "structured_form",
      "submit_mode": "form",
      "state_policy": "submission",
      "variant": "assignment",
    },
    "video_capture_schedule": {
      "surface": "structured_form",
      "submit_mode": "form",
      "state_policy": "submission",
      "variant": "schedule",
    },
    "video_n2_aggregate": {
      "surface": "collection",
      "state_policy": "collection",
      "features": {"capture_progress": True, "aggregate": True},
    },
    "video_production_step": {
      "surface": "deliverable",
      "submit_mode": "file",
      "state_policy": "deliverable",
      "variant": "single",
    },
    "video_production_multi": {
      "surface": "deliverable",
      "submit_mode": "file",
      "state_policy": "deliverable",
      "variant": "multi",
    },
    "video_production_platform": {
      "surface": "deliverable",
      "submit_mode": "file",
      "state_policy": "deliverable",
      "variant": "platform",
    },
    "graph_manual": {
      "surface": "manual",
      "state_policy": "default",
    },
  }
  return _normalize_task_capability(mapping.get(profile))


def resolve_node_task_capability(config: Mapping[str, Any] | None) -> dict[str, Any] | None:
  payload = dict(config or {})
  explicit = _normalize_task_capability(payload.get("task_capability"))
  if explicit is not None:
    return explicit

  ui_profile = payload.get("ui_profile")
  if isinstance(ui_profile, str):
    legacy = _legacy_profile_task_capability(ui_profile.strip())
    if legacy is not None:
      return legacy

  if isinstance(payload.get("aggregate_schema"), Mapping):
    return _normalize_task_capability({
      "surface": "collection",
      "state_policy": "collection",
      "features": {"capture_progress": True, "aggregate": True},
    })
  if isinstance(payload.get("capture_schema"), Mapping):
    return _normalize_task_capability({
      "surface": "structured_form",
      "submit_mode": "form",
      "state_policy": "submission",
    })
  completion_policy = str(payload.get("completion_policy") or "")
  if completion_policy == "on_submit_deliverable":
    return _normalize_task_capability({
      "surface": "deliverable",
      "submit_mode": "file",
      "state_policy": "deliverable",
    })
  if completion_policy == "on_review_approved":
    return _normalize_task_capability({
      "surface": "review",
      "submit_mode": "review",
      "state_policy": "review",
    })
  return None


def resolve_root_task_capability(config: Mapping[str, Any] | None) -> dict[str, Any]:
  payload = dict(config or {})
  explicit = _normalize_task_capability(payload.get("root_task_capability"))
  if explicit is not None:
    return explicit
  run_kind = _legacy_kind(payload)
  if run_kind in {"batch", "production"}:
    legacy_profile = "video_batch_root" if run_kind == "batch" else "video_production_root"
    legacy_capability = _legacy_profile_task_capability(legacy_profile)
    if legacy_capability is not None:
      return legacy_capability
  return _normalize_task_capability({
    "surface": "run_overview",
    "state_policy": "run_active",
  }) or {}


def read_task_capability(metadata: Mapping[str, Any] | None) -> dict[str, Any] | None:
  payload = dict(metadata or {})
  explicit = _normalize_task_capability(payload.get("task_capability"))
  if explicit is not None:
    return explicit
  ui_profile = payload.get("ui_profile")
  if isinstance(ui_profile, str):
    legacy = _legacy_profile_task_capability(ui_profile.strip())
    if legacy is not None:
      return legacy
  if payload.get("workflow_graph_root_task") is True:
    return resolve_root_task_capability(payload)
  return None


def resolve_task_root_visibility(metadata: Mapping[str, Any] | None) -> str:
  capability = read_task_capability(metadata)
  if capability is None:
    return "normal"
  return str(capability.get("root_visibility") or "normal")
