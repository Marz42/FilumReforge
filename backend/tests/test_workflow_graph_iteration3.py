from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.enums import (
  TaskPriority,
  TaskSourceType,
  UserRole,
  UserStatus,
  WorkflowGraphInstanceStatus,
  WorkflowGraphNodeType,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.core.exceptions import ConflictError
from app.models import (
  Task,
  User,
  WorkflowCommandReceipt,
  WorkflowGraphInstance,
  WorkflowHumanTaskLink,
  WorkflowNodeInstance,
)
from app.services.human_task_coordinator import HumanTaskCoordinator
from app.services.workflow_command_receipt_service import (
  WorkflowCommandReceiptService,
  canonical_command_payload,
)


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
