from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
  TaskStatus,
  WorkflowGraphInstanceStatus,
  WorkflowGraphNodeType,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.models import Task, WorkflowDeliverable, WorkflowGraphInstance, WorkflowNodeInstance


MIGRATION_BATCH_KEY = "legacy_graph_migration_batch_id"
MIGRATED_AT_KEY = "legacy_graph_migrated_at"
GRAPH_INSTANCE_ID_KEY = "workflow_graph_instance_id"
NODE_INSTANCE_ID_KEY = "workflow_node_instance_id"
NODE_ITERATION_KEY = "workflow_node_iteration"
HANDSHAKE_STATE_KEY = "workflow_handshake_state"
LATEST_HANDSHAKE_ACTION_KEY = "latest_handshake_action"
LATEST_HANDSHAKE_AT_KEY = "latest_handshake_at"


@dataclass(slots=True)
class LegacyTaskGraphMigrationResult:
  batch_id: str
  dry_run: bool
  scanned_count: int
  eligible_count: int
  migrated_count: int
  skipped_count: int
  deliverable_count: int
  migrated_task_ids: list[UUID]


@dataclass(slots=True)
class LegacyTaskGraphRollbackResult:
  batch_id: str
  dry_run: bool
  matched_instance_count: int
  deleted_instance_count: int
  deleted_node_count: int
  deleted_deliverable_count: int
  restored_task_count: int


