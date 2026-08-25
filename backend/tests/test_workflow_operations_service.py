from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
  UserRole,
  UserStatus,
  WorkflowGraphInstanceStatus,
  WorkflowGraphNodeType,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
  WorkflowOutboxEventStatus,
)
from app.core.exceptions import ConflictError
from app.core.request_context import bind_request_context, reset_request_context
from app.models import (
  ProjectionCheckpoint,
  User,
  WorkflowGraphInstance,
  WorkflowEdgeTraversal,
  WorkflowNodeActivationDependency,
  WorkflowNodeInstance,
  WorkflowOperationalIncident,
  WorkflowOutboxEvent,
  WorkflowRunEvent,
)
from app.services.workflow_event_context import bind_workflow_event_context
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_operational_incident_service import WorkflowOperationalIncidentService
from app.services.workflow_operations_service import WorkflowOperationsService
from app.services.workflow_run_event_service import WorkflowRunEventService
from app.services.strict_projection_telemetry import strict_projection_telemetry


async def _seed_runtime(db_session: AsyncSession) -> dict[str, object]:
  now = datetime.now(UTC)
  admin = User(
    email="workflow-ops-admin@example.com",
    password_hash="test",
    role=UserRole.ADMIN,
    status=UserStatus.ACTIVE,
  )
  db_session.add(admin)
  await db_session.flush()

  failed_run = WorkflowGraphInstance(
    initiator_user_id=admin.id,
    status=WorkflowGraphInstanceStatus.FAILED,
    current_node_key="route",
    context={},
    diagnostics={"code": "no_route", "message": "没有匹配路径"},
    context_version=1,
    max_iterations=5,
  )
  waiting_run = WorkflowGraphInstance(
    initiator_user_id=admin.id,
    status=WorkflowGraphInstanceStatus.ACTIVE,
    current_node_key="join",
    context={},
    diagnostics={},
    context_version=1,
    max_iterations=5,
  )
  stalled_run = WorkflowGraphInstance(
    initiator_user_id=admin.id,
    status=WorkflowGraphInstanceStatus.ACTIVE,
    current_node_key="missing",
    context={},
    diagnostics={},
    context_version=1,
    max_iterations=5,
  )
  db_session.add_all([failed_run, waiting_run, stalled_run])
  await db_session.flush()
  stalled_run.updated_at = now - timedelta(hours=2)

  waiting_node = WorkflowNodeInstance(
    instance_id=waiting_run.id,
    node_key="join",
    title="等待汇聚",
    node_type=WorkflowGraphNodeType.TASK,
    engine_state=WorkflowNodeEngineState.PENDING,
    business_state=WorkflowNodeBusinessState.DRAFT,
    iteration=1,
    node_instance_version=1,
  )
  source_node = WorkflowNodeInstance(
    instance_id=waiting_run.id,
    node_key="source",
    title="来源",
    node_type=WorkflowGraphNodeType.TASK,
    engine_state=WorkflowNodeEngineState.COMPLETED,
    business_state=WorkflowNodeBusinessState.DONE,
    iteration=1,
    node_instance_version=1,
  )
  retry_node = WorkflowNodeInstance(
    instance_id=failed_run.id,
    node_key="route",
    title="失败任务",
    node_type=WorkflowGraphNodeType.TASK,
    engine_state=WorkflowNodeEngineState.FAILED,
    business_state=WorkflowNodeBusinessState.DOING,
    iteration=1,
    node_instance_version=2,
  )
  db_session.add_all([waiting_node, source_node, retry_node])
  await db_session.flush()
  traversal = WorkflowEdgeTraversal(
    instance_id=waiting_run.id,
    source_node_instance_id=source_node.id,
    iteration=1,
    from_node_key="source",
    to_node_key="join",
    status="taken",
    condition={},
    evidence={},
    context_version=1,
  )
  db_session.add(traversal)
  await db_session.flush()
  dependency = WorkflowNodeActivationDependency(
    instance_id=waiting_run.id,
    node_instance_id=waiting_node.id,
    source_node_instance_id=source_node.id,
    traversal_id=traversal.id,
    iteration=1,
    target_node_key="join",
    status="waiting",
  )
  db_session.add(dependency)
  await db_session.flush()
  dependency.created_at = now - timedelta(minutes=45)

  outbox = WorkflowOutboxEvent(
    instance_id=failed_run.id,
    node_instance_id=retry_node.id,
    event_type="node_activated",
    status=WorkflowOutboxEventStatus.FAILED,
    attempt_count=5,
    available_at=now - timedelta(hours=1),
    last_error="delivery failed",
    payload={"recipient_user_id": str(admin.id)},
  )
  checkpoint = ProjectionCheckpoint(
    projection_name="workflow_read_models",
    stream_name="workflow_run_events",
    status="failed",
    processed_count=12,
    attempt_count=1,
    last_error="projector stopped",
  )
  incident = WorkflowOperationalIncident(
    category="coordinator_failure",
    status="open",
    severity="error",
    fingerprint="a" * 64,
    occurrence_count=1,
    first_seen_at=now,
    last_seen_at=now,
    instance_id=failed_run.id,
    node_instance_id=retry_node.id,
    details={"error_type": "RuntimeError"},
  )
  db_session.add_all([outbox, checkpoint, incident])
  await db_session.flush()
  return {
    "admin": admin,
    "failed_run": failed_run,
    "stalled_run": stalled_run,
    "retry_node": retry_node,
    "outbox": outbox,
    "incident": incident,
  }


