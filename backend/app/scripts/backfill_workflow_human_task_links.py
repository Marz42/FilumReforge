"""Dry-run or apply the guarded HumanTask Link backfill."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict

from app.core.database import dispose_async_engine, get_session_factory
from app.services.human_task_coordinator import HumanTaskCoordinator


def _parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description="Cross-check legacy Task/Node/Run anchors and backfill safe HumanTask Links.",
  )
  parser.add_argument(
    "--apply",
    action="store_true",
    help="Write only unambiguous links. Without this flag the command is read-only.",
  )
  return parser.parse_args()


async def run(*, apply: bool) -> dict[str, object]:
  async with get_session_factory()() as session:
    report = await HumanTaskCoordinator(session).backfill_existing_links(dry_run=not apply)
    if apply and not report.issues:
      await session.commit()
    else:
      await session.rollback()
    payload = asdict(report)
    payload["mode"] = "apply_blocked" if apply and report.issues else ("apply" if apply else "dry-run")
    payload["has_anomalies"] = bool(report.issues)
    return payload


async def main() -> None:
  args = _parse_args()
  try:
    print(json.dumps(await run(apply=bool(args.apply)), ensure_ascii=False, indent=2, default=str))
  finally:
    await dispose_async_engine()


if __name__ == "__main__":
  asyncio.run(main())
