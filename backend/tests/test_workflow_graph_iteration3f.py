from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.enums import (
  TaskPriority,
  TaskSourceType,
  TaskStatus,
  UserRole,
  UserStatus,
  WorkflowGraphInstanceStatus,
  WorkflowGraphNodeType,
  WorkflowGraphTemplateStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.core.config import Settings
from app.core.exceptions import ConflictError
from app.models import (
  Task,
  User,
  WorkflowCommandReceipt,
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateNode,
  WorkflowHumanTaskLink,
  WorkflowNodeInstance,
  WorkflowOperationalIncident,
  WorkflowOutboxEvent,
)
from app.services.human_task_coordinator import HumanTaskCoordinator
from app.services.workflow_command_executor import WorkflowCommandExecutor
from app.services.workflow_iteration4_readiness_service import (
  WorkflowIteration4ReadinessService,
)
from app.services.task_service import TaskService
from app.services.workflow_graph_service import WorkflowGraphService


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


async def _projection(
  db_session,  # noqa: ANN001
  *,
  actor: User,
  iteration: int = 1,
  instance: WorkflowGraphInstance | None = None,
  instance_key: str = "singleton",
) -> tuple[Task, WorkflowGraphInstance, WorkflowNodeInstance]:
  task = Task(
    title=f"human-{iteration}",
    creator_id=actor.id,
    assignee_id=actor.id,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.TEMPLATE,
    extra_metadata={},
  )
  db_session.add(task)
  await db_session.flush()
  if instance is None:
    instance = WorkflowGraphInstance(
      initiator_user_id=actor.id,
      source_type="template",
      status=WorkflowGraphInstanceStatus.ACTIVE,
      context={},
      definition_snapshot={"format_version": 2, "nodes": [], "edges": []},
      definition_hash="a" * 64,
      engine_version="graph-v3",
      executor_kind="snapshot",
    )
    db_session.add(instance)
    await db_session.flush()
  node = WorkflowNodeInstance(
    instance_id=instance.id,
    node_key="approve",
    instance_key=instance_key,
    title="Approve",
    node_type=WorkflowGraphNodeType.TASK,
    engine_state=WorkflowNodeEngineState.ACTIVATED,
    business_state=WorkflowNodeBusinessState.DOING,
    assignee_user_id=actor.id,
    iteration=iteration,
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
@pytest.mark.workflow_i4_gate
async def test_i3f_link_records_iteration_and_supersedes_previous_link(db_session) -> None:  # noqa: ANN001
  actor = await _actor(db_session, email="i3f-supersede@example.com")
  first_task, instance, first_node = await _projection(db_session, actor=actor)
  coordinator = HumanTaskCoordinator(db_session)
  first_link = await coordinator.ensure_link(
    task_id=first_task.id,
    node_instance_id=first_node.id,
  )
  second_task, _instance, second_node = await _projection(
    db_session,
    actor=actor,
    iteration=2,
    instance=instance,
  )
  second_link = await coordinator.ensure_link(
    task_id=second_task.id,
    node_instance_id=second_node.id,
  )
  assert first_link.iteration == 1
  assert second_link.iteration == 2
  assert first_link.lifecycle == "superseded"
  assert first_link.superseded_by_link_id == second_link.id
  assert first_link.superseded_at is not None


@pytest.mark.asyncio
@pytest.mark.workflow_i4_gate
async def test_i3f_link_wins_json_mismatch_and_records_incident(db_session) -> None:  # noqa: ANN001
  actor = await _actor(db_session, email="i3f-mismatch@example.com")
  task, instance, node = await _projection(db_session, actor=actor)
  coordinator = HumanTaskCoordinator(db_session)
  await coordinator.ensure_link(task_id=task.id, node_instance_id=node.id)
  task.extra_metadata = {
    "workflow_graph_instance_id": str(uuid4()),
    "workflow_node_instance_id": str(uuid4()),
  }
  resolution = await coordinator.resolve_for_task(task=task)
  assert resolution.source == "link"
  assert resolution.instance is instance
  assert resolution.node_instance is node
  incident = await db_session.scalar(
    select(WorkflowOperationalIncident).where(
      WorkflowOperationalIncident.category == "link_mismatch"
    )
  )
  assert incident is not None
  assert incident.task_id == task.id


@pytest.mark.asyncio
@pytest.mark.workflow_i4_gate
async def test_i3f_payload_conflict_is_queryable(db_session) -> None:  # noqa: ANN001
  actor = await _actor(db_session, email="i3f-conflict@example.com")
  executor = WorkflowCommandExecutor(db_session)

  async def operation() -> dict[str, object]:
    return {"ok": True}

  await executor.execute(
    command_id="i3f-conflict-001",
    command_type="create_run",
    payload={"value": 1},
    operation=operation,
    actor_user_id=actor.id,
  )
  with pytest.raises(ConflictError, match="不同 payload"):
    await executor.execute(
      command_id="i3f-conflict-001",
      command_type="create_run",
      payload={"value": 2},
      operation=operation,
      actor_user_id=actor.id,
    )
  incident = await db_session.scalar(
    select(WorkflowOperationalIncident).where(
      WorkflowOperationalIncident.category == "receipt_conflict"
    )
  )
  assert incident is not None
  assert incident.command_receipt_id is not None


@pytest.mark.asyncio
@pytest.mark.workflow_i4_gate
async def test_i3f_command_failure_rolls_back_business_outbox_and_success_receipt(db_session) -> None:  # noqa: ANN001, E501
  actor = await _actor(db_session, email="i3f-rollback@example.com")
  executor = WorkflowCommandExecutor(db_session)

  async def operation() -> dict[str, object]:
    task = Task(
      title="must rollback",
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
      status=WorkflowGraphInstanceStatus.ACTIVE,
      context={},
    )
    db_session.add(instance)
    await db_session.flush()
    db_session.add(
      WorkflowOutboxEvent(
        instance_id=instance.id,
        event_type="workflow_node_activated",
        payload={},
        available_at=datetime.now(UTC),
      )
    )
    await db_session.flush()
    raise RuntimeError("fault-after-outbox")

  with pytest.raises(RuntimeError, match="fault-after-outbox"):
    await executor.execute(
      command_id="i3f-fault-001",
      command_type="complete_node",
      payload={"node": "fault"},
      operation=operation,
      actor_user_id=actor.id,
    )

  assert await db_session.scalar(select(func.count(Task.id)).where(Task.title == "must rollback")) == 0
  assert await db_session.scalar(select(func.count(WorkflowOutboxEvent.id))) == 0
  receipt = await db_session.scalar(
    select(WorkflowCommandReceipt).where(WorkflowCommandReceipt.command_id == "i3f-fault-001")
  )
  assert receipt is not None
  assert receipt.status == "failed"


@pytest.mark.asyncio
@pytest.mark.workflow_i4_gate
async def test_i3f_readiness_reports_engine_versions_and_migration_blockers(db_session) -> None:  # noqa: ANN001, E501
  actor = await _actor(db_session, email="i3f-ready@example.com")
  task, instance, _node = await _projection(db_session, actor=actor)
  report = await WorkflowIteration4ReadinessService(db_session).build_report()
  assert report["runtime_ready"] is False
  assert any(item["engine_version"] == "graph-v3" for item in report["engine_version_counts"])
  assert any(item.get("task_id") == str(task.id) for item in report["incomplete_objects"])

  await HumanTaskCoordinator(db_session).backfill_existing_links(dry_run=False)
  report = await WorkflowIteration4ReadinessService(db_session).build_report()
  assert report["runtime_ready"] is True
  assert report["incomplete_objects"] == []


@pytest.mark.asyncio
@pytest.mark.workflow_i4_gate
async def test_i3f_notice_only_runtime_creates_no_work_item_or_link(db_session) -> None:  # noqa: ANN001
  actor = await _actor(db_session, email="i3f-notice@example.com")
  template = WorkflowGraphTemplate(
    code="i3f-notice-only",
    base_code="i3f-notice-only",
    version=1,
    name="Notice only",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=actor.id,
  )
  db_session.add(template)
  await db_session.flush()
  db_session.add(
    WorkflowGraphTemplateNode(
      template_id=template.id,
      node_key="notice",
      title="Notice",
      node_type=WorkflowGraphNodeType.NOTICE,
      sort_order=1,
    )
  )
  await db_session.flush()
  result = await WorkflowGraphService(db_session).create_multi_node_instance(
    template_id=template.id,
    initiator_id=actor.id,
  )
  await db_session.flush()
  assert result.instance.status == WorkflowGraphInstanceStatus.COMPLETED
  assert await db_session.scalar(select(func.count(WorkflowHumanTaskLink.id))) == 0
  assert await db_session.scalar(select(func.count(Task.id))) == 0


@pytest.mark.asyncio
@pytest.mark.workflow_i4_gate
async def test_i3f_compatibility_rollback_keeps_existing_standalone_task(db_session) -> None:  # noqa: ANN001, E501
  actor = await _actor(db_session, email="i3f-rollback-standalone@example.com")
  enabled = Settings(
    jwt_secret_key="i3f-standalone-enabled-secret-123456",
    workflow_standalone_manual_tasks_enabled=True,
  )
  task_service = TaskService(db_session, settings=enabled)
  task, _ = await task_service.create_task_record(
    actor=actor,
    title="survives compatibility rollback",
    assignee_id=actor.id,
    commit=True,
  )
  assert await db_session.get(Task, task.id) is not None
  assert await db_session.scalar(
    select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == task.id)
  ) is None

  rolled_back = TaskService(
    db_session,
    settings=enabled.model_copy(update={"workflow_standalone_manual_tasks_enabled": False}),
  )
  transitioned = await rolled_back.transition_task_status(
    actor=actor,
    task_id=task.id,
    target_status=TaskStatus.DOING,
  )
  assert transitioned.id == task.id
  assert await db_session.get(Task, task.id) is not None
  assert await db_session.scalar(
    select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == task.id)
  ) is None