@pytest.mark.asyncio
async def test_operations_dashboard_aggregates_actionable_health_without_payloads(
  db_session: AsyncSession,
) -> None:
  seeded = await _seed_runtime(db_session)

  dashboard = await WorkflowOperationsService(db_session).build_dashboard(
    stalled_minutes=30,
    limit=20,
  )

  assert dashboard["metrics"]["runs"]["failed"] == 1
  assert dashboard["metrics"]["runs"]["active"] == 2
  assert dashboard["metrics"]["stalled_run_count"] == 1
  assert dashboard["metrics"]["join_wait_count"] == 1
  assert dashboard["metrics"]["oldest_join_wait_seconds"] >= 40 * 60
  assert dashboard["metrics"]["outbox"]["failed"] == 1
  assert dashboard["metrics"]["outbox_backlog_count"] == 1
  assert dashboard["metrics"]["projection_failed_stream_count"] == 1
  assert {item["category"] for item in dashboard["issues"]} >= {
    "no_route",
    "stalled_run",
    "join_wait",
  }
  assert dashboard["failed_outbox"][0]["id"] == str(seeded["outbox"].id)
  assert "payload" not in dashboard["failed_outbox"][0]


@pytest.mark.asyncio
async def test_operations_dashboard_surfaces_strict_projection_gap_with_trace_and_checkpoint(
  db_session: AsyncSession,
) -> None:
  await _seed_runtime(db_session)
  checkpoint = await db_session.scalar(select(ProjectionCheckpoint))
  assert checkpoint is not None
  checkpoint.last_success_at = datetime.now(UTC) - timedelta(seconds=30)
  task_id = uuid4()
  request_token = bind_request_context(
    request_id="ki-015-operations-trace",
    http_method="GET",
    path="/api/v1/task-center/inbox",
  )
  try:
    strict_projection_telemetry.record(
      surface="inbox",
      reason="unsupported_schema",
      projection_schema_version=99,
      task_id=task_id,
    )
  finally:
    reset_request_context(request_token)

  dashboard = await WorkflowOperationsService(db_session).build_dashboard()

  assert dashboard["metrics"]["strict_projection_gap_count"] == 1
  assert dashboard["strict_projection_gaps"]["dimensions"] == [
    {
      "surface": "inbox",
      "reason": "unsupported_schema",
      "projection_schema_version": 99,
      "count": 1,
    }
  ]
  recent = dashboard["strict_projection_gaps"]["recent"][0]
  assert recent["task_id"] == str(task_id)
  assert recent["request_id"] == "ki-015-operations-trace"
  assert recent["checkpoint_stream_name"] == "workflow_run_events"
  assert recent["checkpoint_status"] == "failed"
  assert recent["checkpoint_last_success_at"] == checkpoint.last_success_at
  alert = dashboard["issues"][0]
  assert alert["category"] == "strict_projection_gap"
  assert alert["task_id"] == str(task_id)
  assert alert["request_id"] == "ki-015-operations-trace"


@pytest.mark.asyncio
async def test_outbox_manual_replay_and_incident_resolution_are_audited(
  db_session: AsyncSession,
) -> None:
  seeded = await _seed_runtime(db_session)
  service = WorkflowOperationsService(db_session)
  admin = seeded["admin"]
  outbox = seeded["outbox"]
  incident = seeded["incident"]
  assert isinstance(admin, User)
  assert isinstance(outbox, WorkflowOutboxEvent)
  assert isinstance(incident, WorkflowOperationalIncident)

  replay = await service.replay_outbox(
    outbox_event_id=outbox.id,
    actor_user_id=admin.id,
    reason="生产通知通道恢复后人工重放",
  )
  assert replay["status"] == "retrying"
  assert outbox.attempt_count == 0
  assert outbox.manual_replay_count == 1
  assert outbox.last_replayed_by_user_id == admin.id
  assert outbox.last_replay_reason == "生产通知通道恢复后人工重放"

  with pytest.raises(ConflictError, match="FAILED"):
    await service.replay_outbox(
      outbox_event_id=outbox.id,
      actor_user_id=admin.id,
      reason="重复操作",
    )

  updated = await service.update_incident(
    incident_id=incident.id,
    actor_user_id=admin.id,
    status="resolved",
    reason="已核对并修复协调器配置",
  )
  assert updated["status"] == "resolved"
  assert incident.resolved_by_user_id == admin.id
  assert incident.resolution_note == "已核对并修复协调器配置"

  incident_service = WorkflowOperationalIncidentService(db_session)
  recurring = await incident_service.record(
    category="coordinator_failure",
    identity={"command_id": "recurring-command"},
  )
  await service.update_incident(
    incident_id=recurring.id,
    actor_user_id=admin.id,
    status="ignored",
    reason="第一次出现时已人工核对",
  )
  reopened = await incident_service.record(
    category="coordinator_failure",
    identity={"command_id": "recurring-command"},
  )
  assert reopened.status == "open"
  assert reopened.resolved_by_user_id is None
  assert reopened.resolution_note is None


