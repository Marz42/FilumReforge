"""Read-only inventory for active legacy workflow graph runs."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import dispose_async_engine, get_session_factory
from app.core.enums import WorkflowGraphInstanceStatus
from app.models import WorkflowGraphInstance, WorkflowGraphTemplate
from app.services.workflow_definition_snapshot import LEGACY_EXECUTOR_KIND


@dataclass(frozen=True, slots=True)
class LegacyTemplateRunCount:
  template_id: str | None
  template_code: str | None
  template_version: int | None
  active_run_count: int


@dataclass(frozen=True, slots=True)
class LegacyRunReport:
  active_legacy_run_count: int
  unprovable_definition_count: int
  missing_template_run_count: int
  by_template_version: list[LegacyTemplateRunCount]


async def build_legacy_run_report(session: AsyncSession) -> LegacyRunReport:
  rows = (
    await session.execute(
      select(
        WorkflowGraphInstance.template_id,
        WorkflowGraphTemplate.code,
        WorkflowGraphTemplate.version,
        func.count(WorkflowGraphInstance.id),
      )
      .outerjoin(
        WorkflowGraphTemplate,
        WorkflowGraphTemplate.id == WorkflowGraphInstance.template_id,
      )
      .where(
        WorkflowGraphInstance.status.in_(
          (WorkflowGraphInstanceStatus.PENDING, WorkflowGraphInstanceStatus.ACTIVE)
        ),
        WorkflowGraphInstance.executor_kind == LEGACY_EXECUTOR_KIND,
      )
      .group_by(
        WorkflowGraphInstance.template_id,
        WorkflowGraphTemplate.code,
        WorkflowGraphTemplate.version,
      )
      .order_by(WorkflowGraphTemplate.code.asc(), WorkflowGraphTemplate.version.asc())
    )
  ).all()
  grouped = [
    LegacyTemplateRunCount(
      template_id=str(template_id) if template_id is not None else None,
      template_code=template_code,
      template_version=template_version,
      active_run_count=int(run_count),
    )
    for template_id, template_code, template_version, run_count in rows
  ]
  active_count = sum(item.active_run_count for item in grouped)
  missing_count = sum(
    item.active_run_count for item in grouped if item.template_id is None or item.template_code is None
  )
  return LegacyRunReport(
    active_legacy_run_count=active_count,
    # Legacy runs have no creation-time canonical hash, so their exact definition
    # cannot be proven even when the current template row still exists.
    unprovable_definition_count=active_count,
    missing_template_run_count=missing_count,
    by_template_version=grouped,
  )


async def main() -> None:
  try:
    async with get_session_factory()() as session:
      report = await build_legacy_run_report(session)
      print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
  finally:
    await dispose_async_engine()


if __name__ == "__main__":
  asyncio.run(main())
