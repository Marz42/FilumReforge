from __future__ import annotations

from typing import Mapping
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.enums import (
  TaskPriority,
  TaskSourceType,
  TaskStatus,
  UserRole,
  UserStatus,
  WorkflowGraphInstanceStatus,
  WorkflowGraphNodeType,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.models import (
  Task,
  User,
  WorkflowDeliverable,
  WorkflowGraphInstance,
  WorkflowHumanTaskLink,
  WorkflowNodeInstance,
  WorkflowRunEvent,
)
from app.services.human_task_coordinator import HumanTaskCoordinator
from app.services.workflow_graph_service import SingleNodeWorkflowSeed, WorkflowGraphService
from app.services.workflow_node_handlers import (
  HumanTaskNodeHandler,
  NoticeNodeHandler,
  WorkflowCapabilityCommand,
  WorkflowCapabilityContext,
  WorkflowCapabilityOperationError,
  WorkflowCapabilityOutcome,
  WorkflowDecisionSemantic,
  WorkflowNodeHandlerNotFoundError,
  WorkflowNodeHandlerRegistrationError,
  WorkflowNodeHandlerRegistry,
  build_default_workflow_node_handler_registry,
)


def _context(
  *,
  node_type: WorkflowGraphNodeType,
  engine_state: WorkflowNodeEngineState = WorkflowNodeEngineState.PENDING,
  business_state: WorkflowNodeBusinessState = WorkflowNodeBusinessState.DRAFT,
) -> WorkflowCapabilityContext:
  return WorkflowCapabilityContext(
    node_type=node_type,
    node_key="node-a",
    engine_state=engine_state,
    business_state=business_state,
    config={},
  )


def test_i4_default_registry_is_explicit_for_supported_and_legacy_node_types() -> None:
  registry = build_default_workflow_node_handler_registry()

  assert registry.require(WorkflowGraphNodeType.TASK).capability_key == "human_task"
  assert registry.require(WorkflowGraphNodeType.NOTICE).capability_key == "notice"
  assert registry.resolve(WorkflowGraphNodeType.APPROVAL) is None
  with pytest.raises(WorkflowNodeHandlerNotFoundError, match="approval"):
    registry.require(WorkflowGraphNodeType.APPROVAL)

  with pytest.raises(WorkflowNodeHandlerRegistrationError, match="task"):
    registry.register(HumanTaskNodeHandler())


def test_i4_human_task_handler_maps_lifecycle_without_writing_runtime() -> None:
  handler = HumanTaskNodeHandler()
  activation = handler.activate(_context(node_type=WorkflowGraphNodeType.TASK))
  assert activation.outcome == WorkflowCapabilityOutcome.WAITING
  assert activation.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert activation.business_state == WorkflowNodeBusinessState.ASSIGNED
  assert activation.side_effects == ("ensure_work_item",)
  assert handler.interruptible is True
  assert handler.compensation == "terminate_work_item"

  completion = handler.command(
    _context(
      node_type=WorkflowGraphNodeType.TASK,
      engine_state=WorkflowNodeEngineState.ACTIVATED,
      business_state=WorkflowNodeBusinessState.DOING,
    ),
    command=WorkflowCapabilityCommand.COMPLETE,
    payload={"accepted": True},
  )
  assert completion.outcome == WorkflowCapabilityOutcome.SUCCEEDED
  assert completion.engine_state == WorkflowNodeEngineState.COMPLETED
  assert completion.business_state == WorkflowNodeBusinessState.DONE
  assert completion.result == {"accepted": True}
  assert completion.diagnostics["decision_semantic"] == "work_item_complete"

  cancelled = handler.cancel(
    _context(
      node_type=WorkflowGraphNodeType.TASK,
      engine_state=WorkflowNodeEngineState.ACTIVATED,
      business_state=WorkflowNodeBusinessState.DOING,
    )
  )
  assert cancelled.engine_state == WorkflowNodeEngineState.TERMINATED
  assert cancelled.business_state == WorkflowNodeBusinessState.CANCELLED

  retried = handler.retry(
    _context(
      node_type=WorkflowGraphNodeType.TASK,
      engine_state=WorkflowNodeEngineState.SUSPENDED,
      business_state=WorkflowNodeBusinessState.ASSIGNED,
    )
  )
  assert retried.engine_state == WorkflowNodeEngineState.ACTIVATED
  with pytest.raises(WorkflowCapabilityOperationError, match="FAILED/SUSPENDED"):
    handler.retry(_context(node_type=WorkflowGraphNodeType.TASK))


def test_i4_collection_finalize_is_explicit_and_allows_coordinator_contribution() -> None:
  handler = HumanTaskNodeHandler()
  coordinator_id = str(uuid4())
  contributor_ids = [coordinator_id, str(uuid4()), str(uuid4())]
  context = WorkflowCapabilityContext(
    node_type=WorkflowGraphNodeType.TASK,
    node_key="finalize-collection",
    engine_state=WorkflowNodeEngineState.ACTIVATED,
    business_state=WorkflowNodeBusinessState.DOING,
    config={"decision_semantic": WorkflowDecisionSemantic.COLLECTION_FINALIZE.value},
  )

  result = handler.command(
    context,
    command=WorkflowCapabilityCommand.FINALIZE_COLLECTION,
    payload={
      "actor_user_id": coordinator_id,
      "contributor_user_ids": contributor_ids,
      "contributor_resolution": "deliverable_current_submitter",
      "decision_subject": {
        "kind": "collection",
        "source_node_keys": ["contribution-a", "contribution-b", "contribution-c"],
      },
    },
  )

  assert result.outcome == WorkflowCapabilityOutcome.SUCCEEDED
  assert result.diagnostics == {
    "decision_semantic": "collection_finalize",
    "decision_subject": {
      "kind": "collection",
      "source_node_keys": ["contribution-a", "contribution-b", "contribution-c"],
    },
    "contributor_user_ids": contributor_ids,
    "contributor_resolution": "deliverable_current_submitter",
    "actor_is_contributor": True,
  }
  with pytest.raises(WorkflowCapabilityOperationError, match="不匹配"):
    handler.command(context, command=WorkflowCapabilityCommand.COMPLETE)
  with pytest.raises(WorkflowCapabilityOperationError, match="source_node_keys"):
    handler.command(
      context,
      command=WorkflowCapabilityCommand.FINALIZE_COLLECTION,
      payload={"decision_subject": {"kind": "collection"}},
    )


def test_i4_notice_handler_declares_automatic_non_interruptible_contract() -> None:
  handler = NoticeNodeHandler()
  assert handler.interruptible is False
  assert handler.compensation == "none"
  assert handler.declared_side_effects == ()

  completion = handler.command(
    _context(
      node_type=WorkflowGraphNodeType.NOTICE,
      engine_state=WorkflowNodeEngineState.ACTIVATED,
      business_state=WorkflowNodeBusinessState.ASSIGNED,
    ),
    command=WorkflowCapabilityCommand.COMPLETE,
    payload={"completion_mode": "automatic"},
  )
  mapped = handler.map_result(completion)
  assert mapped["capability_key"] == "notice"
  assert mapped["outcome"] == "succeeded"
  assert mapped["result"] == {"completion_mode": "automatic"}
  with pytest.raises(WorkflowCapabilityOperationError, match="不支持人工取消"):
    handler.cancel(_context(node_type=WorkflowGraphNodeType.NOTICE))


class _RecordingHumanTaskHandler(HumanTaskNodeHandler):
  def __init__(self) -> None:
    self.activations = 0
    self.commands = 0

  def activate(self, context: WorkflowCapabilityContext):  # noqa: ANN201
    self.activations += 1
    return super().activate(context)

  def command(
    self,
    context: WorkflowCapabilityContext,
    *,
    command: WorkflowCapabilityCommand,
    payload: Mapping[str, object] | None = None,
  ):  # noqa: ANN201
    self.commands += 1
    return super().command(context, command=command, payload=payload)


@pytest.mark.asyncio
async def test_i4_runtime_consumes_handler_activation_and_completion_results(db_session) -> None:  # noqa: ANN001, E501
  handler = _RecordingHumanTaskHandler()
  registry = WorkflowNodeHandlerRegistry()
  registry.register(handler)
  registry.register(NoticeNodeHandler())
  actor = User(
    email="iteration4-handler@example.com",
    password_hash="hashed",
    role=UserRole.EMPLOYEE,
    status=UserStatus.ACTIVE,
  )
  db_session.add(actor)
  await db_session.flush()
  actor_id = actor.id
  service = WorkflowGraphService(db_session, node_handler_registry=registry)

  instance, node = await service.create_single_node_instance(
    seed=SingleNodeWorkflowSeed(
      title="Iteration 4 handler contract",
      creator_id=actor_id,
      assignee_id=actor_id,
      department_id=None,
      description=None,
      due_date=None,
      priority=TaskPriority.MEDIUM,
    )
  )
  assert handler.activations == 1
  assert node.engine_state == WorkflowNodeEngineState.ACTIVATED

  task = Task(
    title="Iteration 4 linked work item",
    creator_id=actor_id,
    assignee_id=actor_id,
    status=TaskStatus.DOING,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.MANUAL,
    extra_metadata={},
  )
  db_session.add(task)
  await db_session.flush()
  link = await HumanTaskCoordinator(db_session).bind_projection_task(
    task=task,
    node_instance=node,
    source="manual_compat",
  )

  await service.complete_node_instance(
    node_instance_id=node.id,
    actor_id=actor_id,
    commit=False,
  )
  assert handler.commands == 1
  assert node.engine_state == WorkflowNodeEngineState.COMPLETED
  assert node.node_instance_version == 2
  assert link.lifecycle == "completed"
  assert link.completed_at is not None
  assert task.status == TaskStatus.DOING
  assert instance.status.value == "completed"

  event = await db_session.scalar(
    select(WorkflowRunEvent).where(WorkflowRunEvent.event_type == "node_completed")
  )
  assert event is not None
  assert event.payload["capability_result"]["capability_key"] == "human_task"
  assert event.payload["capability_result"]["outcome"] == "succeeded"
  assert event.payload["capability_result"]["diagnostics"]["decision_semantic"] == "work_item_complete"
  persisted_link = await db_session.scalar(
    select(WorkflowHumanTaskLink).where(WorkflowHumanTaskLink.id == link.id)
  )
  assert persisted_link is link


@pytest.mark.asyncio
async def test_i4_collection_coordinator_can_finalize_after_abc_contribute(db_session) -> None:  # noqa: ANN001, E501
  contributors = [
    User(
      email=f"iteration4-contributor-{index}@example.com",
      password_hash="hashed",
      role=UserRole.EMPLOYEE,
      status=UserStatus.ACTIVE,
    )
    for index in range(3)
  ]
  db_session.add_all(contributors)
  await db_session.flush()
  coordinator, contributor_b, contributor_c = contributors

  instance = WorkflowGraphInstance(
    initiator_user_id=coordinator.id,
    source_type=TaskSourceType.TEMPLATE.value,
    status=WorkflowGraphInstanceStatus.ACTIVE,
    current_node_key="finalize-collection",
    context={},
  )
  db_session.add(instance)
  await db_session.flush()

  contribution_nodes = [
    WorkflowNodeInstance(
      instance_id=instance.id,
      node_key=f"contribution-{label}",
      title=f"Contribution {label.upper()}",
      node_type=WorkflowGraphNodeType.TASK,
      engine_state=WorkflowNodeEngineState.COMPLETED,
      business_state=WorkflowNodeBusinessState.DONE,
      assignee_user_id=contributor.id,
      node_instance_version=2,
      config={},
    )
    for label, contributor in zip(
      ("a", "b", "c"),
      (coordinator, contributor_b, contributor_c),
      strict=True,
    )
  ]
  finalize_node = WorkflowNodeInstance(
    instance_id=instance.id,
    node_key="finalize-collection",
    title="Finalize collection",
    node_type=WorkflowGraphNodeType.TASK,
    engine_state=WorkflowNodeEngineState.ACTIVATED,
    business_state=WorkflowNodeBusinessState.DOING,
    assignee_user_id=coordinator.id,
    config={
      "decision_semantic": "collection_finalize",
      "decision_subject": {
        "kind": "collection",
        "source_node_keys": ["contribution-a", "contribution-b", "contribution-c"],
      },
    },
  )
  db_session.add_all([*contribution_nodes, finalize_node])
  await db_session.flush()
  db_session.add_all(
    [
      WorkflowDeliverable(
        node_instance_id=node.id,
        submitted_by_user_id=contributor.id,
        summary=f"Submission {index}",
        payload={},
        signature=f"submission-{index}",
      )
      for index, (node, contributor) in enumerate(
        zip(contribution_nodes, contributors, strict=True),
        start=1,
      )
    ]
  )
  await db_session.flush()

  await WorkflowGraphService(db_session).complete_node_instance(
    node_instance_id=finalize_node.id,
    actor_id=coordinator.id,
    commit=False,
  )

  assert finalize_node.engine_state == WorkflowNodeEngineState.COMPLETED
  event = await db_session.scalar(
    select(WorkflowRunEvent).where(
      WorkflowRunEvent.event_type == "node_completed",
      WorkflowRunEvent.actor_user_id == coordinator.id,
    )
  )
  assert event is not None
  diagnostics = event.payload["capability_result"]["diagnostics"]
  assert diagnostics["decision_semantic"] == "collection_finalize"
  assert set(diagnostics["contributor_user_ids"]) == {
    str(contributor.id) for contributor in contributors
  }
  assert diagnostics["contributor_resolution"] == "deliverable_current_submitter"
  assert diagnostics["actor_is_contributor"] is True
