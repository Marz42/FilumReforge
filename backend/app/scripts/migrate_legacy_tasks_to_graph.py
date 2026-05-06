from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from app.core.database import dispose_async_engine, get_session_factory
from app.services.legacy_task_graph_migration_service import LegacyTaskGraphMigrationService


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="将旧 Task 迁移为 graph runtime 投影。")
  parser.add_argument("--batch-id", help="迁移批次标识；默认使用 UTC 时间戳。")
  parser.add_argument("--limit", type=int, default=None, help="最多处理多少条任务。")
  parser.add_argument("--dry-run", action="store_true", help="只输出计划，不写数据库。")
  return parser.parse_args()


async def run_migration(*, batch_id: str, limit: int | None, dry_run: bool) -> None:
  async with get_session_factory()() as session:
    service = LegacyTaskGraphMigrationService(session)
    result = await service.migrate_tasks(
      batch_id=batch_id,
      limit=limit,
      dry_run=dry_run,
    )
    if dry_run:
      await session.rollback()
    else:
      await session.commit()

  print(f"batch_id={result.batch_id}")
  print(f"dry_run={result.dry_run}")
  print(f"scanned={result.scanned_count}")
  print(f"eligible={result.eligible_count}")
  print(f"migrated={result.migrated_count}")
  print(f"skipped={result.skipped_count}")
  print(f"deliverables={result.deliverable_count}")
  if result.migrated_task_ids:
    print("task_ids=")
    for task_id in result.migrated_task_ids:
      print(f"- {task_id}")


async def main() -> None:
  args = parse_args()
  batch_id = args.batch_id or datetime.now(UTC).strftime("legacy-task-graph-%Y%m%d%H%M%S")
  try:
    await run_migration(batch_id=batch_id, limit=args.limit, dry_run=args.dry_run)
  finally:
    await dispose_async_engine()


if __name__ == "__main__":
  asyncio.run(main())