"""Resolve task-center list fields aligned with frontend user-state.ts (TCE B-05)."""

from __future__ import annotations

from typing import Any

from app.core.enums import TaskStatus, WorkflowNodeBusinessState
from app.models import Task

TaskUserFacingState = str


def resolve_task_run_label(
  *,
  title: str,
  metadata: dict[str, Any] | None = None,
  graph_run_label: str | None = None,
) -> str | None:
  payload = metadata or {}
  raw_run_label = payload.get("run_label")
  if isinstance(raw_run_label, str) and raw_run_label.strip():
    return raw_run_label.strip()
  if graph_run_label and graph_run_label.strip():
    return graph_run_label.strip()
  separator_index = title.rfind(" / ")
  if separator_index >= 0:
    suffix = title[separator_index + 3 :].strip()
    if suffix:
      return suffix
  return None


def _has_rework_signal(metadata: dict[str, Any]) -> bool:
  capture_state = metadata.get("latest_capture_state")
  if capture_state in {"rejected", "returned"}:
    return True
  rework_reason = metadata.get("latest_rework_reason")
  handshake_action = metadata.get("latest_handshake_action")
  return (
    isinstance(rework_reason, str)
    and rework_reason.strip()
    and handshake_action != "assigned"
  )


def _resolve_profile_id(task: Task, metadata: dict[str, Any]) -> str:
  ui_profile = metadata.get("ui_profile")
  if isinstance(ui_profile, str) and ui_profile.strip():
    return ui_profile.strip()

  node_key = metadata.get("template_node_key") or metadata.get("workflow_node_key")
  node_key_text = str(node_key) if node_key is not None else ""
  run_kind = str(metadata.get("run_kind") or "")

  if task.source_type.value == "template" and metadata.get("workflow_graph_instance_id"):
    if run_kind == "batch" and not node_key_text:
      return "video_batch_root"
    if node_key_text.startswith("N1_") or "PROPOSE" in node_key_text:
      return "video_n1_capture"
    if node_key_text.startswith("N2_") or "AGGREGATE" in node_key_text:
      return "video_n2_aggregate"
    if node_key_text.startswith("N7_") and "ASSIGN" in node_key_text:
      return "video_capture_assign"
    if node_key_text:
      return "video_production_step"

  if metadata.get("workflow_graph_instance_id") and metadata.get("workflow_node_instance_id"):
    return "graph_manual"

  return "legacy_task"


def _map_status_fallback(status: TaskStatus) -> TaskUserFacingState:
  if status == TaskStatus.DONE:
    return "completed"
  if status == TaskStatus.REVIEW:
    return "awaiting_confirm"
  if status == TaskStatus.DOING:
    return "in_progress"
  return "pending"


def resolve_task_user_facing_state(
  *,
  task: Task,
  status: TaskStatus,
  graph_business_state: WorkflowNodeBusinessState | None = None,
  graph_node_key: str | None = None,
) -> TaskUserFacingState:
  metadata = task.extra_metadata if isinstance(task.extra_metadata, dict) else {}

  if graph_business_state == WorkflowNodeBusinessState.RETURNED_FOR_REWORK and status != TaskStatus.DONE:
    return "returned"
  if graph_business_state == WorkflowNodeBusinessState.REJECTED and status != TaskStatus.DONE:
    return "returned"

  if _has_rework_signal(metadata) and status != TaskStatus.DONE:
    return "returned"
  if status == TaskStatus.DONE:
    return "completed"

  profile_id = _resolve_profile_id(task, metadata)
  if graph_node_key:
    node_key_text = graph_node_key
    if node_key_text.startswith("N1_") or "PROPOSE" in node_key_text:
      profile_id = "video_n1_capture"
    elif node_key_text.startswith("N2_") or "AGGREGATE" in node_key_text:
      profile_id = "video_n2_aggregate"

  if graph_business_state == WorkflowNodeBusinessState.PENDING_REVIEW:
    if profile_id == "video_production_step":
      return "awaiting_confirm"
    if profile_id in {"video_n1_capture", "video_n2_aggregate"}:
      return "pending" if profile_id == "video_n2_aggregate" else "completed"

  if graph_business_state in {
    WorkflowNodeBusinessState.ASSIGNED,
    WorkflowNodeBusinessState.ACCEPTED,
  }:
    if profile_id == "graph_manual":
      return "pending"

  if profile_id == "video_batch_root":
    return "in_progress"

  if profile_id == "video_capture_assign":
    if status in {TaskStatus.TODO, TaskStatus.DOING}:
      return "pending"

  if profile_id in {"video_n1_capture", "video_n2_aggregate"}:
    if status in {TaskStatus.TODO, TaskStatus.DOING}:
      return "pending"
    if status == TaskStatus.REVIEW:
      return "pending" if profile_id == "video_n2_aggregate" else "completed"

  if profile_id == "video_production_step":
    if status == TaskStatus.REVIEW:
      return "awaiting_confirm"
    if status in {TaskStatus.TODO, TaskStatus.DOING}:
      return "pending"

  return _map_status_fallback(status)
