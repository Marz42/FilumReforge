from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WorkflowOperationalIncident


def operational_incident_fingerprint(
  category: str,
  *,
  identity: dict[str, Any],
) -> str:
  canonical = json.dumps(
    {"category": category, "identity": identity},
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
    default=str,
  )
  return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class WorkflowOperationalIncidentService:
  """Persist rare workflow readiness exceptions without duplicating rows."""

  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def record(
    self,
    *,
    category: str,
    identity: dict[str, Any],
    severity: str = "warning",
    instance_id: UUID | None = None,
    node_instance_id: UUID | None = None,
    task_id: UUID | None = None,
    command_receipt_id: UUID | None = None,
    outbox_event_id: UUID | None = None,
    engine_version: str | None = None,
    details: dict[str, Any] | None = None,
  ) -> WorkflowOperationalIncident:
    fingerprint = operational_incident_fingerprint(category, identity=identity)
    now = datetime.now(UTC)
    existing = await self._session.scalar(
      select(WorkflowOperationalIncident).where(
        WorkflowOperationalIncident.category == category,
        WorkflowOperationalIncident.fingerprint == fingerprint,
      )
    )
    if existing is not None:
      existing.status = "open"
      existing.resolved_at = None
      existing.last_seen_at = now
      existing.occurrence_count += 1
      existing.severity = severity
      existing.details = {**dict(existing.details or {}), **dict(details or {})}
      await self._session.flush()
      return existing

    incident = WorkflowOperationalIncident(
      category=category,
      status="open",
      severity=severity,
      fingerprint=fingerprint,
      occurrence_count=1,
      first_seen_at=now,
      last_seen_at=now,
      instance_id=instance_id,
      node_instance_id=node_instance_id,
      task_id=task_id,
      command_receipt_id=command_receipt_id,
      outbox_event_id=outbox_event_id,
      engine_version=engine_version,
      details=dict(details or {}),
    )
    try:
      async with self._session.begin_nested():
        self._session.add(incident)
        await self._session.flush()
    except IntegrityError:
      existing = await self._session.scalar(
        select(WorkflowOperationalIncident).where(
          WorkflowOperationalIncident.category == category,
          WorkflowOperationalIncident.fingerprint == fingerprint,
        )
      )
      if existing is None:
        raise
      existing.status = "open"
      existing.resolved_at = None
      existing.last_seen_at = now
      existing.occurrence_count += 1
      existing.details = {**dict(existing.details or {}), **dict(details or {})}
      await self._session.flush()
      return existing
    return incident

  async def resolve(self, incident: WorkflowOperationalIncident) -> None:
    incident.status = "resolved"
    incident.resolved_at = datetime.now(UTC)
    await self._session.flush()
