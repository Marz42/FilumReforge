from __future__ import annotations

from dataclasses import dataclass

from app.models import Report, User, WorkflowDefinition
from app.schemas.report_center import ReportTargetOptionRead
from app.services.report_service import ReportService
from app.services.workflow_engine_service import WorkflowEngineService


@dataclass
class ReportCenterSnapshot:
  pending_reports: list[Report]
  initiated_reports: list[Report]
  history_reports: list[Report]
  upward_target_options: list[ReportTargetOptionRead]
  downward_target_options: list[ReportTargetOptionRead]
  workflow_definition_options: list[WorkflowDefinition]
  permissions: dict[str, bool]


class ReportCenterService:
  def __init__(
    self,
    report_service: ReportService,
    workflow_engine_service: WorkflowEngineService,
  ) -> None:
    self._report_service = report_service
    self._workflow_engine_service = workflow_engine_service

  async def get_snapshot(self, *, actor: User) -> ReportCenterSnapshot:
    upward_target_options = await self._report_service.list_upward_target_options(actor=actor)
    downward_target_options = await self._report_service.list_downward_target_options(actor=actor)
    workflow_definition_options = await self._workflow_engine_service.list_definitions(actor=actor)

    return ReportCenterSnapshot(
      pending_reports=await self._report_service.list_pending_reports(actor=actor),
      initiated_reports=await self._report_service.list_initiated_reports(actor=actor),
      history_reports=await self._report_service.list_history_reports(actor=actor),
      upward_target_options=upward_target_options,
      downward_target_options=downward_target_options,
      workflow_definition_options=workflow_definition_options,
      permissions={
        "can_create_upward": len(upward_target_options) > 0,
        "can_create_downward": len(downward_target_options) > 0,
      },
    )
