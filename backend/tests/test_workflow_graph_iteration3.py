from __future__ import annotations

import inspect
import re
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
from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models import (
  Task,
  User,
  WorkflowCommandReceipt,
  WorkflowGraphInstance,
  WorkflowHumanTaskLink,
  WorkflowNodeInstance,
  WorkflowOperationalIncident,
  WorkflowRunEvent,
)
from app.services.human_task_coordinator import HumanTaskCoordinator
from app.services.workflow_command_executor import WorkflowCommandExecutor
from app.services.workflow_command_receipt_service import (
  WorkflowCommandReceiptService,
  canonical_command_payload,
)
from app.services.task_service import TaskService
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_run_event_service import WorkflowRunEventService


async def _actor(db_session, *, email: str) -> User:  # noqa: ANN001
  actor = User(
    email=email,
    password_hash="hashed",
    role=UserRole.EMPLOYEE,
    status=UserStatus.ACTIVE,
  )
  db_session.add(actor)
  await db_session.flush()
  return actor


async def _legacy_projection(db_session, *, actor: User, title: str = "legacy") -> tuple[Task, WorkflowGraphInstance, WorkflowNodeInstance]:  # noqa: ANN001, E501
  task = Task(
    title=title,
    creator_id=actor.id,
    assignee_id=actor.id,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.MANUAL,
    extra_metadata={},
  )
  db_session.add(task)
  await db_session.flush()
  instance = WorkflowGraphInstance(
    initiator_user_id=actor.id,
    source_type=TaskSourceType.MANUAL.value,
    source_id=task.id,
    status=WorkflowGraphInstanceStatus.ACTIVE,
    context={},
  )
  db_session.add(instance)
  await db_session.flush()
  node = WorkflowNodeInstance(
    instance_id=instance.id,
    node_key="manual_task",
    instance_key="singleton",
    title=title,
    node_type=WorkflowGraphNodeType.TASK,
    engine_state=WorkflowNodeEngineState.ACTIVATED,
    business_state=WorkflowNodeBusinessState.ASSIGNED,
    assignee_user_id=actor.id,
    config={"task_id": str(task.id)},
  )
  db_session.add(node)
  await db_session.flush()
  task.extra_metadata = {
    "workflow_graph_instance_id": str(instance.id),
    "workflow_node_instance_id": str(node.id),
  }
  await db_session.flush()
  return task, instance, node


@pytest.mark.asyncio
async def test_human_task_link_is_idempotent_and_link_first(db_session) -> None:  # noqa: ANN001
  actor = await _actor(db_session, email="i3-link@example.com")
  task, instance, node = await _legacy_projection(db_session, actor=actor)
  coordinator = HumanTaskCoordinator(db_session)

  first = await coordinator.ensure_link(
    task_id=task.id,
    node_instance_id=node.id,
    source="backfill",
  )
  second = await coordinator.ensure_link(
    task_id=task.id,
    node_instance_id=node.id,
    source="backfill",
  )
  assert second.id == first.id

  task.extra_metadata = {
    "workflow_graph_instance_id": str(uuid4()),
    "workflow_node_instance_id": str(uuid4()),
  }
  await db_session.flush()
  resolution = await coordinator.resolve_for_task(task=task)
  assert resolution.source == "link"
  assert resolution.instance is instance
  assert resolution.node_instance is node


@pytest.mark.asyncio
async def test_human_task_link_supports_multiple_work_items_but_one_primary(db_session) -> None:  # noqa: ANN001
  actor = await _actor(db_session, email="i3-multi@example.com")
  primary_task, _instance, node = await _legacy_projection(db_session, actor=actor, title="primary")
  supporting_task = Task(
    title="supporting",
    creator_id=actor.id,
    assignee_id=actor.id,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.TEMPLATE,
    extra_metadata={},
  )
  second_primary = Task(
    title="second-primary",
    creator_id=actor.id,
    assignee_id=actor.id,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.TEMPLATE,
    extra_metadata={},
  )
  db_session.add_all([supporting_task, second_primary])
  await db_session.flush()
  coordinator = HumanTaskCoordinator(db_session)
  await coordinator.ensure_link(task_id=primary_task.id, node_instance_id=node.id)
  supporting = await coordinator.ensure_link(
    task_id=supporting_task.id,
    node_instance_id=node.id,
    link_role="supporting",
  )
  assert supporting.link_role == "supporting"

  with pytest.raises(ConflictError, match="active primary"):
    await coordinator.ensure_link(task_id=second_primary.id, node_instance_id=node.id)