class LegacyTaskGraphMigrationService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def migrate_tasks(
    self,
    *,
    batch_id: str,
    dry_run: bool = False,
    limit: int | None = None,
  ) -> LegacyTaskGraphMigrationResult:
    tasks = await self._load_candidate_tasks(limit=limit)
    scanned_count = len(tasks)
    if not tasks:
      return LegacyTaskGraphMigrationResult(
        batch_id=batch_id,
        dry_run=dry_run,
        scanned_count=0,
        eligible_count=0,
        migrated_count=0,
        skipped_count=0,
        deliverable_count=0,
        migrated_task_ids=[],
      )

    existing_source_ids = set(
      source_id
      for source_id in await self._session.scalars(
        select(WorkflowGraphInstance.source_id).where(
          WorkflowGraphInstance.source_id.in_([task.id for task in tasks])
        )
      )
      if source_id is not None
    )
    eligible_tasks = [
      task for task in tasks if task.id not in existing_source_ids and not self._task_has_graph_anchor(task)
    ]

    if dry_run:
      return LegacyTaskGraphMigrationResult(
        batch_id=batch_id,
        dry_run=True,
        scanned_count=scanned_count,
        eligible_count=len(eligible_tasks),
        migrated_count=0,
        skipped_count=scanned_count - len(eligible_tasks),
        deliverable_count=0,
        migrated_task_ids=[task.id for task in eligible_tasks],
      )

    migrated_task_ids: list[UUID] = []
    deliverable_count = 0
    for task in eligible_tasks:
      instance, node_instance = self._build_graph_projection(task=task, batch_id=batch_id)
      self._session.add(instance)
      self._session.add(node_instance)
      await self._session.flush()

      deliverable = self._build_deliverable_if_needed(
        task=task,
        node_instance=node_instance,
        batch_id=batch_id,
      )
      if deliverable is not None:
        self._session.add(deliverable)
        deliverable_count += 1

      self._mark_task_as_migrated(
        task=task,
        batch_id=batch_id,
        instance_id=instance.id,
        node_instance_id=node_instance.id,
      )
      migrated_task_ids.append(task.id)

    await self._session.flush()
    return LegacyTaskGraphMigrationResult(
      batch_id=batch_id,
      dry_run=False,
      scanned_count=scanned_count,
      eligible_count=len(eligible_tasks),
      migrated_count=len(migrated_task_ids),
      skipped_count=scanned_count - len(eligible_tasks),
      deliverable_count=deliverable_count,
      migrated_task_ids=migrated_task_ids,
    )

  async def rollback_batch(
    self,
    *,
    batch_id: str,
    dry_run: bool = False,
  ) -> LegacyTaskGraphRollbackResult:
    instances = list(
      await self._session.scalars(
        select(WorkflowGraphInstance)
        .options(
          selectinload(WorkflowGraphInstance.node_instances).selectinload(WorkflowNodeInstance.deliverables)
        )
        .order_by(WorkflowGraphInstance.created_at.asc())
      )
    )
    matched_instances = [
      instance
      for instance in instances
      if any((node.config or {}).get("migration_batch_id") == batch_id for node in instance.node_instances)
    ]
    deleted_node_count = sum(len(instance.node_instances) for instance in matched_instances)
    deleted_deliverable_count = sum(
      len(node.deliverables)
      for instance in matched_instances
      for node in instance.node_instances
    )

    restored_task_count = 0
    if not dry_run:
      for instance in matched_instances:
        if instance.source_id is not None:
          task = await self._session.get(Task, instance.source_id)
          if task is not None and (task.extra_metadata or {}).get(MIGRATION_BATCH_KEY) == batch_id:
            metadata = dict(task.extra_metadata or {})
            for key in [
              GRAPH_INSTANCE_ID_KEY,
              NODE_INSTANCE_ID_KEY,
              NODE_ITERATION_KEY,
              MIGRATION_BATCH_KEY,
              MIGRATED_AT_KEY,
            ]:
              metadata.pop(key, None)
            task.extra_metadata = metadata
            restored_task_count += 1
        await self._session.delete(instance)
      await self._session.flush()

    return LegacyTaskGraphRollbackResult(
      batch_id=batch_id,
      dry_run=dry_run,
      matched_instance_count=len(matched_instances),
      deleted_instance_count=0 if dry_run else len(matched_instances),
      deleted_node_count=0 if dry_run else deleted_node_count,
      deleted_deliverable_count=0 if dry_run else deleted_deliverable_count,
      restored_task_count=0 if dry_run else restored_task_count,
    )

  async def _load_candidate_tasks(self, *, limit: int | None) -> list[Task]:
    statement = (
      select(Task)
      .options(
        selectinload(Task.template_instance),
        selectinload(Task.template_step_run),
      )
      .order_by(Task.created_at.asc(), Task.id.asc())
    )
    if limit is not None:
      statement = statement.limit(limit)
    return list(await self._session.scalars(statement))

  @staticmethod
  def _task_has_graph_anchor(task: Task) -> bool:
    metadata = dict(task.extra_metadata or {})
    return bool(metadata.get(GRAPH_INSTANCE_ID_KEY) or metadata.get(NODE_INSTANCE_ID_KEY))

  @staticmethod
  def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
      return value
    if isinstance(value, str) and value:
      try:
        return datetime.fromisoformat(value)
      except ValueError:
        return None
    return None

  @staticmethod
  def _parse_uuid(value: object) -> UUID | None:
    if isinstance(value, UUID):
      return value
    if isinstance(value, str) and value:
      try:
        return UUID(value)
      except ValueError:
        return None
    return None

  def _resolve_node_state(
    self,
    *,
    task: Task,
  ) -> tuple[WorkflowNodeEngineState, WorkflowNodeBusinessState, datetime | None, datetime | None]:
    metadata = dict(task.extra_metadata or {})
    latest_review_state = str(metadata.get("latest_review_state") or "").strip()
    handshake_state = str(metadata.get(HANDSHAKE_STATE_KEY) or "").strip()
    latest_handshake_action = str(metadata.get(LATEST_HANDSHAKE_ACTION_KEY) or "").strip()
    acknowledged_at = self._parse_datetime(metadata.get(LATEST_HANDSHAKE_AT_KEY)) or task.started_at or task.updated_at

    if task.status == TaskStatus.DONE:
      return (
        WorkflowNodeEngineState.COMPLETED,
        WorkflowNodeBusinessState.DONE,
        acknowledged_at,
        task.completed_at or task.updated_at,
      )

    if task.status == TaskStatus.REVIEW:
      submitted_at = self._parse_datetime(metadata.get("latest_deliverable_submitted_at"))
      return (
        WorkflowNodeEngineState.ACKNOWLEDGED,
        WorkflowNodeBusinessState.PENDING_REVIEW,
        submitted_at or acknowledged_at,
        None,
      )

    if task.status == TaskStatus.DOING:
      business_state = (
        WorkflowNodeBusinessState.RETURNED_FOR_REWORK
        if latest_review_state == "returned_for_rework"
        else WorkflowNodeBusinessState.DOING
      )
      return (WorkflowNodeEngineState.ACKNOWLEDGED, business_state, acknowledged_at, None)

    if handshake_state == "assigned" or latest_handshake_action in {"delegated", "reassigned", "takeover"}:
      return (WorkflowNodeEngineState.ACTIVATED, WorkflowNodeBusinessState.ASSIGNED, None, None)
    if handshake_state == "rejected":
      return (WorkflowNodeEngineState.ACKNOWLEDGED, WorkflowNodeBusinessState.REJECTED, acknowledged_at, None)

    return (WorkflowNodeEngineState.ACKNOWLEDGED, WorkflowNodeBusinessState.ACCEPTED, acknowledged_at, None)

  def _build_graph_projection(
    self,
    *,
    task: Task,
    batch_id: str,
  ) -> tuple[WorkflowGraphInstance, WorkflowNodeInstance]:
    now = datetime.now(UTC)
    engine_state, business_state, acknowledged_at, completed_at = self._resolve_node_state(task=task)
    instance_completed = task.status == TaskStatus.DONE
    instance = WorkflowGraphInstance(
      initiator_user_id=task.creator_id,
      department_id=task.department_id,
      source_type=task.source_type.value,
      source_id=task.id,
      status=WorkflowGraphInstanceStatus.COMPLETED if instance_completed else WorkflowGraphInstanceStatus.ACTIVE,
      current_node_key=None if instance_completed else "task-node",
      context={
        "title": task.title,
        "description": task.description,
        "priority": task.priority.value,
        "due_date": task.due_date.isoformat() if task.due_date is not None else None,
        "legacy": {
          "task_id": str(task.id),
          "task_source_type": task.source_type.value,
          "template_instance_id": str(task.template_instance_id) if task.template_instance_id is not None else None,
          "template_step_run_id": str(task.template_step_run_id) if task.template_step_run_id is not None else None,
          "migration_batch_id": batch_id,
          "migrated_at": now.isoformat(),
        },
      },
      context_version=1,
      max_iterations=5,
      completed_at=completed_at if instance_completed else None,
    )
    node_instance = WorkflowNodeInstance(
      instance=instance,
      node_key="task-node",
      title=task.title,
      node_type=WorkflowGraphNodeType.TASK,
      engine_state=engine_state,
      business_state=business_state,
      assignee_user_id=task.assignee_id,
      iteration=1,
      node_instance_version=1,
      config={
        "task_id": str(task.id),
        "description": task.description,
        "priority": task.priority.value,
        "due_date": task.due_date.isoformat() if task.due_date is not None else None,
        "template_instance_id": str(task.template_instance_id) if task.template_instance_id is not None else None,
        "template_step_run_id": str(task.template_step_run_id) if task.template_step_run_id is not None else None,
        "migration_batch_id": batch_id,
        "legacy_task_source_type": task.source_type.value,
        "legacy_metadata_keys": sorted((task.extra_metadata or {}).keys()),
      },
      activated_at=task.created_at,
      acknowledged_at=acknowledged_at,
      completed_at=completed_at,
    )
    return instance, node_instance

  def _build_deliverable_if_needed(
    self,
    *,
    task: Task,
    node_instance: WorkflowNodeInstance,
    batch_id: str,
  ) -> WorkflowDeliverable | None:
    metadata = dict(task.extra_metadata or {})
    summary = metadata.get("latest_deliverable_summary")
    attachment_ids = metadata.get("latest_deliverable_attachment_ids") or []
    submitted_at = self._parse_datetime(metadata.get("latest_deliverable_submitted_at"))
    review_state = metadata.get("latest_review_state")
    if not summary and not attachment_ids and submitted_at is None and review_state is None:
      return None

    submitted_by_user_id = self._parse_uuid(metadata.get("latest_deliverable_submitted_by_user_id")) or task.assignee_id
    payload: dict[str, Any] = {
      "migration_batch_id": batch_id,
      "legacy_task_id": str(task.id),
      "submission_history": [],
    }
    if summary or attachment_ids or submitted_at is not None:
      latest_submission = {
        "summary": summary,
        "attachment_ids": list(attachment_ids),
        "submitted_at": submitted_at.isoformat() if submitted_at is not None else None,
        "submitted_by_user_id": str(submitted_by_user_id) if submitted_by_user_id is not None else None,
      }
      payload["latest_submission"] = latest_submission
      payload["submission_history"] = [latest_submission]

    review_entry: dict[str, Any] = {}
    if review_state == "approved":
      review_entry["action"] = "approve_completion"
    elif review_state == "returned_for_rework":
      review_entry["action"] = "return_for_rework"
    elif review_state == "pending_review":
      review_entry["action"] = "pending_review"
    if review_entry:
      review_entry["comment"] = metadata.get("latest_review_comment")
      review_entry["reviewed_at"] = metadata.get("latest_reviewed_at")
      review_entry["reviewer_user_id"] = metadata.get("latest_reviewer_user_id")
      if metadata.get("latest_review_quality_score") is not None:
        review_entry["quality_score"] = metadata.get("latest_review_quality_score")
      if metadata.get("rework_count") is not None:
        review_entry["rework_count"] = metadata.get("rework_count")
      payload["latest_review"] = review_entry
    if metadata.get("rework_count") is not None:
      payload["rework_count"] = metadata.get("rework_count")

    return WorkflowDeliverable(
      node_instance=node_instance,
      submitted_by_user_id=submitted_by_user_id,
      submitted_at=submitted_at,
      summary=str(summary) if summary is not None else None,
      payload=payload,
      signature=f"migration:{batch_id}:task:{task.id}",
    )

  def _mark_task_as_migrated(
    self,
    *,
    task: Task,
    batch_id: str,
    instance_id: UUID,
    node_instance_id: UUID,
  ) -> None:
    metadata = dict(task.extra_metadata or {})
    metadata.update(
      {
        GRAPH_INSTANCE_ID_KEY: str(instance_id),
        NODE_INSTANCE_ID_KEY: str(node_instance_id),
        NODE_ITERATION_KEY: 1,
        MIGRATION_BATCH_KEY: batch_id,
        MIGRATED_AT_KEY: datetime.now(UTC).isoformat(),
      }
    )
    if task.status == TaskStatus.TODO and not metadata.get(HANDSHAKE_STATE_KEY):
      metadata[HANDSHAKE_STATE_KEY] = "accepted"
      metadata[LATEST_HANDSHAKE_ACTION_KEY] = metadata.get(LATEST_HANDSHAKE_ACTION_KEY) or "accepted"
      metadata[LATEST_HANDSHAKE_AT_KEY] = metadata.get(LATEST_HANDSHAKE_AT_KEY) or task.updated_at.isoformat()
    task.extra_metadata = metadata