from __future__ import annotations

import logging
from collections import Counter, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from uuid import UUID

from app.core.request_context import get_request_context


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StrictProjectionGapDimension:
  surface: str
  reason: str
  projection_schema_version: int | None
  count: int


@dataclass(frozen=True, slots=True)
class StrictProjectionGapSample:
  surface: str
  reason: str
  projection_schema_version: int | None
  task_id: UUID
  request_id: str | None
  occurred_at: datetime


@dataclass(frozen=True, slots=True)
class StrictProjectionTelemetrySnapshot:
  total_count: int
  dimensions: tuple[StrictProjectionGapDimension, ...]
  recent: tuple[StrictProjectionGapSample, ...]


class StrictProjectionTelemetry:
  """Process-local counters plus structured logs for strict read gaps.

  The bounded samples feed the admin-only Operations dashboard. Structured logs
  are the cross-process alerting source and intentionally carry only identifiers
  that already passed the Task Center surface's visibility query.
  """

  def __init__(self, *, recent_limit: int = 100) -> None:
    self._counts: Counter[tuple[str, str, int | None]] = Counter()
    self._recent: deque[StrictProjectionGapSample] = deque(maxlen=recent_limit)
    self._lock = Lock()

  def record(
    self,
    *,
    surface: str,
    reason: str,
    projection_schema_version: int | None,
    task_id: UUID,
  ) -> None:
    context = get_request_context()
    raw_request_id = str(context.get("request_id") or "").strip()
    request_id = raw_request_id[:64] or None
    sample = StrictProjectionGapSample(
      surface=surface,
      reason=reason,
      projection_schema_version=projection_schema_version,
      task_id=task_id,
      request_id=request_id,
      occurred_at=datetime.now(UTC),
    )
    with self._lock:
      self._counts[(surface, reason, projection_schema_version)] += 1
      self._recent.appendleft(sample)

    logger.error(
      "strict_projection_gap surface=%s reason=%s projection_schema_version=%s "
      "task_id=%s request_id=%s",
      surface,
      reason,
      projection_schema_version,
      task_id,
      request_id,
    )

  def snapshot(self) -> StrictProjectionTelemetrySnapshot:
    with self._lock:
      dimensions = tuple(
        StrictProjectionGapDimension(
          surface=surface,
          reason=reason,
          projection_schema_version=schema_version,
          count=count,
        )
        for (surface, reason, schema_version), count in sorted(
          self._counts.items(),
          key=lambda item: (
            item[0][0],
            item[0][1],
            item[0][2] if item[0][2] is not None else -1,
          ),
        )
      )
      return StrictProjectionTelemetrySnapshot(
        total_count=sum(self._counts.values()),
        dimensions=dimensions,
        recent=tuple(self._recent),
      )

  def reset(self) -> None:
    """Reset process-local state; intended for isolated tests and worker restart hooks."""

    with self._lock:
      self._counts.clear()
      self._recent.clear()


strict_projection_telemetry = StrictProjectionTelemetry()