@pytest.mark.asyncio
async def test_human_task_backfill_requires_cross_checked_anchors(db_session) -> None:  # noqa: ANN001
  actor = await _actor(db_session, email="i3-backfill@example.com")
  task, _instance, node = await _legacy_projection(db_session, actor=actor)
  invalid = Task(
    title="invalid-anchor",
    creator_id=actor.id,
    assignee_id=actor.id,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.MANUAL,
    extra_metadata={
      "workflow_graph_instance_id": "invalid",
      "workflow_node_instance_id": str(node.id),
    },
  )
  db_session.add(invalid)
  await db_session.flush()
  coordinator = HumanTaskCoordinator(db_session)

  dry_run = await coordinator.backfill_existing_links(dry_run=True)
  assert dry_run.scanned == 2
  assert dry_run.eligible == 1
  assert dry_run.created == 0
  assert [issue.code for issue in dry_run.issues] == ["invalid_json_anchor"]

  report = await coordinator.backfill_existing_links(dry_run=False)
  assert report.created == 1
  assert report.issues
  assert await db_session.scalar(
    select(WorkflowHumanTaskLink).where(WorkflowHumanTaskLink.task_id == task.id)
  ) is not None
  incident = await db_session.scalar(
    select(WorkflowOperationalIncident).where(
      WorkflowOperationalIncident.category == "link_backfill_issue"
    )
  )
  assert incident is not None
  assert incident.task_id == invalid.id

  await db_session.delete(invalid)
  await db_session.flush()
  report = await coordinator.backfill_existing_links(dry_run=False)
  assert report.created == 0
  link = await db_session.scalar(
    select(WorkflowHumanTaskLink).where(WorkflowHumanTaskLink.task_id == task.id)
  )
  assert link is not None
  assert link.source == "backfill"


@pytest.mark.asyncio
async def test_command_receipt_replays_first_result_and_rejects_payload_change(db_session) -> None:  # noqa: ANN001
  actor = await _actor(db_session, email="i3-command@example.com")
  service = WorkflowCommandReceiptService(db_session)
  payload = {"node_id": uuid4(), "result": {"approved": True, "score": 5}}

  first = await service.claim(
    command_id="complete-node-001",
    command_type="complete_node",
    payload=payload,
    actor_user_id=actor.id,
  )
  assert first.is_replay is False
  await service.complete(receipt=first.receipt, result={"status": "completed"})

  replay = await service.claim(
    command_id="complete-node-001",
    command_type="complete_node",
    payload={"result": {"score": 5, "approved": True}, "node_id": payload["node_id"]},
    actor_user_id=actor.id,
  )
  assert replay.is_replay is True
  assert replay.is_terminal is True
  assert replay.receipt.result == {"status": "completed"}

  with pytest.raises(ConflictError, match="不同 payload"):
    await service.claim(
      command_id="complete-node-001",
      command_type="complete_node",
      payload={"node_id": payload["node_id"], "result": {"approved": False}},
      actor_user_id=actor.id,
    )

  receipts = list(await db_session.scalars(select(WorkflowCommandReceipt)))
  assert len(receipts) == 1


def test_command_payload_is_canonical() -> None:
  entity_id = uuid4()
  assert canonical_command_payload({"b": 2, "a": entity_id}) == canonical_command_payload(
    {"a": entity_id, "b": 2}
  )


@pytest.mark.asyncio
async def test_command_executor_replays_result_and_stamps_event_envelope(db_session) -> None:  # noqa: ANN001
  actor = await _actor(db_session, email="i3-executor@example.com")
  _task, instance, _node = await _legacy_projection(db_session, actor=actor)
  executions = 0

  async def operation() -> dict[str, object]:
    nonlocal executions
    executions += 1
    await WorkflowRunEventService(db_session).append(
      instance_id=instance.id,
      event_type="test_command_applied",
      actor_user_id=actor.id,
      aggregate_version=2,
      payload={"execution": executions},
    )
    return {"instance_id": str(instance.id), "execution": executions}

  executor = WorkflowCommandExecutor(db_session)
  first = await executor.execute(
    command_id="command-envelope-001",
    command_type="test_command",
    payload={"instance_id": instance.id},
    operation=operation,
    actor_user_id=actor.id,
    aggregate_type="workflow_run",
  )
  replay = await executor.execute(
    command_id="command-envelope-001",
    command_type="test_command",
    payload={"instance_id": instance.id},
    operation=operation,
    actor_user_id=actor.id,
    aggregate_type="workflow_run",
  )

  assert replay == first
  assert executions == 1
  events = list(
    await db_session.scalars(
      select(WorkflowRunEvent).where(WorkflowRunEvent.instance_id == instance.id)
    )
  )
  assert len(events) == 1
  assert events[0].event_version == 1
  assert events[0].aggregate_version == 2
  assert events[0].command_id == "command-envelope-001"
  assert events[0].correlation_id is not None
  assert events[0].occurred_at is not None

  receipt = await db_session.scalar(
    select(WorkflowCommandReceipt).where(
      WorkflowCommandReceipt.command_id == "command-envelope-001"
    )
  )
  assert receipt is not None
  assert receipt.status == "succeeded"
  assert receipt.aggregate_id == instance.id


