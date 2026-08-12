"""Explicit operational entry point for Iteration 5 projection rebuilds."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from uuid import UUID

from app.core.database import dispose_async_engine, get_session_factory
from app.services.workflow_projection_rebuild_service import WorkflowProjectionRebuildService


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description="Rebuild workflow query projections without changing business source data."
  )
  scope = parser.add_mutually_exclusive_group(required=True)
  scope.add_argument("--task-id", help="Rebuild one Task and its Task timeline.")
  scope.add_argument("--run-id", help="Rebuild one process Run and linked Tasks.")
  scope.add_argument(
    "--all",
    action="store_true",
    dest="rebuild_all",
    help="Transactionally rebuild all projection rows and checkpoint high-watermarks.",
  )
  return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> dict[str, object]:
  async with get_session_factory()() as session:
    service = WorkflowProjectionRebuildService(session)
    if args.task_id:
      task_id = UUID(args.task_id)
      item = await service.rebuild_task(task_id)
      result: dict[str, object] = {
        "scope": "task",
        "task_id": str(task_id),
        "projected": item is not None,
      }
    elif args.run_id:
      run_id = UUID(args.run_id)
      summary = await service.rebuild_run(run_id)
      result = {
        "scope": "run",
        "run_id": str(run_id),
        "projected": summary is not None,
      }
    else:
      rebuild_result = await service.rebuild_all()
      result = {"scope": "all", **asdict(rebuild_result)}
    await session.commit()
    return result


async def main(args: argparse.Namespace) -> None:
  try:
    result = await _run(args)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
  finally:
    await dispose_async_engine()


if __name__ == "__main__":
  asyncio.run(main(parse_args()))
