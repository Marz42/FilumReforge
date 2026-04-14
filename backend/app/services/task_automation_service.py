from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models import TaskSchedule, TaskTemplate, User
from app.services.access_control import MANAGEMENT_ROLES, ensure_active_user
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

  @staticmethod
  def _ensure_management(actor: User) -> None:
    if actor.role not in MANAGEMENT_ROLES:
      raise AuthorizationError("当前账号不能管理自动化调度。")

  @staticmethod
  def _compute_next_run_at(*, cron_expr: str, timezone_name: str, base_time: datetime) -> datetime:
    try:
      zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
      raise ConflictError("无效的时区配置。") from exc

    if base_time.tzinfo is None:
      base_time = base_time.replace(tzinfo=UTC)
    localized_base = base_time.astimezone(zone)
    try:
      next_localized = croniter(cron_expr, localized_base).get_next(datetime)
    except ValueError as exc:
      raise ConflictError("无效的 cron 表达式。") from exc
    if next_localized.tzinfo is None:
      next_localized = next_localized.replace(tzinfo=zone)
    return next_localized.astimezone(UTC)

  async def _get_schedule_or_raise(self, *, actor: User, schedule_id) -> TaskSchedule:
    statement = self._statement().where(TaskSchedule.id == schedule_id)
    if actor.role not in MANAGEMENT_ROLES:
      statement = statement.where(TaskSchedule.owner_user_id == actor.id)
    schedule = await self._session.scalar(statement)
    if schedule is None:
      raise NotFoundError("自动化调度不存在。")
    return schedule

  async def list_schedules(self, *, actor: User) -> list[TaskSchedule]:
    ensure_active_user(actor)
    statement = self._statement().order_by(TaskSchedule.updated_at.desc())
    if actor.role not in MANAGEMENT_ROLES:
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
    self._ensure_management(actor)

    template = await self._session.get(TaskTemplate, template_id)
    if template is None:
      raise NotFoundError("任务模板不存在。")
    if not template.is_active:
      raise ConflictError("未启用的模板不能创建自动化调度。")

    next_run_at = self._compute_next_run_at(
      cron_expr=cron_expr,
      timezone_name=timezone,
      base_time=datetime.now(UTC),
    )
    schedule = TaskSchedule(
      template_id=template.id,
      owner_user_id=actor.id,
      cron_expr=cron_expr.strip(),
      timezone=timezone.strip(),
      next_run_at=next_run_at,
      is_active=is_active,
      payload=dict(payload or {}),
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
    self._ensure_management(actor)
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
        base_time=datetime.now(UTC),
      )
      if schedule.is_active
      else None
    )
    await self._session.commit()
    return await self._get_schedule_or_raise(actor=actor, schedule_id=schedule.id)

  async def run_due_schedules(self, *, now: datetime | None = None) -> int:
    current_time = now.astimezone(UTC) if now is not None and now.tzinfo is not None else now
    if current_time is None:
      current_time = datetime.now(UTC)
    elif current_time.tzinfo is None:
      current_time = current_time.replace(tzinfo=UTC)

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
      owner = schedule.owner
      if owner is None:
        owner = await self._session.get(User, schedule.owner_user_id)
      if owner is None:
        raise NotFoundError("调度所属用户不存在。")
      ensure_active_user(owner)

      await self._template_service.instantiate_template(
        actor=owner,
        template_id=schedule.template_id,
        payload=schedule.payload,
      )
      schedule.next_run_at = self._compute_next_run_at(
        cron_expr=schedule.cron_expr,
        timezone_name=schedule.timezone,
        base_time=current_time,
      )
      await self._session.commit()
      executed_count += 1

    return executed_count