@pytest.mark.asyncio
async def test_admin_suspend_resume_preserves_runtime_state_and_rejects_auto_nodes(
  db_session: AsyncSession,
) -> None:
  seeded = await _seed_runtime(db_session)
  admin = seeded["admin"]
  assert isinstance(admin, User)
  run = WorkflowGraphInstance(
    initiator_user_id=admin.id,
    status=WorkflowGraphInstanceStatus.ACTIVE,
    current_node_key="work",
    context={},
    diagnostics={},
    context_version=1,
    max_iterations=5,
  )
  db_session.add(run)
  await db_session.flush()
  node = WorkflowNodeInstance(
    instance_id=run.id,
    node_key="work",
    title="处理中",
    node_type=WorkflowGraphNodeType.TASK,
    engine_state=WorkflowNodeEngineState.ACKNOWLEDGED,
    business_state=WorkflowNodeBusinessState.DOING,
    iteration=1,
    node_instance_version=3,
  )
  auto_node = WorkflowNodeInstance(
    instance_id=run.id,
    node_key="notice",
    title="自动通知",
    node_type=WorkflowGraphNodeType.NOTICE,
    engine_state=WorkflowNodeEngineState.ACTIVATED,
    business_state=WorkflowNodeBusinessState.ASSIGNED,
    iteration=1,
    node_instance_version=1,
  )
  db_session.add_all([node, auto_node])
  await db_session.flush()
  graph = WorkflowGraphService(db_session)

  await graph.suspend_node_instance_by_admin(
    node_instance_id=node.id,
    actor_id=admin.id,
    reason="等待外部依赖恢复",
    commit=False,
  )
  assert node.engine_state == WorkflowNodeEngineState.SUSPENDED
  assert node.business_state == WorkflowNodeBusinessState.DOING
  assert node.config["operational_suspension"]["previous_engine_state"] == "acknowledged"

  with pytest.raises(ConflictError, match="只能重试 FAILED"):
    await graph.retry_node_instance(
      node_instance_id=node.id,
      actor_id=admin.id,
      reason="不应用重试绕过人工挂起",
      allow_suspended=False,
      commit=False,
    )

  await graph.resume_node_instance_by_admin(
    node_instance_id=node.id,
    actor_id=admin.id,
    reason="外部依赖已恢复",
    commit=False,
  )
  assert node.engine_state == WorkflowNodeEngineState.ACKNOWLEDGED
  assert node.business_state == WorkflowNodeBusinessState.DOING
  assert node.config["operational_suspension"]["status"] == "resumed"

  with pytest.raises(ConflictError, match="不可中断"):
    await graph.suspend_node_instance_by_admin(
      node_instance_id=auto_node.id,
      actor_id=admin.id,
      reason="不应允许",
      commit=False,
    )


@pytest.mark.asyncio
async def test_run_event_trace_carries_request_command_run_node_and_task_ids(
  db_session: AsyncSession,
) -> None:
  seeded = await _seed_runtime(db_session)
  admin = seeded["admin"]
  run = seeded["failed_run"]
  node = seeded["retry_node"]
  assert isinstance(admin, User)
  assert isinstance(run, WorkflowGraphInstance)
  assert isinstance(node, WorkflowNodeInstance)
  task_id = admin.id
  token = bind_request_context(
    request_id="request-iteration-5d",
    http_method="POST",
    path="/api/v1/workflow-graph/admin/operations/test",
  )
  try:
    with bind_workflow_event_context(command_id="command-iteration-5d") as envelope:
      event = await WorkflowRunEventService(db_session).append(
        instance_id=run.id,
        event_type="operations_test",
        actor_user_id=admin.id,
        node_instance_id=node.id,
        task_id=task_id,
        payload={"secret": "must-not-be-returned"},
      )
  finally:
    reset_request_context(token)

  assert event.request_id == "request-iteration-5d"
  assert event.command_id == "command-iteration-5d"
  assert event.correlation_id == envelope.correlation_id
  assert event.node_instance_id == node.id
  assert event.task_id == task_id

  items = await WorkflowOperationsService(db_session).search_traces(
    request_id="request-iteration-5d",
    limit=10,
  )
  assert items[0]["instance_id"] == str(run.id)
  assert items[0]["node_instance_id"] == str(node.id)
  assert items[0]["task_id"] == str(task_id)
  assert items[0]["payload_keys"] == ["secret"]
  assert "payload" not in items[0]
  persisted = await db_session.scalar(select(WorkflowRunEvent).where(WorkflowRunEvent.id == event.id))
  assert persisted is not None