@pytest.mark.asyncio
async def test_command_executor_replays_first_domain_failure(db_session) -> None:  # noqa: ANN001
  actor = await _actor(db_session, email="i3-failed-command@example.com")
  executions = 0

  async def operation() -> dict[str, object]:
    nonlocal executions
    executions += 1
    raise NotFoundError("目标节点不存在。")

  executor = WorkflowCommandExecutor(db_session)
  missing_node_id = uuid4()
  for _attempt in range(2):
    with pytest.raises(NotFoundError, match="目标节点不存在"):
      await executor.execute(
        command_id="failed-command-001",
        command_type="complete_node",
        payload={"node_instance_id": str(missing_node_id)},
        operation=operation,
        actor_user_id=actor.id,
      )

  assert executions == 1
  receipt = await db_session.scalar(
    select(WorkflowCommandReceipt).where(
      WorkflowCommandReceipt.command_id == "failed-command-001"
    )
  )
  assert receipt is not None
  assert receipt.status == "failed"


@pytest.mark.asyncio
async def test_human_task_link_lifecycle_follows_runtime_resolution(db_session) -> None:  # noqa: ANN001
  actor = await _actor(db_session, email="i3-lifecycle@example.com")
  task, _instance, node = await _legacy_projection(db_session, actor=actor)
  coordinator = HumanTaskCoordinator(db_session)
  link = await coordinator.ensure_link(task_id=task.id, node_instance_id=node.id)
  now = node.created_at

  node.engine_state = WorkflowNodeEngineState.COMPLETED
  node.completed_at = now
  await coordinator.sync_link_lifecycles_for_instance(instance_id=node.instance_id)
  assert link.lifecycle == "completed"
  assert link.completed_at == now
  assert link.invalidated_at is None

  node.engine_state = WorkflowNodeEngineState.TERMINATED
  await coordinator.sync_link_lifecycles_for_instance(instance_id=node.instance_id)
  assert link.lifecycle == "invalidated"
  assert link.completed_at is None
  assert link.invalidated_at is not None


@pytest.mark.asyncio
async def test_manual_task_defaults_to_standalone_full_lifecycle(db_session) -> None:  # noqa: ANN001
  actor = await _actor(db_session, email="i3-standalone@example.com")
  service = TaskService(
    db_session,
    settings=Settings(jwt_secret_key="test-jwt-secret-key-for-suite-123456"),
    workflow_graph_service=WorkflowGraphService(db_session),
  )

  task, _ = await service.create_task_record(
    actor=actor,
    title="standalone work item",
    assignee_id=actor.id,
    commit=True,
  )
  assert await db_session.scalar(
    select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == task.id)
  ) is None
  assert await db_session.scalar(
    select(WorkflowHumanTaskLink).where(WorkflowHumanTaskLink.task_id == task.id)
  ) is None

  task = await service.transition_task_status(
    actor=actor,
    task_id=task.id,
    target_status=TaskStatus.DOING,
  )
  task = await service.transition_task_status(
    actor=actor,
    task_id=task.id,
    target_status=TaskStatus.REVIEW,
  )
  task = await service.transition_task_status(
    actor=actor,
    task_id=task.id,
    target_status=TaskStatus.DONE,
  )
  assert task.status == TaskStatus.DONE


def test_iteration3_cross_domain_write_ownership_guard() -> None:
  task_service_source = inspect.getsource(TaskService)
  runtime_service_source = inspect.getsource(WorkflowGraphService)

  assert re.search(
    r"node_instance\.(engine_state|business_state|assignee_user_id)\s*=(?!=)",
    task_service_source,
  ) is None
  assert re.search(
    r"\btask\.(status|assignee_id|extra_metadata)\s*=(?!=)",
    runtime_service_source,
  ) is None
