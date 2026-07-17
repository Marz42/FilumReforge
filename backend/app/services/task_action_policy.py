"""Unified Work Item action contract (Iteration 3 downstream adaptation).

Iteration 3 decoupled standalone Task from the graph engine. Task center
bucketing, detail actions, and delegation must therefore be derived from the
Work Item itself — its relations, status and assignment policy — *not* from the
presence of a WorkflowGraphInstance / NodeInstance / HumanTaskLink.

This module centralises those derivations so the API, task center and frontend
consume a single, stable contract instead of re-inferring capabilities from
graph metadata.

Scope of this pass: ``direct`` assignment for standalone Task. The ``handshake``
assignment mode (PENDING_ACCEPTANCE / DECLINED) is reserved for the next batch;
the DTO already carries ``assignment_mode`` so it can be added without another
contract break.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.core.enums import (
  TaskAssignmentMode,
  TaskExecutionMode,
  TaskSourceType,
  TaskStatus,
)
from app.models import Task, User

# Action identifiers shared with the frontend. Each maps to a real endpoint.
ACTION_START_WORK = "start_work"
ACTION_SUBMIT_DELIVERABLE = "submit_deliverable"
ACTION_DELEGATE_ASSIGNMENT = "delegate_assignment"
ACTION_APPROVE_DELIVERABLE = "approve_deliverable"
ACTION_RETURN_FOR_REWORK = "return_for_rework"
ACTION_ACCEPT_ASSIGNMENT = "accept_assignment"
ACTION_REJECT_ASSIGNMENT = "reject_assignment"

_ACTION_LABELS: dict[str, tuple[str, str]] = {
  ACTION_START_WORK: ("开始处理", "primary"),
  ACTION_SUBMIT_DELIVERABLE: ("提交交付", "warning"),
  ACTION_DELEGATE_ASSIGNMENT: ("转办", "warning"),
  ACTION_APPROVE_DELIVERABLE: ("通过验收", "success"),
  ACTION_RETURN_FOR_REWORK: ("打回返工", "danger"),
  ACTION_ACCEPT_ASSIGNMENT: ("接受任务", "primary"),
  ACTION_REJECT_ASSIGNMENT: ("退回协商", "danger"),
}


@dataclass(frozen=True, slots=True)
class ActionOption:
  action: str
  label: str
  button_type: str = "primary"


@dataclass(frozen=True, slots=True)
class WorkItemActionContext:
  """Per-actor, read-only capability snapshot for a Work Item."""

  execution_mode: str
  assignment_mode: str
  current_action_owner_id: UUID | None
  requires_action: bool
  action_type: str | None
  available_actions: list[ActionOption] = field(default_factory=list)


def _action_option(action: str) -> ActionOption:
  label, button_type = _ACTION_LABELS[action]
  return ActionOption(action=action, label=label, button_type=button_type)


def uses_graph_projection(task: Task) -> bool:
  """A manual Task carrying graph identity is a legacy single-node graph task."""
  metadata = task.extra_metadata or {}
  return bool(metadata.get("workflow_graph_instance_id")) and bool(
    metadata.get("workflow_node_instance_id")
  )


def derive_execution_mode(task: Task) -> str:
  if task.source_type == TaskSourceType.TEMPLATE:
    return TaskExecutionMode.WORKFLOW.value
  if uses_graph_projection(task):
    return TaskExecutionMode.WORKFLOW.value
  return TaskExecutionMode.STANDALONE.value


def is_standalone(task: Task) -> bool:
  return derive_execution_mode(task) == TaskExecutionMode.STANDALONE.value


def standalone_action_owner_id(task: Task) -> UUID | None:
  """Who must act next on a standalone Task.

  TODO / DOING → assignee (execution); REVIEW → creator (acceptance); DONE → none.
  """
  if task.status == TaskStatus.DONE:
    return None
  if task.status == TaskStatus.REVIEW:
    return task.creator_id
  return task.assignee_id


def _standalone_available_actions(
  *,
  task: Task,
  actor: User,
  is_management: bool,
) -> list[ActionOption]:
  actions: list[str] = []
  is_assignee = actor.id == task.assignee_id
  is_creator = actor.id == task.creator_id
  can_handle_execution = is_assignee or is_management
  can_review = is_creator or is_management

  if task.status == TaskStatus.TODO:
    if can_handle_execution:
      actions.append(ACTION_START_WORK)
      # REVIEW-stage delegation is forbidden by product decision; TODO/DOING allow it.
      actions.append(ACTION_DELEGATE_ASSIGNMENT)
  elif task.status == TaskStatus.DOING:
    if can_handle_execution:
      actions.append(ACTION_SUBMIT_DELIVERABLE)
      actions.append(ACTION_DELEGATE_ASSIGNMENT)
  elif task.status == TaskStatus.REVIEW:
    if can_review:
      actions.append(ACTION_APPROVE_DELIVERABLE)
      actions.append(ACTION_RETURN_FOR_REWORK)

  return [_action_option(action) for action in actions]


def _standalone_action_type(*, task: Task) -> str | None:
  if task.status == TaskStatus.TODO:
    return ACTION_START_WORK
  if task.status == TaskStatus.DOING:
    return ACTION_SUBMIT_DELIVERABLE
  if task.status == TaskStatus.REVIEW:
    return "review_deliverable"
  return None


def build_standalone_action_context(
  *,
  task: Task,
  actor: User,
  is_management: bool,
) -> WorkItemActionContext:
  owner_id = standalone_action_owner_id(task)
  actor_is_owner = owner_id is not None and owner_id == actor.id
  action_type = _standalone_action_type(task=task) if actor_is_owner or is_management else None
  return WorkItemActionContext(
    execution_mode=TaskExecutionMode.STANDALONE.value,
    assignment_mode=task.assignment_mode or TaskAssignmentMode.DIRECT.value,
    current_action_owner_id=owner_id,
    requires_action=actor_is_owner and action_type is not None,
    action_type=action_type,
    available_actions=_standalone_available_actions(
      task=task,
      actor=actor,
      is_management=is_management,
    ),
  )
