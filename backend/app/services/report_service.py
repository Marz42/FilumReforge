from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
  DEFAULT_USER_NOTIFICATION_CHANNELS,
  AttachmentStatus,
  AttachmentTargetType,
  DelegationScopeType,
  DelegationStatus,
  ReportDirection,
  ReportRouteStatus,
  ReportStatus,
  ReportingLineType,
)
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.core.request_context import merge_error_context, set_error_scope, set_error_stage
from app.models import (
  Attachment,
  AttachmentLink,
  Delegation,
  Report,
  ReportRoute,
  ReportingLine,
  User,
  WorkflowDefinition,
  WorkflowInstance,
)
from app.schemas.messages import NotificationMessage
from app.schemas.report_center import ReportActionOptionRead, ReportTargetOptionRead
from app.services.access_control import ensure_active_user
from app.services.notification_service import NotificationService
from app.services.notification_source import build_report_source_payload
from app.services.workflow_engine_service import WorkflowEngineService


def _user_label(user: User | None) -> str:
  if user is None:
    return "未知用户"
  if user.profile is not None and user.profile.real_name:
    return user.profile.real_name
  return user.email


def _excerpt(value: str, *, limit: int = 160) -> str:
  text = value.strip()
  if len(text) <= limit:
    return text
  return f"{text[: limit - 3]}..."


