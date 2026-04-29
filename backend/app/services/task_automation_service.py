from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models import TaskSchedule, TaskTemplate, User
from app.services.access_control import can_manage_task_templates, ensure_active_user
from app.services.task_template_service import TaskTemplateService


class TaskAutomationService:
  def __init__(
    self,
    session: AsyncSession,
    template_service: TaskTemplateService,
  ) -> None:
    self._session = session
    self._template_service = template_service

  def _statement(self):
    return select(TaskSchedule).options(
      selectinload(TaskSchedule.template),
      selectinload(TaskSchedule.owner),
    )

  async def _ensure_manage_templates(self, *, actor: User) -> None:
    if not await can_manage_task_templates(self._session, actor):
      raise AuthorizationError("当前账号不能管理自动化调度。")

  @staticmethod
  def _resolve_timezone(timezone_name: str):
    normalized_timezone = timezone_name.strip()
    if not normalized_timezone:
      raise ConflictError("无效的时区配置。")
    if normalized_timezone.upper() == "UTC":
      return dt_timezone.utc
    try:
      return ZoneInfo(normalized_timezone)
    except ZoneInfoNotFoundError as exc:
      raise ConflictError("无效的时区配置。") from exc

  @staticmethod
  def _compute_next_run_at(*, cron_expr: str, timezone_name: str, base_time: datetime) -> datetime:
    zone = TaskAutomationService._resolve_timezone(timezone_name)

    if base_time.tzinfo is None:
      base_time = base_time.replace(tzinfo=dt_timezone.utc)
    localized_base = base_time.astimezone(zone)
    try:
      next_localized = croniter(cron_expr, localized_base).get_next(datetime)
    except ValueError as exc:
      raise ConflictError("无效的 cron 表达式。") from exc
    if next_localized.tzinfo is None:
      next_localized = next_localized.replace(tzinfo=zone)
    return next_localized.astimezone(dt_timezone.utc)

  async def _get_schedule_or_raise(self, *, actor: User, schedule_id) -> TaskSchedule:
    statement = self._statement().where(TaskSchedule.id == schedule_id)
    if not await can_manage_task_templates(self._session, actor):
      statement = statement.where(TaskSchedule.owner_user_id == actor.id)
    schedule = await self._session.scalar(statement)
    if schedule is None:
      raise NotFoundError("自动化调度不存在。")
    return schedule

  async def list_schedules(self, *, actor: User) -> list[TaskSchedule]:
    ensure_active_user(actor)
    statement = self._statement().order_by(TaskSchedule.updated_at.desc())
    if not await can_manage_task_templates(self._session, actor):
      statement = statement.where(TaskSchedule.owner_user_id == actor.id)
    return list(await self._session.scalars(statement))

  async def create_schedule(
    self,
    *,
    actor: User,
    template_id,
    cron_expr: str,
    timezone: str = "UTC",
    payload: dict[str, object] | None = None,
    is_active: bool = True,
  ) -> TaskSchedule:
    ensure_active_user(actor)
    await self._ensure_manage_templates(actor=actor)

    template = await self._session.get(TaskTemplate, template_id)
    if template is None:
      raise NotFoundError("任务模板不存在。")
    if not template.is_active:
      raise ConflictError("未启用的模板不能创建自动化调度。")

    next_run_at = self._compute_next_run_at(
      cron_expr=cron_expr,
      timezone_name=timezone,
      base_time=datetime.now(dt_timezone.utc),
    )
    schedule = TaskSchedule(
      template_id=template.id,
      owner_user_id=actor.id,
      cron_expr=cron_expr.strip(),
      timezone=timezone.strip(),
      next_run_at=next_run_at,
      is_active=is_active,
      payload=dict(payload or {}),
      last_run_at=None,
      last_run_status=None,
      last_run_message=None,
      last_run_task_count=None,
    )
    self._session.add(schedule)
    await self._session.commit()
    return await self._get_schedule_or_raise(actor=actor, schedule_id=schedule.id)

  async def update_schedule(
    self,
    *,
    actor: User,
    schedule_id,
    cron_expr: str | None = None,
    timezone: str | None = None,
    payload: dict[str, object] | None = None,
    is_active: bool | None = None,
  ) -> TaskSchedule:
    ensure_active_user(actor)
    await self._ensure_manage_templates(actor=actor)
    schedule = await self._get_schedule_or_raise(actor=actor, schedule_id=schedule_id)

    if cron_expr is not None:
      schedule.cron_expr = cron_expr.strip()
    if timezone is not None:
      schedule.timezone = timezone.strip()
    if payload is not None:
      schedule.payload = dict(payload)
    if is_active is not None:
      schedule.is_active = is_active

    schedule.next_run_at = (
      self._compute_next_run_at(
        cron_expr=schedule.cron_expr,
        timezone_name=schedule.timezone,
        base_time=datetime.now(dt_timezone.utc),
      )
      if schedule.is_active
      else None
    )
    await self._session.commit()
    return await self._get_schedule_or_raise(actor=actor, schedule_id=schedule.id)

  async def run_due_schedules(self, *, now: datetime | None = None) -> int:
    current_time = now.astimezone(dt_timezone.utc) if now is not None and now.tzinfo is not None else now
    if current_time is None:
      current_time = datetime.now(dt_timezone.utc)
    elif current_time.tzinfo is None:
      current_time = current_time.replace(tzinfo=dt_timezone.utc)

    schedules = list(
      await self._session.scalars(
        self._statement()
        .where(
          TaskSchedule.is_active.is_(True),
          TaskSchedule.next_run_at.is_not(None),
          TaskSchedule.next_run_at <= current_time,
        )
        .order_by(TaskSchedule.next_run_at.asc())
      )
    )

    executed_count = 0
    for schedule in schedules:
      try:
        owner = schedule.owner
        if owner is None:
          owner = await self._session.get(User, schedule.owner_user_id)
        if owner is None:
          raise NotFoundError("调度所属用户不存在。")
        ensure_active_user(owner)

        instantiation = await self._template_service.instantiate_template(
          actor=owner,
          template_id=schedule.template_id,
          payload=schedule.payload,
        )
        schedule.last_run_at = current_time
        schedule.last_run_status = "success"
        schedule.last_run_message = f"成功实例化 {len(instantiation.tasks)} 条任务"
        schedule.last_run_task_count = len(instantiation.tasks)
        executed_count += 1
      except Exception as exc:
        schedule.last_run_at = current_time
        schedule.last_run_status = "failed"
        schedule.last_run_message = str(exc)
        schedule.last_run_task_count = 0

      schedule.next_run_at = self._compute_next_run_at(
        cron_expr=schedule.cron_expr,
        timezone_name=schedule.timezone,
        base_time=current_time,
      )
      await self._session.commit()

    return executed_count
