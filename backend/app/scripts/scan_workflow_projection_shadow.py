"""Explicit recent/full audit entry point for Iteration 5-C shadow comparison."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict

from app.core.database import dispose_async_engine, get_session_factory
from app.services.workflow_projection_shadow_service import WorkflowProjectionShadowService


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description="Compare source-derived workflow views with projections without cutting reads."
  )
  scope = parser.add_mutually_exclusive_group(required=True)
  scope.add_argument("--recent", action="store_const", const="recent", dest="sample_mode")
  scope.add_argument("--full", action="store_const", const="full", dest="sample_mode")
  parser.add_argument("--task-limit", type=int, default=100)
  parser.add_argument("--run-limit", type=int, default=100)
  parser.add_argument("--timeline-limit", type=int, default=200)
  parser.add_argument("--lag-grace-seconds", type=int, default=60)
  return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> dict[str, object]:
  async with get_session_factory()() as session:
    result = await WorkflowProjectionShadowService(session).scan(
      sample_mode=args.sample_mode,
      task_limit=args.task_limit,
      run_limit=args.run_limit,
      timeline_limit=args.timeline_limit,
      lag_grace_seconds=args.lag_grace_seconds,
    )
    await session.commit()
    return {**asdict(result), "scan_id": str(result.scan_id)}


async def main(args: argparse.Namespace) -> None:
  try:
    print(json.dumps(await _run(args), ensure_ascii=False, sort_keys=True))
  finally:
    await dispose_async_engine()


if __name__ == "__main__":
  asyncio.run(main(parse_args()))
