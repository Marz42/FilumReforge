from __future__ import annotations

from typing import Mapping
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.enums import (
  TaskPriority,
  WorkflowGraphNodeType,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.models import WorkflowRunEvent
from app.services.workflow_graph_service import SingleNodeWorkflowSeed, WorkflowGraphService
from app.services.workflow_node_handlers import (
  HumanTaskNodeHandler,
  NoticeNodeHandler,
  WorkflowCapabilityCommand,
  WorkflowCapabilityContext,
  WorkflowCapabilityOperationError,
  WorkflowCapabilityOutcome,
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
  actor_id = uuid4()
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

  await service.complete_node_instance(
    node_instance_id=node.id,
    actor_id=actor_id,
    commit=False,
  )
  assert handler.commands == 1
  assert node.engine_state == WorkflowNodeEngineState.COMPLETED
  assert instance.status.value == "completed"

  event = await db_session.scalar(
    select(WorkflowRunEvent).where(WorkflowRunEvent.event_type == "node_completed")
  )
  assert event is not None
  assert event.payload["capability_result"]["capability_key"] == "human_task"
  assert event.payload["capability_result"]["outcome"] == "succeeded"
