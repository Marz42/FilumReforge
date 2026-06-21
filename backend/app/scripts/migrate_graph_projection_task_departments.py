"""One-off migration: align graph projection Task.department_id with assignee profile department."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import dispose_async_engine, get_session_factory
from app.models import Task, User


@dataclass(slots=True)
class MigrationResult:
  dry_run: bool
  scanned: int
  eligible: int
  updated: int
  skipped_no_assignee_dept: int
  task_ids: list[UUID]


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description="将图投影任务的 department_id 修正为受理人 Profile 所属部门。",
  )
  parser.add_argument("--dry-run", action="store_true", help="只统计，不写数据库。")
  parser.add_argument("--limit", type=int, default=None, help="最多处理多少条任务。")
  return parser.parse_args()


def _is_graph_projection_task(task: Task) -> bool:
  metadata = task.extra_metadata if isinstance(task.extra_metadata, dict) else {}
  return bool(metadata.get("workflow_graph_instance_id") and metadata.get("workflow_node_instance_id"))


async def run_migration(*, dry_run: bool, limit: int | None) -> MigrationResult:
  async with get_session_factory()() as session:
    statement = (
      select(Task)
      .options(selectinload(Task.assignee).selectinload(User.profile))
      .where(Task.assignee_id.is_not(None))
      .order_by(Task.updated_at.desc())
    )
    if limit is not None:
      statement = statement.limit(limit)

    tasks = list(await session.scalars(statement))
    updated_ids: list[UUID] = []
    eligible = 0
    skipped_no_assignee_dept = 0

    for task in tasks:
      if not _is_graph_projection_task(task):
        continue
      eligible += 1
      profile = task.assignee.profile if task.assignee is not None else None
      target_department_id = profile.department_id if profile is not None else None
      if target_department_id is None:
        skipped_no_assignee_dept += 1
        continue
      if task.department_id == target_department_id:
        continue
      if not dry_run:
        task.department_id = target_department_id
      updated_ids.append(task.id)

    if dry_run:
      await session.rollback()
    else:
      await session.commit()

  return MigrationResult(
    dry_run=dry_run,
    scanned=len(tasks),
    eligible=eligible,
    updated=len(updated_ids),
    skipped_no_assignee_dept=skipped_no_assignee_dept,
    task_ids=updated_ids,
  )


async def main() -> None:
  args = parse_args()
  try:
    result = await run_migration(dry_run=args.dry_run, limit=args.limit)
  finally:
    await dispose_async_engine()

  print(f"dry_run={result.dry_run}")
  print(f"scanned={result.scanned}")
  print(f"eligible={result.eligible}")
  print(f"updated={result.updated}")
  print(f"skipped_no_assignee_dept={result.skipped_no_assignee_dept}")
  if result.task_ids:
    print("task_ids=")
    for task_id in result.task_ids:
      print(f"- {task_id}")


if __name__ == "__main__":
  asyncio.run(main())
