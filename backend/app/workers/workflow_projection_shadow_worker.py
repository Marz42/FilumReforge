"""Independent periodic runner for privacy-safe projection shadow observations."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.workflow_projection_shadow_service import WorkflowProjectionShadowService


logger = logging.getLogger(__name__)


async def scan_workflow_projection_shadow(
  *,
  session_factory: async_sessionmaker[AsyncSession],
  task_limit: int = 100,
  run_limit: int = 100,
  timeline_limit: int = 200,
  lag_grace_seconds: int = 60,
) -> int:
  """Record one recent shadow sample without touching business or projection writes."""
  try:
    async with session_factory() as session:
      service = WorkflowProjectionShadowService(session)
      await service.prune(retention_days=30)
      result = await service.scan(
        sample_mode="recent",
        task_limit=task_limit,
        run_limit=run_limit,
        timeline_limit=timeline_limit,
        lag_grace_seconds=lag_grace_seconds,
      )
      await session.commit()
      return result.compared_count
  except Exception:  # noqa: BLE001 - observation failure must remain isolated.
    logger.exception("Workflow projection shadow scan failed")
    return 0
