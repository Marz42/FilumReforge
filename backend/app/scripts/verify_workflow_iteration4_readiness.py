from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from app.core.database import get_session_factory
from app.services.workflow_iteration4_readiness_service import (
  WorkflowIteration4ReadinessService,
)


def _json_default(value: object) -> str:
  if isinstance(value, (datetime, date)):
    return value.isoformat()
  if isinstance(value, UUID):
    return str(value)
  if isinstance(value, Enum):
    return str(value.value)
  return str(value)


async def _run() -> dict[str, Any]:
  async with get_session_factory()() as session:
    return await WorkflowIteration4ReadinessService(session).build_report()


def main() -> int:
  parser = argparse.ArgumentParser(description="Verify workflow Iteration 4 runtime readiness.")
  parser.add_argument("--format", choices=("json",), default="json")
  parser.add_argument("--fail-on-open", action="store_true")
  args = parser.parse_args()
  report = asyncio.run(_run())
  print(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default))
  return 1 if args.fail_on_open and not report["runtime_ready"] else 0


if __name__ == "__main__":
  raise SystemExit(main())
