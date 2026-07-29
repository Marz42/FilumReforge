from __future__ import annotations

from datetime import UTC, datetime
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
  WorkflowOutboxEvent,
  WorkflowRunEvent,
)
from app.services.human_task_coordinator import HumanTaskCoordinator
from app.services.workflow_graph_service import SingleNodeWorkflowSeed, WorkflowGraphService
from app.services.workflow_node_handlers import (
  ApprovalNodeHandler,
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


def test_i4_approval_handler_blocks_same_subject_submitter_without_fallback() -> None:
  handler = ApprovalNodeHandler()
  actor_id = str(uuid4())
  context = WorkflowCapabilityContext(
    node_type=WorkflowGraphNodeType.APPROVAL,
    node_key="accept-deliverable",
    engine_state=WorkflowNodeEngineState.ACTIVATED,
    business_state=WorkflowNodeBusinessState.PENDING_REVIEW,
    config={"decision_semantic": "deliverable_acceptance"},
  )

  result = handler.command(
    context,
    command=WorkflowCapabilityCommand.APPROVE,
    payload={
      "actor_user_id": actor_id,
      "contributor_user_ids": [actor_id],
      "decision_maker_user_ids": [actor_id],
      "decision_subject": {"kind": "deliverable", "version": 2},
    },
  )

  assert result.outcome == WorkflowCapabilityOutcome.BLOCKED
  assert result.engine_state == WorkflowNodeEngineState.SUSPENDED
  assert result.diagnostics["policy_code"] == "submitter_cannot_be_only_acceptor"
  assert result.diagnostics["decision_subject"] == {"kind": "deliverable", "version": 2}
  assert "self_review_fallback" not in result.diagnostics


def test_i4_approval_handler_scopes_overlap_to_current_decision_subject() -> None:
  handler = ApprovalNodeHandler()
  actor_id = str(uuid4())
  current_submitter_id = str(uuid4())
  context = WorkflowCapabilityContext(
    node_type=WorkflowGraphNodeType.APPROVAL,
    node_key="accept-distinct-deliverable",
    engine_state=WorkflowNodeEngineState.ACTIVATED,
    business_state=WorkflowNodeBusinessState.PENDING_REVIEW,
    config={"decision_semantic": "deliverable_acceptance"},
  )

  result = handler.command(
    context,
    command=WorkflowCapabilityCommand.APPROVE,
    payload={
      "actor_user_id": actor_id,
      "contributor_user_ids": [current_submitter_id],
      "decision_maker_user_ids": [actor_id],
      "decision_subject": {"kind": "deliverable", "version": 3},
    },
  )

  assert result.outcome == WorkflowCapabilityOutcome.SUCCEEDED
  assert result.engine_state == WorkflowNodeEngineState.COMPLETED
  assert result.diagnostics["actor_is_contributor"] is False
  assert result.diagnostics["policy_code"] == "deliverable_acceptance_allowed"


def test_i4_approval_handler_allows_configured_contributor_cosign_only_with_independent_peer() -> None:
  handler = ApprovalNodeHandler()
  contributor_id = str(uuid4())
  independent_id = str(uuid4())
  context = WorkflowCapabilityContext(
    node_type=WorkflowGraphNodeType.APPROVAL,
    node_key="cosign",
    engine_state=WorkflowNodeEngineState.ACTIVATED,
    business_state=WorkflowNodeBusinessState.PENDING_REVIEW,
    config={
      "decision_semantic": "cosign",
      "allow_contributor_cosign": True,
    },
  )

  allowed = handler.command(
    context,
    command=WorkflowCapabilityCommand.APPROVE,
    payload={
      "actor_user_id": contributor_id,
      "contributor_user_ids": [contributor_id],
      "decision_maker_user_ids": [contributor_id, independent_id],
    },
  )
  blocked = handler.command(
    context,
    command=WorkflowCapabilityCommand.APPROVE,
    payload={
      "actor_user_id": contributor_id,
      "contributor_user_ids": [contributor_id],
      "decision_maker_user_ids": [contributor_id],
    },
  )

  assert allowed.outcome == WorkflowCapabilityOutcome.SUCCEEDED
  assert allowed.diagnostics["policy_code"] == "cosign_allowed"
  assert blocked.outcome == WorkflowCapabilityOutcome.BLOCKED
  assert blocked.diagnostics["policy_code"] == "contributor_cannot_be_only_cosign_decider"


def test_i4_approval_handler_requires_explicit_semantic_and_decision_maker() -> None:
  handler = ApprovalNodeHandler()
  assert handler.validate_definition({}) == (
    "Approval 必须显式配置 decision_semantic。",
  )
  context = WorkflowCapabilityContext(
    node_type=WorkflowGraphNodeType.APPROVAL,
    node_key="business-approval",
    engine_state=WorkflowNodeEngineState.ACTIVATED,
    business_state=WorkflowNodeBusinessState.PENDING_REVIEW,
    config={"decision_semantic": "business_approval"},
  )
  actor_id = str(uuid4())
  no_candidate_result = handler.command(
    context,
    command=WorkflowCapabilityCommand.APPROVE,
    payload={
      "actor_user_id": actor_id,
      "contributor_user_ids": [],
      "decision_maker_user_ids": [],
    },
  )
  contributor_result = handler.command(
    context,
    command=WorkflowCapabilityCommand.APPROVE,
    payload={
      "actor_user_id": actor_id,
      "contributor_user_ids": [actor_id],
      "decision_maker_user_ids": [actor_id],
    },
  )
  assert no_candidate_result.outcome == WorkflowCapabilityOutcome.BLOCKED
  assert no_candidate_result.diagnostics["policy_code"] == "no_eligible_decision_maker"
  assert contributor_result.outcome == WorkflowCapabilityOutcome.BLOCKED
  assert (
    contributor_result.diagnostics["policy_code"]
    == "contributor_cannot_approve_business_subject"
  )


class _RecordingHumanTaskHandler(HumanTaskNodeHandler):
  def __init__(self) -> None:
    self.activations = 0
    self.commands = 0
    self.cancellations = 0
    self.retries = 0

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

  def cancel(self, context: WorkflowCapabilityContext):  # noqa: ANN201
    self.cancellations += 1
    return super().cancel(context)

  def retry(self, context: WorkflowCapabilityContext):  # noqa: ANN201
    self.retries += 1
    return super().retry(context)


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


@pytest.mark.asyncio
async def test_i4_admin_cancel_consumes_human_task_handler_result(db_session) -> None:  # noqa: ANN001, E501
  handler = _RecordingHumanTaskHandler()
  registry = WorkflowNodeHandlerRegistry()
  registry.register(handler)
  registry.register(NoticeNodeHandler())
  actor = User(
    email="iteration4-cancel@example.com",
    password_hash="hashed",
    role=UserRole.ADMIN,
    status=UserStatus.ACTIVE,
  )
  db_session.add(actor)
  await db_session.flush()
  service = WorkflowGraphService(db_session, node_handler_registry=registry)
  instance, node = await service.create_single_node_instance(
    seed=SingleNodeWorkflowSeed(
      title="Cancel through capability result",
      creator_id=actor.id,
      assignee_id=actor.id,
      department_id=None,
      description=None,
      due_date=None,
      priority=TaskPriority.MEDIUM,
    )
  )
  task = Task(
    title="Linked cancellable work item",
    creator_id=actor.id,
    assignee_id=actor.id,
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

  await service.cancel_instance_by_admin(
    actor_id=actor.id,
    instance_id=instance.id,
    reason="cancel contract test",
  )
  await db_session.flush()

  assert handler.cancellations == 1
  assert node.engine_state == WorkflowNodeEngineState.TERMINATED
  assert node.business_state == WorkflowNodeBusinessState.CANCELLED
  assert node.node_instance_version == 2
  assert link.lifecycle == "cancelled"
  assert task.status == TaskStatus.DOING
  event = await db_session.scalar(
    select(WorkflowRunEvent).where(WorkflowRunEvent.event_type == "node_cancelled")
  )
  assert event is not None
  assert event.payload["reason"] == "cancel contract test"
  assert event.payload["capability_result"]["outcome"] == "cancelled"
  assert event.payload["capability_result"]["side_effects"] == ["terminate_work_item"]


@pytest.mark.asyncio
async def test_i4_retry_restores_runtime_link_event_and_outbox_in_one_uow(db_session) -> None:  # noqa: ANN001, E501
  handler = _RecordingHumanTaskHandler()
  registry = WorkflowNodeHandlerRegistry()
  registry.register(handler)
  registry.register(NoticeNodeHandler())
  actor = User(
    email="iteration4-retry@example.com",
    password_hash="hashed",
    role=UserRole.EMPLOYEE,
    status=UserStatus.ACTIVE,
  )
  db_session.add(actor)
  await db_session.flush()
  instance = WorkflowGraphInstance(
    initiator_user_id=actor.id,
    source_type=TaskSourceType.TEMPLATE.value,
    status=WorkflowGraphInstanceStatus.FAILED,
    current_node_key=None,
    result="failed",
    diagnostics={"code": "capability_failed"},
    context={
      "run_kind": "production",
      "failure": {"code": "capability_failed"},
    },
    completed_at=datetime.now(UTC),
  )
  db_session.add(instance)
  await db_session.flush()
  node = WorkflowNodeInstance(
    instance_id=instance.id,
    node_key="retry-human-task",
    title="Retry HumanTask",
    node_type=WorkflowGraphNodeType.TASK,
    engine_state=WorkflowNodeEngineState.FAILED,
    business_state=WorkflowNodeBusinessState.DOING,
    assignee_user_id=actor.id,
    node_instance_version=2,
    config={},
  )
  db_session.add(node)
  await db_session.flush()
  task = Task(
    title="Retry linked work item",
    creator_id=actor.id,
    assignee_id=actor.id,
    status=TaskStatus.DOING,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.TEMPLATE,
    extra_metadata={},
  )
  db_session.add(task)
  await db_session.flush()
  link = await HumanTaskCoordinator(db_session).bind_projection_task(
    task=task,
    node_instance=node,
    source="manual_compat",
  )
  link.lifecycle = "invalidated"
  link.invalidated_at = datetime.now(UTC)
  await db_session.commit()
  instance_id = instance.id
  node_id = node.id
  link_id = link.id
  task_id = task.id

  await WorkflowGraphService(db_session, node_handler_registry=registry).retry_node_instance(
    node_instance_id=node_id,
    actor_id=actor.id,
    commit=False,
  )

  assert handler.retries == 1
  assert node.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert node.business_state == WorkflowNodeBusinessState.ASSIGNED
  assert node.node_instance_version == 3
  assert link.lifecycle == "active"
  assert link.invalidated_at is None
  assert task.status == TaskStatus.DOING
  assert instance.status == WorkflowGraphInstanceStatus.ACTIVE
  assert instance.result is None
  assert instance.diagnostics == {}
  assert "failure" not in instance.context
  assert instance.current_node_key == node.node_key
  event = await db_session.scalar(
    select(WorkflowRunEvent).where(WorkflowRunEvent.event_type == "node_retried")
  )
  assert event is not None
  assert event.payload["capability_result"]["outcome"] == "waiting"
  outbox = await db_session.scalar(
    select(WorkflowOutboxEvent).where(
      WorkflowOutboxEvent.event_type == "workflow_node_activated"
    )
  )
  assert outbox is not None
  assert outbox.node_instance_id == node.id

  await db_session.rollback()
  persisted_instance = await db_session.get(WorkflowGraphInstance, instance_id)
  persisted_node = await db_session.get(WorkflowNodeInstance, node_id)
  persisted_link = await db_session.get(WorkflowHumanTaskLink, link_id)
  persisted_task = await db_session.get(Task, task_id)
  assert persisted_instance is not None
  assert persisted_instance.status == WorkflowGraphInstanceStatus.FAILED
  assert persisted_instance.result == "failed"
  assert persisted_instance.context["failure"]["code"] == "capability_failed"
  assert persisted_node is not None
  assert persisted_node.engine_state == WorkflowNodeEngineState.FAILED
  assert persisted_node.node_instance_version == 2
  assert persisted_link is not None
  assert persisted_link.lifecycle == "invalidated"
  assert persisted_task is not None
  assert persisted_task.status == TaskStatus.DOING
  assert await db_session.scalar(
    select(WorkflowRunEvent.id).where(WorkflowRunEvent.event_type == "node_retried")
  ) is None
  assert await db_session.scalar(
    select(WorkflowOutboxEvent.id).where(
      WorkflowOutboxEvent.event_type == "workflow_node_activated"
    )
  ) is None


@pytest.mark.asyncio
async def test_i4_prior_contribution_does_not_block_a_distinct_downstream_work_item(db_session) -> None:  # noqa: ANN001, E501
  actor = User(
    email="iteration4-distinct-subject@example.com",
    password_hash="hashed",
    role=UserRole.EMPLOYEE,
    status=UserStatus.ACTIVE,
  )
  db_session.add(actor)
  await db_session.flush()
  instance = WorkflowGraphInstance(
    initiator_user_id=actor.id,
    source_type=TaskSourceType.TEMPLATE.value,
    status=WorkflowGraphInstanceStatus.ACTIVE,
    current_node_key="downstream-delivery",
    context={},
  )
  db_session.add(instance)
  await db_session.flush()
  upstream = WorkflowNodeInstance(
    instance_id=instance.id,
    node_key="upstream-contribution",
    title="Upstream contribution",
    node_type=WorkflowGraphNodeType.TASK,
    engine_state=WorkflowNodeEngineState.COMPLETED,
    business_state=WorkflowNodeBusinessState.DONE,
    assignee_user_id=actor.id,
    node_instance_version=2,
    config={},
  )
  downstream = WorkflowNodeInstance(
    instance_id=instance.id,
    node_key="downstream-delivery",
    title="Distinct downstream delivery",
    node_type=WorkflowGraphNodeType.TASK,
    engine_state=WorkflowNodeEngineState.ACTIVATED,
    business_state=WorkflowNodeBusinessState.DOING,
    assignee_user_id=actor.id,
    config={"decision_semantic": "work_item_complete"},
  )
  db_session.add_all([upstream, downstream])
  await db_session.flush()
  db_session.add(
    WorkflowDeliverable(
      node_instance_id=upstream.id,
      submitted_by_user_id=actor.id,
      summary="Earlier contribution",
      payload={},
      signature="earlier-contribution",
    )
  )
  await db_session.flush()

  await WorkflowGraphService(db_session).complete_node_instance(
    node_instance_id=downstream.id,
    actor_id=actor.id,
    commit=False,
  )

  assert downstream.engine_state == WorkflowNodeEngineState.COMPLETED
  events = list(
    await db_session.scalars(
      select(WorkflowRunEvent).where(WorkflowRunEvent.event_type == "node_completed")
    )
  )
  event = next(
    item for item in events if item.payload["node_instance_id"] == str(downstream.id)
  )
  diagnostics = event.payload["capability_result"]["diagnostics"]
  assert diagnostics["decision_semantic"] == "work_item_complete"
  assert diagnostics["decision_subject"] == {
    "kind": "work_item",
    "node_instance_id": str(downstream.id),
  }
  assert diagnostics["contributor_user_ids"] == []
  assert diagnostics["actor_is_contributor"] is False
