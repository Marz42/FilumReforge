"""Resolve task-center list fields aligned with frontend user-state.ts (TCE B-05)."""

from __future__ import annotations

from typing import Any

from app.core.enums import TaskStatus, WorkflowNodeBusinessState
from app.models import Task
from app.services.workflow_template_capability_contract import read_task_capability

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


def _map_status_fallback(status: TaskStatus) -> TaskUserFacingState:
  if status == TaskStatus.DONE:
    return "completed"
  if status == TaskStatus.BLOCKED:
    return "blocked"
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

  if status == TaskStatus.BLOCKED:
    return "blocked"
  if graph_business_state == WorkflowNodeBusinessState.RETURNED_FOR_REWORK and status != TaskStatus.DONE:
    return "returned"
  if graph_business_state == WorkflowNodeBusinessState.REJECTED and status != TaskStatus.DONE:
    return "returned"

  if _has_rework_signal(metadata) and status != TaskStatus.DONE:
    return "returned"
  if status == TaskStatus.DONE:
    return "completed"

  _ = graph_node_key  # Compatibility parameter; node names no longer drive behavior.
  task_capability = read_task_capability(metadata) or {}
  state_policy = str(task_capability.get("state_policy") or "default")
  surface = str(task_capability.get("surface") or "")

  if graph_business_state == WorkflowNodeBusinessState.PENDING_REVIEW:
    if state_policy in {"deliverable", "review"}:
      return "awaiting_confirm"
    if state_policy in {"submission", "collection"}:
      return "pending" if state_policy == "collection" else "completed"

  if graph_business_state in {
    WorkflowNodeBusinessState.ASSIGNED,
    WorkflowNodeBusinessState.ACCEPTED,
  }:
    if surface == "manual":
      return "pending"

  if state_policy == "run_active":
    return "in_progress"

  if state_policy in {"submission", "collection"}:
    if status in {TaskStatus.TODO, TaskStatus.DOING}:
      return "pending"
    if status == TaskStatus.REVIEW:
      return "pending" if state_policy == "collection" else "completed"

  if state_policy in {"deliverable", "review"}:
    if status == TaskStatus.REVIEW:
      return "awaiting_confirm"
    if status in {TaskStatus.TODO, TaskStatus.DOING}:
      return "pending"

  return _map_status_fallback(status)
