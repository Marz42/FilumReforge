from __future__ import annotations

import argparse
import asyncio

from app.core.database import dispose_async_engine, get_session_factory
from app.services.legacy_task_graph_migration_service import LegacyTaskGraphMigrationService


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="回滚指定批次的 legacy task -> graph 迁移。")
  parser.add_argument("--batch-id", required=True, help="需要回滚的迁移批次标识。")
  parser.add_argument("--dry-run", action="store_true", help="只输出匹配结果，不写数据库。")
  return parser.parse_args()


async def run_rollback(*, batch_id: str, dry_run: bool) -> None:
  async with get_session_factory()() as session:
    service = LegacyTaskGraphMigrationService(session)
    result = await service.rollback_batch(batch_id=batch_id, dry_run=dry_run)
    if dry_run:
      await session.rollback()
    else:
      await session.commit()

  print(f"batch_id={result.batch_id}")
  print(f"dry_run={result.dry_run}")
  print(f"matched_instances={result.matched_instance_count}")
  print(f"deleted_instances={result.deleted_instance_count}")
  print(f"deleted_nodes={result.deleted_node_count}")
  print(f"deleted_deliverables={result.deleted_deliverable_count}")
  print(f"restored_tasks={result.restored_task_count}")


async def main() -> None:
  args = parse_args()
  try:
    await run_rollback(batch_id=args.batch_id, dry_run=args.dry_run)
  finally:
    await dispose_async_engine()


if __name__ == "__main__":
  asyncio.run(main())