class ReportService:
  _MAX_REPORT_ATTACHMENTS = 10

  def __init__(
    self,
    session: AsyncSession,
    notification_service: NotificationService | None = None,
    workflow_engine_service: WorkflowEngineService | None = None,
  ) -> None:
    self._session = session
    self._notification_service = notification_service
    self._workflow_engine_service = workflow_engine_service

  def _report_statement(self):
    return (
      select(Report)
      .execution_options(populate_existing=True)
      .options(
        selectinload(Report.initiator).selectinload(User.profile),
        selectinload(Report.target).selectinload(User.profile),
        selectinload(Report.current_recipient).selectinload(User.profile),
        selectinload(Report.workflow_definition),
        selectinload(Report.workflow_instance)
        .selectinload(WorkflowInstance.definition)
        .selectinload(WorkflowDefinition.steps),
        selectinload(Report.routes)
        .selectinload(ReportRoute.sender)
        .selectinload(User.profile),
        selectinload(Report.routes)
        .selectinload(ReportRoute.recipient)
        .selectinload(User.profile),
        selectinload(Report.routes)
        .selectinload(ReportRoute.assigned_user)
        .selectinload(User.profile),
      )
    )

  async def _get_report_or_raise(self, *, actor: User, report_id: UUID) -> Report:
    ensure_active_user(actor)
    statement = self._report_statement().where(
      Report.id == report_id,
      self._report_involvement_clause(actor_id=actor.id),
    )
    report = await self._session.scalar(statement)
    if report is None:
      raise NotFoundError("汇报不存在。")
    return report

  @staticmethod
  def _report_involvement_clause(*, actor_id: UUID):
    return or_(
      Report.initiator_user_id == actor_id,
      Report.target_user_id == actor_id,
      Report.current_recipient_user_id == actor_id,
      Report.routes.any(ReportRoute.recipient_user_id == actor_id),
      Report.routes.any(ReportRoute.assigned_user_id == actor_id),
      Report.routes.any(ReportRoute.sender_user_id == actor_id),
    )

  async def _list_active_primary_reporting_lines(self) -> list[ReportingLine]:
    effective_date = date.today()
    statement = (
      select(ReportingLine)
      .options(
        selectinload(ReportingLine.user).selectinload(User.profile),
        selectinload(ReportingLine.manager).selectinload(User.profile),
      )
      .where(
        ReportingLine.line_type == ReportingLineType.SOLID,
        ReportingLine.is_primary.is_(True),
        ReportingLine.starts_at <= effective_date,
        or_(ReportingLine.ends_at.is_(None), ReportingLine.ends_at >= effective_date),
      )
      .order_by(ReportingLine.starts_at.desc(), ReportingLine.created_at.desc())
    )
    return list(await self._session.scalars(statement))

  async def _build_reporting_maps(self) -> tuple[dict[UUID, ReportingLine], dict[UUID, list[ReportingLine]]]:
    lines = await self._list_active_primary_reporting_lines()
    parent_by_user: dict[UUID, ReportingLine] = {}
    for line in lines:
      parent_by_user.setdefault(line.user_id, line)

    children_by_manager: dict[UUID, list[ReportingLine]] = defaultdict(list)
    for line in parent_by_user.values():
      children_by_manager[line.manager_user_id].append(line)

    for child_lines in children_by_manager.values():
      child_lines.sort(key=lambda item: _user_label(item.user))

    return parent_by_user, children_by_manager

  async def list_upward_target_options(self, *, actor: User) -> list[ReportTargetOptionRead]:
    ensure_active_user(actor)
    parent_by_user, _ = await self._build_reporting_maps()
    options: list[ReportTargetOptionRead] = []
    current_user_id = actor.id
    path_labels: list[str] = []
    while current_user_id in parent_by_user:
      line = parent_by_user[current_user_id]
      manager = line.manager
      if manager is None:
        break
      manager_label = _user_label(manager)
      path_labels.append(manager_label)
      options.append(
        ReportTargetOptionRead(
          user_id=manager.id,
          label=manager_label,
          path_labels=list(path_labels),
          hops=len(path_labels),
        )
      )
      current_user_id = manager.id
    return options

  async def list_downward_target_options(self, *, actor: User) -> list[ReportTargetOptionRead]:
    ensure_active_user(actor)
    _, children_by_manager = await self._build_reporting_maps()
    options: list[ReportTargetOptionRead] = []
    queue: deque[tuple[UUID, list[str]]] = deque([(actor.id, [])])
    while queue:
      manager_id, path_labels = queue.popleft()
      for line in children_by_manager.get(manager_id, []):
        user = line.user
        if user is None:
          continue
        next_path = [*path_labels, _user_label(user)]
        options.append(
          ReportTargetOptionRead(
            user_id=user.id,
            label=_user_label(user),
            path_labels=next_path,
            hops=len(next_path),
          )
        )
        queue.append((user.id, next_path))
    return options

  async def _resolve_upward_path(self, *, actor_id: UUID, target_user_id: UUID) -> list[UUID]:
    parent_by_user, _ = await self._build_reporting_maps()
    path: list[UUID] = []
    current_user_id = actor_id
    while current_user_id in parent_by_user:
      line = parent_by_user[current_user_id]
      path.append(line.manager_user_id)
      if line.manager_user_id == target_user_id:
        return path
      current_user_id = line.manager_user_id
    raise ConflictError("目标用户不在当前账号的逐级上报链路中。")

  async def _resolve_downward_path(self, *, actor_id: UUID, target_user_id: UUID) -> list[UUID]:
    _, children_by_manager = await self._build_reporting_maps()
    queue: deque[UUID] = deque([actor_id])
    parent: dict[UUID, UUID | None] = {actor_id: None}
    while queue:
      manager_id = queue.popleft()
      for line in children_by_manager.get(manager_id, []):
        child_user_id = line.user_id
        if child_user_id in parent:
          continue
        parent[child_user_id] = manager_id
        if child_user_id == target_user_id:
          path: list[UUID] = []
          current_id: UUID | None = target_user_id
          while current_id is not None and current_id != actor_id:
            path.append(current_id)
            current_id = parent.get(current_id)
          path.reverse()
          return path
        queue.append(child_user_id)
    raise ConflictError("目标用户不在当前账号的逐级传达链路中。")

  async def _resolve_route_path(
    self,
    *,
    actor: User,
    target_user_id: UUID,
    direction: ReportDirection,
  ) -> list[UUID]:
    if target_user_id == actor.id:
      raise ConflictError("目标用户不能是当前账号本人。")
    if direction == ReportDirection.UPWARD:
      return await self._resolve_upward_path(actor_id=actor.id, target_user_id=target_user_id)
    return await self._resolve_downward_path(actor_id=actor.id, target_user_id=target_user_id)

  async def _find_active_delegate(self, *, recipient_user_id: UUID) -> User | None:
    now = datetime.now(UTC)
    delegation = await self._session.scalar(
      select(Delegation)
      .options(selectinload(Delegation.delegate).selectinload(User.profile))
      .where(
        Delegation.delegator_user_id == recipient_user_id,
        Delegation.scope_type == DelegationScopeType.ALL,
        Delegation.status.in_([DelegationStatus.PENDING, DelegationStatus.ACTIVE]),
        Delegation.starts_at <= now,
        Delegation.ends_at > now,
      )
      .order_by(Delegation.starts_at.desc())
    )
    if delegation is None or delegation.delegate is None:
      return None
    ensure_active_user(delegation.delegate)
    return delegation.delegate

  async def _activate_route(self, *, report: Report, route: ReportRoute) -> None:
    assignee = await self._find_active_delegate(recipient_user_id=route.recipient_user_id)
    if assignee is None:
      assignee = await self._session.get(User, route.recipient_user_id)
    if assignee is None:
      raise NotFoundError("汇报目标用户不存在。")
    ensure_active_user(assignee)

    now = datetime.now(UTC)
    route.assigned_user_id = assignee.id
    route.assigned_user = assignee
    route.status = ReportRouteStatus.PENDING
    route.activated_at = now
    report.current_recipient_user_id = assignee.id
    report.current_recipient = assignee
    report.current_route_sequence = route.sequence_no

    if self._notification_service is None:
      return

    direction_label = "向上汇报" if report.direction == ReportDirection.UPWARD else "向下传达"
    await self._notification_service.send(
      NotificationMessage(
        source_type="report",
        source_id=report.id,
        recipient_user_id=assignee.id,
        recipient_email=assignee.email,
        message_type="report_pending",
        title=f"新的{direction_label}：{report.title}",
        body_text=f"请处理「{report.title}」。",
        payload=build_report_source_payload(
          report_id=report.id,
          report_title=report.title,
          route_tab="pending",
          extra_payload={
            "direction": report.direction.value,
            "report_id": str(report.id),
            "route_sequence": route.sequence_no,
          },
        ),
        channels=list(DEFAULT_USER_NOTIFICATION_CHANNELS),
      )
    )

  async def _notify_initiator(
    self,
    *,
    report: Report,
    message_type: str,
    title: str,
    body_text: str,
    payload: dict[str, object] | None = None,
  ) -> None:
    if self._notification_service is None:
      return
    initiator = report.initiator
    if initiator is None:
      initiator = await self._session.get(User, report.initiator_user_id)
    if initiator is None:
      return
    await self._notification_service.send(
      NotificationMessage(
        source_type="report",
        source_id=report.id,
        recipient_user_id=initiator.id,
        recipient_email=initiator.email,
        message_type=message_type,
        title=title,
        body_text=body_text,
        payload=build_report_source_payload(
          report_id=report.id,
          report_title=report.title,
          route_tab="initiated",
          extra_payload=dict(payload or {}),
        ),
        channels=list(DEFAULT_USER_NOTIFICATION_CHANNELS),
      )
    )

  async def list_pending_reports(self, *, actor: User) -> list[Report]:
    ensure_active_user(actor)
    statement = (
      self._report_statement()
      .where(
        Report.status == ReportStatus.IN_PROGRESS,
        Report.routes.any(
          and_(
            ReportRoute.assigned_user_id == actor.id,
            ReportRoute.status == ReportRouteStatus.PENDING,
          )
        ),
      )
      .order_by(Report.updated_at.desc())
    )
    return list(await self._session.scalars(statement))

  async def list_initiated_reports(self, *, actor: User) -> list[Report]:
    ensure_active_user(actor)
    statement = (
      self._report_statement()
      .where(
        Report.initiator_user_id == actor.id,
        Report.status == ReportStatus.IN_PROGRESS,
      )
      .order_by(Report.updated_at.desc())
    )
    return list(await self._session.scalars(statement))

  async def list_history_reports(self, *, actor: User) -> list[Report]:
    ensure_active_user(actor)
    statement = (
      self._report_statement()
      .where(
        self._report_involvement_clause(actor_id=actor.id),
        Report.status.in_([ReportStatus.COMPLETED, ReportStatus.RETURNED, ReportStatus.ARCHIVED]),
      )
      .order_by(Report.updated_at.desc())
    )
    return list(await self._session.scalars(statement))

  async def get_report(self, *, actor: User, report_id: UUID) -> Report:
    return await self._get_report_or_raise(actor=actor, report_id=report_id)

  async def _bind_attachments_to_report(
    self,
    *,
    actor: User,
    report_id: UUID,
    attachment_ids: list[UUID],
  ) -> None:
    if len(attachment_ids) > self._MAX_REPORT_ATTACHMENTS:
      raise ConflictError(f"汇报附件最多 {self._MAX_REPORT_ATTACHMENTS} 个。")
    unique: list[UUID] = []
    seen: set[UUID] = set()
    for raw in attachment_ids:
      if raw in seen:
        continue
      seen.add(raw)
      unique.append(raw)

    for att_id in unique:
      att = await self._session.get(
        Attachment,
        att_id,
        options=(selectinload(Attachment.links),),
      )
      if att is None:
        raise ConflictError("附件不存在。")
      if att.uploader_id != actor.id:
        raise ConflictError("只能绑定本人上传的附件。")
      if att.status != AttachmentStatus.UPLOADED:
        raise ConflictError("附件不可用。")
      if list(att.links):
        raise ConflictError("附件已绑定其他业务对象，请先使用新上传的附件。")
      self._session.add(
        AttachmentLink(
          attachment_id=att.id,
          target_type=AttachmentTargetType.REPORT,
          target_id=report_id,
          relation="primary",
          created_by=actor.id,
        )
      )
    await self._session.flush()

  async def create_report(
    self,
    *,
    actor: User,
    direction: ReportDirection,
    target_user_id: UUID,
    title: str,
    content_md: str,
    workflow_definition_id: UUID | None = None,
    attachment_ids: list[UUID] | None = None,
  ) -> Report:
    ensure_active_user(actor)
    normalized_title = title.strip()
    normalized_content = content_md.strip()
    set_error_scope("report_center.create_report")
    merge_error_context(
      {
        "source_type": "report",
        "actor_email": actor.email,
        "direction": direction.value,
        "target_user_id": str(target_user_id),
        "workflow_definition_id": str(workflow_definition_id) if workflow_definition_id is not None else None,
        "title": _excerpt(normalized_title, limit=120),
        "content_preview": _excerpt(normalized_content),
      }
    )
    set_error_stage("resolve_route_path")
    route_user_ids = await self._resolve_route_path(
      actor=actor,
      target_user_id=target_user_id,
      direction=direction,
    )
    if not route_user_ids:
      raise ConflictError("当前汇报链路为空。")

    merge_error_context({"route_user_ids": [str(user_id) for user_id in route_user_ids]})
    set_error_stage("persist_report")
    report = Report(
      direction=direction,
      status=ReportStatus.IN_PROGRESS,
      title=normalized_title,
      content_md=normalized_content,
      initiator_user_id=actor.id,
      target_user_id=target_user_id,
      workflow_definition_id=workflow_definition_id,
    )
    report.initiator = actor
    self._session.add(report)
    await self._session.flush()
    merge_error_context({"source_id": str(report.id)})

    if attachment_ids:
      await self._bind_attachments_to_report(actor=actor, report_id=report.id, attachment_ids=attachment_ids)

    previous_user_id = actor.id
    routes: list[ReportRoute] = []
    set_error_stage("persist_routes")
    for index, user_id in enumerate(route_user_ids, start=1):
      route = ReportRoute(
        report_id=report.id,
        sequence_no=index,
        sender_user_id=previous_user_id,
        recipient_user_id=user_id,
        status=ReportRouteStatus.QUEUED,
      )
      self._session.add(route)
      routes.append(route)
      previous_user_id = user_id

    await self._session.flush()
    if workflow_definition_id is not None:
      set_error_stage("start_workflow")
      if self._workflow_engine_service is None:
        raise ConflictError("审批流引擎未配置。")
      workflow_instance = await self._workflow_engine_service.start_workflow(
        actor=actor,
        definition_id=workflow_definition_id,
        source_type="report",
        source_id=report.id,
        payload={
          "direction": direction.value,
          "target_user_id": str(target_user_id),
        },
      )
      report.workflow_instance_id = workflow_instance.id

    first_route = routes[0]
    set_error_stage("activate_first_route")
    await self._activate_route(report=report, route=first_route)
    set_error_stage("commit_report")
    await self._session.commit()
    set_error_stage("load_report_response")
    return await self.get_report(actor=actor, report_id=report.id)

  async def act_report(
    self,
    *,
    actor: User,
    report_id: UUID,
    action: str,
    note: str | None = None,
  ) -> Report:
    report = await self._get_report_or_raise(actor=actor, report_id=report_id)
    normalized_action = action.strip().lower()
    if normalized_action not in {"advance", "return", "archive"}:
      raise ConflictError("不支持的汇报动作。")

    if normalized_action == "archive":
      if report.initiator_user_id != actor.id:
        raise AuthorizationError("只有发起人可以归档该汇报。")
      if report.status not in {ReportStatus.COMPLETED, ReportStatus.RETURNED}:
        raise ConflictError("当前汇报不能归档。")
      report.status = ReportStatus.ARCHIVED
      report.archived_at = datetime.now(UTC)
      await self._session.commit()
      return await self.get_report(actor=actor, report_id=report_id)

    if report.status != ReportStatus.IN_PROGRESS:
      raise ConflictError("当前汇报不在可处理状态。")

    pending_route = next((route for route in report.routes if route.status == ReportRouteStatus.PENDING), None)
    if pending_route is None:
      raise ConflictError("当前汇报没有待处理节点。")
    if pending_route.assigned_user_id != actor.id:
      raise AuthorizationError("当前账号不能处理该汇报。")

    now = datetime.now(UTC)
    pending_route.note = note.strip() if note else None
    pending_route.acted_at = now

    if normalized_action == "return":
      pending_route.status = ReportRouteStatus.RETURNED
      report.status = ReportStatus.RETURNED
      report.returned_at = now
      report.current_recipient_user_id = None
      report.current_route_sequence = None
      await self._notify_initiator(
        report=report,
        message_type="report_returned",
        title=f"汇报被退回：{report.title}",
        body_text=f"「{report.title}」已被退回。",
        payload={"note": pending_route.note or ""},
      )
      await self._session.commit()
      return await self.get_report(actor=actor, report_id=report_id)

    next_route = next(
      (
        route
        for route in report.routes
        if route.sequence_no == pending_route.sequence_no + 1 and route.status == ReportRouteStatus.QUEUED
      ),
      None,
    )
    if next_route is None:
      pending_route.status = ReportRouteStatus.COMPLETED
      report.status = ReportStatus.COMPLETED
      report.completed_at = now
      report.current_recipient_user_id = None
      report.current_route_sequence = None
      await self._notify_initiator(
        report=report,
        message_type="report_completed",
        title=f"汇报已完成：{report.title}",
        body_text=f"「{report.title}」已完成逐级流转。",
      )
      await self._session.commit()
      return await self.get_report(actor=actor, report_id=report_id)

    pending_route.status = ReportRouteStatus.FORWARDED
    await self._activate_route(report=report, route=next_route)
    await self._session.commit()
    return await self.get_report(actor=actor, report_id=report_id)

  def build_action_options(self, *, actor: User, report: Report) -> list[ReportActionOptionRead]:
    options: list[ReportActionOptionRead] = []
    if report.status == ReportStatus.IN_PROGRESS:
      pending_route = next((route for route in report.routes if route.status == ReportRouteStatus.PENDING), None)
      has_next_route = any(
        route.sequence_no == (pending_route.sequence_no + 1 if pending_route is not None else -1)
        and route.status == ReportRouteStatus.QUEUED
        for route in report.routes
      )
      if pending_route is not None and pending_route.assigned_user_id == actor.id:
        options.append(
          ReportActionOptionRead(
            action="advance",
            label=(
              "继续上报"
              if has_next_route and report.direction == ReportDirection.UPWARD
              else "继续传达"
              if has_next_route
              else "确认完成"
            ),
          )
        )
        options.append(
          ReportActionOptionRead(
            action="return",
            label="退回",
            button_type="warning",
          )
        )
    if report.status in {ReportStatus.COMPLETED, ReportStatus.RETURNED} and report.initiator_user_id == actor.id:
      options.append(
        ReportActionOptionRead(
          action="archive",
          label="归档",
          button_type="success",
        )
      )
    return options
