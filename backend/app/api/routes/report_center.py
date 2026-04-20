from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
  get_current_user,
  get_report_center_service,
  get_report_service,
)
from app.models import Report, ReportRoute, User
from app.schemas.report_center import (
  ReportActionRequest,
  ReportCenterPermissionsRead,
  ReportCenterRead,
  ReportCreateRequest,
  ReportRead,
  ReportRouteRead,
  WorkflowDefinitionOptionRead,
)
from app.services.report_center_service import ReportCenterService
from app.services.report_service import ReportService

router = APIRouter(prefix="/report-center")


def _user_label(user: User | None) -> str:
  if user is None:
    return "未知用户"
  if user.profile is not None and user.profile.real_name:
    return user.profile.real_name
  return user.email


def _build_route_read(route: ReportRoute) -> ReportRouteRead:
  return ReportRouteRead(
    id=route.id,
    sequence_no=route.sequence_no,
    sender_user_id=route.sender_user_id,
    sender_label=_user_label(route.sender),
    recipient_user_id=route.recipient_user_id,
    recipient_label=_user_label(route.recipient),
    assigned_user_id=route.assigned_user_id,
    assigned_label=_user_label(route.assigned_user) if route.assigned_user is not None else None,
    status=route.status,
    activated_at=route.activated_at,
    acted_at=route.acted_at,
    note=route.note,
  )


def _build_report_read(*, actor: User, report_service: ReportService, report: Report) -> ReportRead:
  return ReportRead(
    id=report.id,
    direction=report.direction,
    status=report.status,
    title=report.title,
    content_md=report.content_md,
    initiator_user_id=report.initiator_user_id,
    initiator_label=_user_label(report.initiator),
    target_user_id=report.target_user_id,
    target_label=_user_label(report.target),
    current_recipient_user_id=report.current_recipient_user_id,
    current_recipient_label=(
      _user_label(report.current_recipient)
      if report.current_recipient_user_id is not None
      else None
    ),
    current_route_sequence=report.current_route_sequence,
    workflow_definition_id=report.workflow_definition_id,
    workflow_definition_name=report.workflow_definition.name if report.workflow_definition is not None else None,
    workflow_instance_id=report.workflow_instance_id,
    created_at=report.created_at,
    updated_at=report.updated_at,
    completed_at=report.completed_at,
    returned_at=report.returned_at,
    archived_at=report.archived_at,
    available_actions=report_service.build_action_options(actor=actor, report=report),
    routes=[_build_route_read(route) for route in report.routes],
  )


@router.get("", response_model=ReportCenterRead)
async def read_report_center(
  actor: Annotated[User, Depends(get_current_user)],
  report_center_service: Annotated[ReportCenterService, Depends(get_report_center_service)],
  report_service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportCenterRead:
  snapshot = await report_center_service.get_snapshot(actor=actor)
  return ReportCenterRead(
    permissions=ReportCenterPermissionsRead(
      can_create_upward=snapshot.permissions["can_create_upward"],
      can_create_downward=snapshot.permissions["can_create_downward"],
    ),
    upward_target_options=snapshot.upward_target_options,
    downward_target_options=snapshot.downward_target_options,
    workflow_definition_options=[
      WorkflowDefinitionOptionRead(id=definition.id, name=definition.name)
      for definition in snapshot.workflow_definition_options
    ],
    pending_reports=[
      _build_report_read(actor=actor, report_service=report_service, report=report)
      for report in snapshot.pending_reports
    ],
    initiated_reports=[
      _build_report_read(actor=actor, report_service=report_service, report=report)
      for report in snapshot.initiated_reports
    ],
    history_reports=[
      _build_report_read(actor=actor, report_service=report_service, report=report)
      for report in snapshot.history_reports
    ],
  )


@router.post("/reports", response_model=ReportRead, status_code=status.HTTP_201_CREATED)
async def create_report(
  payload: ReportCreateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  report_service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportRead:
  report = await report_service.create_report(
    actor=actor,
    direction=payload.direction,
    target_user_id=payload.target_user_id,
    title=payload.title,
    content_md=payload.content_md,
    workflow_definition_id=payload.workflow_definition_id,
  )
  return _build_report_read(actor=actor, report_service=report_service, report=report)


@router.get("/reports/{report_id}", response_model=ReportRead)
async def read_report(
  report_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  report_service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportRead:
  report = await report_service.get_report(actor=actor, report_id=report_id)
  return _build_report_read(actor=actor, report_service=report_service, report=report)


@router.post("/reports/{report_id}/actions", response_model=ReportRead)
async def act_report(
  report_id: UUID,
  payload: ReportActionRequest,
  actor: Annotated[User, Depends(get_current_user)],
  report_service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportRead:
  report = await report_service.act_report(
    actor=actor,
    report_id=report_id,
    action=payload.action,
    note=payload.note,
  )
  return _build_report_read(actor=actor, report_service=report_service, report=report)
