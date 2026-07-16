from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import WorkflowGraphInstanceStatus, WorkflowOutboxEventStatus
from app.models import (
  Task,
  WorkflowCommandReceipt,
  WorkflowGraphInstance,
  WorkflowHumanTaskLink,
  WorkflowOperationalIncident,
  WorkflowOutboxEvent,
)


def _enum_value(value: object) -> str:
  return str(getattr(value, "value", value))


class WorkflowIteration4ReadinessService:
  """Build a queryable runtime-data gate for Iteration 4 admission."""

  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def build_report(self) -> dict[str, Any]:
    incident_rows = list(
      (
        await self._session.execute(
          select(
            WorkflowOperationalIncident.category,
            WorkflowOperationalIncident.status,
            WorkflowOperationalIncident.severity,
            func.count(WorkflowOperationalIncident.id),
          ).group_by(
            WorkflowOperationalIncident.category,
            WorkflowOperationalIncident.status,
            WorkflowOperationalIncident.severity,
          )
        )
      ).all()
    )
    incident_counts = {
      f"{category}:{status}:{severity}": int(count)
      for category, status, severity, count in incident_rows
    }

    outbox_rows = list(
      (
        await self._session.execute(
          select(WorkflowOutboxEvent.status, func.count(WorkflowOutboxEvent.id)).group_by(
            WorkflowOutboxEvent.status
          )
        )
      ).all()
    )
    outbox_counts = {_enum_value(status): int(count) for status, count in outbox_rows}

    receipt_rows = list(
      (
        await self._session.execute(
          select(WorkflowCommandReceipt.status, func.count(WorkflowCommandReceipt.id)).group_by(
            WorkflowCommandReceipt.status
          )
        )
      ).all()
    )
    receipt_counts = {str(status): int(count) for status, count in receipt_rows}

    engine_rows = list(
      (
        await self._session.execute(
          select(
            WorkflowGraphInstance.engine_version,
            WorkflowGraphInstance.executor_kind,
            WorkflowGraphInstance.status,
            func.count(WorkflowGraphInstance.id),
          ).group_by(
            WorkflowGraphInstance.engine_version,
            WorkflowGraphInstance.executor_kind,
            WorkflowGraphInstance.status,
          )
        )
      ).all()
    )
    engine_version_counts = [
      {
        "engine_version": engine_version,
        "executor_kind": executor_kind,
        "status": _enum_value(status),
        "count": int(count),
      }
      for engine_version, executor_kind, status, count in engine_rows
    ]

    linked_task_ids = set(await self._session.scalars(select(WorkflowHumanTaskLink.task_id)))
    fallback_candidates: list[dict[str, str]] = []
    for task in list(await self._session.scalars(select(Task))):
      if task.id in linked_task_ids:
        continue
      metadata = task.extra_metadata if isinstance(task.extra_metadata, dict) else {}
      instance_id = metadata.get("workflow_graph_instance_id")
      node_instance_id = metadata.get("workflow_node_instance_id")
      if instance_id and node_instance_id:
        fallback_candidates.append(
          {
            "kind": "task_without_link",
            "task_id": str(task.id),
            "instance_id": str(instance_id),
            "node_instance_id": str(node_instance_id),
          }
        )

    active_incomplete_runs = list(
      await self._session.scalars(
        select(WorkflowGraphInstance).where(
          WorkflowGraphInstance.status == WorkflowGraphInstanceStatus.ACTIVE,
          (
            (WorkflowGraphInstance.engine_version == "")
            | (WorkflowGraphInstance.executor_kind == "snapshot")
            & (WorkflowGraphInstance.definition_snapshot.is_(None))
          ),
        )
      )
    )
    incomplete_objects = fallback_candidates[:100]
    incomplete_objects.extend(
      {
        "kind": "active_run_incomplete_executor_metadata",
        "instance_id": str(instance.id),
        "engine_version": instance.engine_version,
        "executor_kind": instance.executor_kind,
      }
      for instance in active_incomplete_runs[:100]
    )

    blockers: list[str] = []
    open_high_incident_count = sum(
      count
      for category, status, severity, count in incident_rows
      if status == "open" and severity in {"error", "critical"}
    )
    if open_high_incident_count:
      blockers.append(f"存在 {open_high_incident_count} 个 open error/critical incident。")
    if fallback_candidates:
      blockers.append(f"存在 {len(fallback_candidates)} 个 JSON fallback 潜在对象。")
    if active_incomplete_runs:
      blockers.append(f"存在 {len(active_incomplete_runs)} 个 executor 元数据不完整的 active Run。")
    failed_outbox = outbox_counts.get(WorkflowOutboxEventStatus.FAILED.value, 0)
    if failed_outbox:
      blockers.append(f"存在 {failed_outbox} 个 FAILED workflow outbox event。")
    processing_receipts = receipt_counts.get("processing", 0)
    if processing_receipts:
      blockers.append(f"存在 {processing_receipts} 个 processing command receipt。")

    return {
      "generated_at": datetime.now(UTC),
      "runtime_ready": not blockers,
      "incident_counts": incident_counts,
      "outbox_counts": outbox_counts,
      "receipt_counts": receipt_counts,
      "engine_version_counts": engine_version_counts,
      "incomplete_objects": incomplete_objects,
      "blockers": blockers,
    }
