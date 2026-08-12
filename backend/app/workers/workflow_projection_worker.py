"""Periodic, failure-isolated consumer for Iteration 5 workflow projections."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.workflow_projection_service import (
  PROJECTION_STREAMS,
  WorkflowProjectionService,
)


logger = logging.getLogger(__name__)


async def process_workflow_projection_events(
  *,
  session_factory: async_sessionmaker[AsyncSession],
  batch_size: int = 100,
) -> int:
  """Advance each durable source stream independently after business commits."""
  total_processed = 0
  for stream_name in PROJECTION_STREAMS:
    try:
      async with session_factory() as session:
        result = await WorkflowProjectionService(session).consume_stream(
          stream_name=stream_name,
          batch_size=batch_size,
        )
        await session.commit()
        total_processed += result.processed_count
    except Exception as exc:  # noqa: BLE001 - stream failure is persisted for retry.
      logger.exception("Workflow projection stream failed: %s", stream_name)
      try:
        async with session_factory() as failure_session:
          await WorkflowProjectionService(failure_session).record_stream_failure(
            stream_name=stream_name,
            error=exc,
          )
          await failure_session.commit()
      except Exception:  # noqa: BLE001 - preserve the original stream failure in logs.
        logger.exception("Could not persist projection failure state: %s", stream_name)
  return total_processed
