from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
  EmploymentEventTriggerStatus,
  EmploymentEventType,
  PositionAssignmentType,
  ReportingLineType,
  UserStatus,
  WorkflowDefinitionStatus,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.integrations.notifications.queue import JobQueuePublisher
from app.models import (
  EmploymentEvent,
  Profile,
  ProfilePosition,
  ReportingLine,
  TaskTemplate,
  User,
  WorkflowDefinition,
)
from app.services.access_control import ensure_management_role
from app.services.organization_relation_service import OrganizationRelationService
from app.services.task_template_service import TaskTemplateService
from app.services.workflow_engine_service import WorkflowEngineService

MAX_EVENT_TRIGGER_ATTEMPTS = 3
PROCESS_EMPLOYMENT_EVENT_JOB = "process_employment_event_job"


class HRLifecycleService:
  def __init__(
    self,
    session: AsyncSession,
    *,
    task_template_service: TaskTemplateService | None = None,
    workflow_engine_service: WorkflowEngineService | None = None,
    job_queue_publisher: JobQueuePublisher | None = None,
  ) -> None:
    self._session = session
    self._organization_relation_service = OrganizationRelationService(session)
    self._task_template_service = task_template_service
    self._workflow_engine_service = workflow_engine_service
    self._job_queue_publisher = job_queue_publisher

  async def list_events(self, *, user_id: UUID) -> list[EmploymentEvent]:
    statement = (
      select(EmploymentEvent)
      .where(EmploymentEvent.user_id == user_id)
      .order_by(EmploymentEvent.effective_date.desc(), EmploymentEvent.created_at.desc())
    )
    return list(await self._session.scalars(statement))

  async def create_event(
    self,
    *,
    actor: User,
    user_id: UUID,
    event_type: EmploymentEventType,
    effective_date: date,
    title: str,
    summary: str | None = None,
    payload: dict[str, Any] | None = None,
    task_template_id: UUID | None = None,
    workflow_definition_id: UUID | None = None,
  ) -> EmploymentEvent:
    ensure_management_role(actor)

    user = await self._session.get(User, user_id)
    if user is None:
      raise NotFoundError("用户不存在。")
    profile = await self._session.get(Profile, user_id)
    if profile is None:
      raise NotFoundError("档案不存在。")

    event_payload = payload or {}
    await self._validate_trigger_targets(
      task_template_id=task_template_id,
      workflow_definition_id=workflow_definition_id,
    )
    await self._apply_event_side_effects(
      profile=profile,
      user=user,
      actor=actor,
      event_type=event_type,
      effective_date=effective_date,
      payload=event_payload,
    )

    has_trigger_targets = self._event_has_trigger_targets(
      task_template_id=task_template_id,
      workflow_definition_id=workflow_definition_id,
    )
    event = EmploymentEvent(
      user_id=user_id,
      event_type=event_type,
      effective_date=effective_date,
      title=title,
      summary=summary,
      payload=event_payload,
      task_template_id=task_template_id,
      workflow_definition_id=workflow_definition_id,
      trigger_status=(
        EmploymentEventTriggerStatus.PENDING if has_trigger_targets else EmploymentEventTriggerStatus.SKIPPED
      ),
      triggered_at=None if has_trigger_targets else datetime.now(UTC),
      created_by=actor.id,
    )
    self._session.add(event)
    await self._session.commit()

    if has_trigger_targets:
      await self._enqueue_event_trigger(event=event)

    await self._session.refresh(event)
    return event

  async def process_event_automation(self, *, event_id: UUID) -> EmploymentEvent:
    event = await self._get_event_for_trigger(event_id=event_id)
    if not self._event_has_trigger_targets(
      task_template_id=event.task_template_id,
      workflow_definition_id=event.workflow_definition_id,
    ):
      if event.trigger_status != EmploymentEventTriggerStatus.SKIPPED:
        event.trigger_status = EmploymentEventTriggerStatus.SKIPPED
        event.triggered_at = datetime.now(UTC)
        event.trigger_error = None
        await self._session.commit()
      return event

    if self._event_trigger_completed(event=event):
      if event.trigger_status != EmploymentEventTriggerStatus.SUCCEEDED:
        event.trigger_status = EmploymentEventTriggerStatus.SUCCEEDED
        event.triggered_at = datetime.now(UTC)
        event.trigger_error = None
        await self._session.commit()
      return event

    event.trigger_status = EmploymentEventTriggerStatus.PROCESSING
    event.trigger_error = None
    event.trigger_attempt_count += 1
    await self._session.commit()

    try:
      await self._run_event_automation(event=event)
    except Exception as exc:  # noqa: BLE001
      event.trigger_status = EmploymentEventTriggerStatus.FAILED
      event.trigger_error = str(exc)
      event.triggered_at = datetime.now(UTC)
      await self._session.commit()
      if event.trigger_attempt_count < MAX_EVENT_TRIGGER_ATTEMPTS and self._job_queue_publisher is not None:
        await self._job_queue_publisher.enqueue(PROCESS_EMPLOYMENT_EVENT_JOB, str(event.id))
      await self._session.refresh(event)
      return event

    event.trigger_status = EmploymentEventTriggerStatus.SUCCEEDED
    event.trigger_error = None
    event.triggered_at = datetime.now(UTC)
    await self._session.commit()
    await self._session.refresh(event)
    return event

  @staticmethod
  def _event_has_trigger_targets(
    *,
    task_template_id: UUID | None,
    workflow_definition_id: UUID | None,
  ) -> bool:
    return task_template_id is not None or workflow_definition_id is not None

  @staticmethod
  def _event_trigger_completed(*, event: EmploymentEvent) -> bool:
    if event.task_template_id is not None and event.triggered_template_instance_id is None:
      return False
    if event.workflow_definition_id is not None and event.triggered_workflow_instance_id is None:
      return False
    return True

  async def _validate_trigger_targets(
    self,
    *,
    task_template_id: UUID | None,
    workflow_definition_id: UUID | None,
  ) -> None:
    if task_template_id is not None:
      template = await self._session.get(TaskTemplate, task_template_id)
      if template is None:
        raise NotFoundError("任务模板不存在。")
      if not template.is_active:
        raise ConflictError("生命周期联动要求模板处于启用状态。")

    if workflow_definition_id is not None:
      definition = await self._session.get(WorkflowDefinition, workflow_definition_id)
      if definition is None:
        raise NotFoundError("审批流定义不存在。")
      if definition.status != WorkflowDefinitionStatus.ACTIVE:
        raise ConflictError("生命周期联动要求审批流定义处于启用状态。")

  async def _enqueue_event_trigger(self, *, event: EmploymentEvent) -> None:
    if self._job_queue_publisher is None:
      event.trigger_status = EmploymentEventTriggerStatus.FAILED
      event.trigger_error = "未配置生命周期联动 job queue。"
      event.triggered_at = datetime.now(UTC)
      await self._session.commit()
      return

    try:
      await self._job_queue_publisher.enqueue(PROCESS_EMPLOYMENT_EVENT_JOB, str(event.id))
    except Exception as exc:  # noqa: BLE001
      event.trigger_status = EmploymentEventTriggerStatus.FAILED
      event.trigger_error = f"生命周期联动入队失败：{exc}"
      event.triggered_at = datetime.now(UTC)
      await self._session.commit()

  async def _get_event_for_trigger(self, *, event_id: UUID) -> EmploymentEvent:
    statement = (
      select(EmploymentEvent)
      .options(
        selectinload(EmploymentEvent.creator),
        selectinload(EmploymentEvent.user),
      )
      .where(EmploymentEvent.id == event_id)
    )
    event = await self._session.scalar(statement)
    if event is None:
      raise NotFoundError("生命周期事件不存在。")
    return event

  async def _run_event_automation(self, *, event: EmploymentEvent) -> None:
    if event.creator is None:
      raise NotFoundError("生命周期事件创建人不存在。")
    if event.user is None:
      raise NotFoundError("生命周期事件对应用户不存在。")

    if event.task_template_id is not None and event.triggered_template_instance_id is None:
      if self._task_template_service is None:
        raise ConflictError("生命周期联动未注入模板服务。")
      template_result = await self._task_template_service.instantiate_template(
        actor=event.creator,
        template_id=event.task_template_id,
        department_id=await self._resolve_event_department_id(event=event),
        payload=self._build_trigger_payload(event=event, channel="task_template"),
      )
      event.triggered_template_instance_id = template_result.instance.id
      await self._session.commit()

    if event.workflow_definition_id is not None and event.triggered_workflow_instance_id is None:
      if self._workflow_engine_service is None:
        raise ConflictError("生命周期联动未注入审批流服务。")
      workflow_instance = await self._workflow_engine_service.start_workflow(
        actor=event.creator,
        definition_id=event.workflow_definition_id,
        source_type="employment_event",
        source_id=event.id,
        payload=self._build_trigger_payload(event=event, channel="workflow"),
      )
      event.triggered_workflow_instance_id = workflow_instance.id
      await self._session.commit()

  async def _resolve_event_department_id(self, *, event: EmploymentEvent) -> UUID | None:
    raw_department_id = event.payload.get("department_id")
    if raw_department_id is not None:
      return UUID(str(raw_department_id))

    profile = await self._session.get(Profile, event.user_id)
    return profile.department_id if profile is not None else None

  def _build_trigger_payload(self, *, event: EmploymentEvent, channel: str) -> dict[str, object]:
    payload = dict(event.payload)
    payload["employment_event"] = {
      "event_id": str(event.id),
      "event_type": event.event_type.value,
      "user_id": str(event.user_id),
      "effective_date": event.effective_date.isoformat(),
      "title": event.title,
      "summary": event.summary,
      "channel": channel,
    }
    return payload

  async def _apply_event_side_effects(
    self,
    *,
    profile: Profile,
    user: User,
    actor: User,
    event_type: EmploymentEventType,
    effective_date: date,
    payload: dict[str, Any],
  ) -> None:
    if event_type in {EmploymentEventType.ONBOARD, EmploymentEventType.REHIRE}:
      user.status = UserStatus.ACTIVE
      profile.hire_date = effective_date

    if event_type == EmploymentEventType.OFFBOARD:
      user.status = UserStatus.OFFBOARDED
      await self._close_open_positions(user_id=user.id, effective_date=effective_date)
      await self._close_open_reporting_lines(user_id=user.id, effective_date=effective_date)

    if event_type in {
      EmploymentEventType.ONBOARD,
      EmploymentEventType.REHIRE,
      EmploymentEventType.TRANSFER,
      EmploymentEventType.PROMOTION,
    }:
      await self._apply_position_payload(
        actor=actor,
        user_id=user.id,
        effective_date=effective_date,
        payload=payload,
      )
      await self._apply_reporting_payload(
        user_id=user.id,
        effective_date=effective_date,
        payload=payload,
      )

    if event_type == EmploymentEventType.TRANSFER and payload.get("department_id") is not None:
      profile.department_id = UUID(str(payload["department_id"]))
    if payload.get("job_title") is not None:
      profile.job_title = str(payload["job_title"])

  async def _apply_position_payload(
    self,
    *,
    actor: User,
    user_id: UUID,
    effective_date: date,
    payload: dict[str, Any],
  ) -> None:
    if payload.get("position_id") is None or payload.get("department_id") is None:
      return

    assignment_type = PositionAssignmentType(payload.get("assignment_type", PositionAssignmentType.PRIMARY.value))
    await self._organization_relation_service._assign_position_record(
      user_id=user_id,
      position_id=UUID(str(payload["position_id"])),
      department_id=UUID(str(payload["department_id"])),
      assignment_type=assignment_type,
      is_primary=bool(payload.get("is_primary", True)),
      starts_at=effective_date,
      ends_at=None,
    )

  async def _apply_reporting_payload(
    self,
    *,
    user_id: UUID,
    effective_date: date,
    payload: dict[str, Any],
  ) -> None:
    manager_user_id = payload.get("manager_user_id")
    if manager_user_id is not None:
      await self._organization_relation_service._create_reporting_line_record(
        user_id=user_id,
        manager_user_id=UUID(str(manager_user_id)),
        line_type=ReportingLineType.SOLID,
        starts_at=effective_date,
        department_id=UUID(str(payload["department_id"])) if payload.get("department_id") is not None else None,
        is_primary=True,
        ends_at=None,
      )

    for dotted_manager_id in payload.get("dotted_manager_ids", []):
      await self._organization_relation_service._create_reporting_line_record(
        user_id=user_id,
        manager_user_id=UUID(str(dotted_manager_id)),
        line_type=ReportingLineType.DOTTED,
        starts_at=effective_date,
        department_id=UUID(str(payload["department_id"])) if payload.get("department_id") is not None else None,
        is_primary=False,
        ends_at=None,
      )

  async def _close_open_positions(self, *, user_id: UUID, effective_date: date) -> None:
    assignments = list(
      await self._session.scalars(
        select(ProfilePosition).where(
          ProfilePosition.user_id == user_id,
          or_(ProfilePosition.ends_at.is_(None), ProfilePosition.ends_at >= effective_date),
        )
      )
    )
    for assignment in assignments:
      assignment.ends_at = effective_date
      assignment.is_primary = False

  async def _close_open_reporting_lines(self, *, user_id: UUID, effective_date: date) -> None:
    reporting_lines = list(
      await self._session.scalars(
        select(ReportingLine).where(
          ReportingLine.user_id == user_id,
          or_(ReportingLine.ends_at.is_(None), ReportingLine.ends_at >= effective_date),
        )
      )
    )
    for reporting_line in reporting_lines:
      reporting_line.ends_at = effective_date
      reporting_line.is_primary = False
