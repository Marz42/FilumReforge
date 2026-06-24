"""F-24: department/subtree scheduled graph template instantiation."""

from __future__ import annotations

import json
from collections import deque
from datetime import UTC, datetime, timezone as dt_timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import UserStatus, WorkflowGraphInstanceStatus, WorkflowGraphTemplateStatus
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models import (
  Department,
  Profile,
  User,
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateNode,
  WorkflowGraphTemplateSchedule,
)
from app.schemas.messages import NotificationMessage
from app.schemas.workflow_graph_schedule import (
  GraphTemplateScheduleCreateRequest,
  GraphTemplateScheduleRead,
  GraphTemplateScheduleRunNowResponse,
  GraphTemplateScheduleUpdateRequest,
)
from app.schemas.workflow_video import ParticipantsSnapshotEntry
from app.services.access_control import (
  can_publish_org_tasks,
  ensure_active_user,
  expand_department_ids,
  get_effective_managed_department_ids,
  is_management_role,
)
from app.services.notification_service import NotificationService
from app.services.participant_resolution_service import ParticipantResolutionService
from app.services.workflow_video_instantiation_service import WorkflowVideoInstantiationService

MAX_SUBTREE_DEPARTMENTS = 100


def template_is_schedulable(
  *,
  template: WorkflowGraphTemplate,
  nodes: list[WorkflowGraphTemplateNode],
) -> bool:
  config = template.config if isinstance(template.config, dict) else {}
  if config.get("schedulable") is not True:
    return False
  if str(config.get("run_kind") or "batch") != "batch":
    return False
  if config.get("aggregate_mode") == "streaming":
    return False
  policies = config.get("participant_policies")
  if not isinstance(policies, dict) or not policies:
    return False
  has_multi_instance = any(
    isinstance(node.config, dict)
    and node.config.get("kind") == "multi_instance"
    and node.config.get("expand_from")
    for node in nodes
  )
  return has_multi_instance


def resolve_primary_participant_policy_ref(
  *,
  template: WorkflowGraphTemplate,
  nodes: list[WorkflowGraphTemplateNode],
) -> str:
  config = template.config if isinstance(template.config, dict) else {}
  policies = config.get("participant_policies")
  if not isinstance(policies, dict) or not policies:
    raise ConflictError("模板未配置 participant_policies。")
  for node in nodes:
    node_config = node.config if isinstance(node.config, dict) else {}
    expand_from = node_config.get("expand_from")
    if node_config.get("kind") == "multi_instance" and isinstance(expand_from, str) and expand_from in policies:
      return expand_from
  return next(iter(policies.keys()))


class WorkflowGraphTemplateScheduleService:
  def __init__(
    self,
    session: AsyncSession,
    *,
    notification_service: NotificationService | None = None,
    instantiation_service: WorkflowVideoInstantiationService | None = None,
  ) -> None:
    self._session = session
    self._notification_service = notification_service
    self._instantiation_service = instantiation_service
    self._participant_service = ParticipantResolutionService(session)

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
    zone = WorkflowGraphTemplateScheduleService._resolve_timezone(timezone_name)
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

  async def _ensure_can_manage_scope(self, *, actor: User, scope_department_id: UUID) -> None:
    ensure_active_user(actor)
    if not await can_publish_org_tasks(self._session, actor):
      raise AuthorizationError("当前账号不能管理周期任务调度。")
    if is_management_role(actor):
      return
    managed_ids = await get_effective_managed_department_ids(self._session, actor.id)
    expanded = await expand_department_ids(self._session, managed_ids)
    if scope_department_id not in expanded:
      raise AuthorizationError("无权在该部门范围配置周期任务。")

  async def _load_template_graph(
    self,
    *,
    template_id: UUID,
  ) -> tuple[WorkflowGraphTemplate, list[WorkflowGraphTemplateNode]]:
    template = await self._session.get(WorkflowGraphTemplate, template_id)
    if template is None:
      raise NotFoundError("图模板不存在。")
    nodes = list(
      await self._session.scalars(
        select(WorkflowGraphTemplateNode)
        .where(WorkflowGraphTemplateNode.template_id == template_id)
        .order_by(WorkflowGraphTemplateNode.sort_order)
      )
    )
    return template, nodes

  async def _validate_schedulable_template(
    self,
    *,
    template: WorkflowGraphTemplate,
    nodes: list[WorkflowGraphTemplateNode],
  ) -> None:
    if template.status != WorkflowGraphTemplateStatus.ACTIVE:
      raise ConflictError("仅 active 且 schedulable 的模板可配置周期任务。")
    if not template_is_schedulable(template=template, nodes=nodes):
      raise ConflictError("模板未标记 schedulable 或不符合批次采集调度条件。")

  async def _list_departments(self) -> list[Department]:
    return list(await self._session.scalars(select(Department)))

  async def _department_has_active_members(self, *, department_id: UUID) -> bool:
    member_id = await self._session.scalar(
      select(Profile.user_id)
      .join(User, User.id == Profile.user_id)
      .where(
        Profile.department_id == department_id,
        User.status == UserStatus.ACTIVE,
      )
      .limit(1)
    )
    return member_id is not None

  async def expand_target_departments(
    self,
    *,
    scope_department_id: UUID,
    scope_mode: str,
    exclude_department_ids: set[UUID],
  ) -> list[Department]:
    departments = await self._list_departments()
    department_map = {department.id: department for department in departments}
    root = department_map.get(scope_department_id)
    if root is None:
      raise NotFoundError("作用域部门不存在。")

    candidates: list[Department] = []
    if scope_mode == "self":
      if root.is_active and root.id not in exclude_department_ids:
        candidates = [root]
    else:
      queue: deque[UUID] = deque([root.id])
      seen: set[UUID] = set()
      while queue and len(candidates) < MAX_SUBTREE_DEPARTMENTS:
        department_id = queue.popleft()
        if department_id in seen or department_id in exclude_department_ids:
          continue
        seen.add(department_id)
        department = department_map.get(department_id)
        if department is None or not department.is_active:
          continue
        candidates.append(department)
        for child in departments:
          if child.parent_id == department_id and child.is_active:
            queue.append(child.id)
      if len(seen) >= MAX_SUBTREE_DEPARTMENTS:
        raise ConflictError(f"子树部门数超过上限 {MAX_SUBTREE_DEPARTMENTS}。")

    result: list[Department] = []
    for department in candidates:
      if department.id in exclude_department_ids:
        continue
      if await self._department_has_active_members(department_id=department.id):
        result.append(department)
    return result

  async def _has_active_run(self, *, template_id: UUID, department_id: UUID) -> bool:
    existing = await self._session.scalar(
      select(WorkflowGraphInstance.id)
      .where(
        WorkflowGraphInstance.template_id == template_id,
        WorkflowGraphInstance.department_id == department_id,
        WorkflowGraphInstance.status == WorkflowGraphInstanceStatus.ACTIVE,
      )
      .limit(1)
    )
    return existing is not None

  async def validate_no_active_run_overlap(
    self,
    *,
    template_id: UUID,
    target_departments: list[Department],
  ) -> None:
    conflicts: list[str] = []
    for department in target_departments:
      if await self._has_active_run(template_id=template_id, department_id=department.id):
        conflicts.append(department.name)
    if conflicts:
      raise ConflictError(
        "以下部门已有进行中的同模板 Run，无法发布周期任务："
        + "、".join(conflicts[:5])
        + ("…" if len(conflicts) > 5 else "")
      )

  async def _build_participants_snapshot(
    self,
    *,
    actor: User,
    template: WorkflowGraphTemplate,
    nodes: list[WorkflowGraphTemplateNode],
    department_id: UUID,
    participant_mode: str,
    participant_user_ids: list[UUID],
    exclude_user_ids: set[UUID],
  ) -> dict[str, ParticipantsSnapshotEntry]:
    policy_ref = resolve_primary_participant_policy_ref(template=template, nodes=nodes)
    policy = self._participant_service._policy_from_template(template, policy_ref)

    if participant_mode == "subset":
      if not participant_user_ids:
        raise ConflictError("subset 模式至少选择一名参与人。")
      users = await self._participant_service._load_users_with_profiles(user_ids=participant_user_ids)
      filtered_ids = [user.id for user in users if user.id not in exclude_user_ids]
      if not filtered_ids:
        raise ConflictError("排除后无可用参与人。")
      return {
        policy_ref: ParticipantsSnapshotEntry(mode="subset", user_ids=filtered_ids),
      }

    users = await self._participant_service.resolve_policy(
      actor=actor,
      policy=policy,
      policy_ref=policy_ref,
      department_id=department_id,
      mode="all",
    )
    filtered_ids = [user.id for user in users if user.id not in exclude_user_ids]
    if not filtered_ids:
      raise ConflictError("排除后无可用参与人。")
    mode = "all" if len(filtered_ids) == len(users) else "subset"
    return {
      policy_ref: ParticipantsSnapshotEntry(mode=mode, user_ids=filtered_ids),
    }

  def _render_run_label(
    self,
    *,
    schedule: WorkflowGraphTemplateSchedule,
    department: Department,
    now: datetime,
  ) -> str:
    template = schedule.run_label_template or "{name} · {date}"
    return (
      template.replace("{name}", schedule.name)
      .replace("{date}", now.astimezone(dt_timezone.utc).strftime("%Y-%m-%d"))
      .replace("{department}", department.name)
    )

  async def _notify_managers(
    self,
    *,
    schedule: WorkflowGraphTemplateSchedule,
    departments: list[Department],
  ) -> None:
    if self._notification_service is None or schedule.next_run_at is None:
      return
    next_run_text = schedule.next_run_at.astimezone(
      self._resolve_timezone(schedule.timezone)
    ).strftime("%Y-%m-%d %H:%M")
    body = f"通知：您有一个新的周期任务，下一次开始于 {next_run_text}"
    notified: set[UUID] = set()
    for department in departments:
      if department.manager_id is None or department.manager_id in notified:
        continue
      manager = await self._session.get(User, department.manager_id)
      if manager is None:
        continue
      notified.add(manager.id)
      await self._notification_service.send(
        NotificationMessage(
          source_type="workflow_graph_template_schedule",
          source_id=schedule.id,
          recipient_user_id=manager.id,
          recipient_email=manager.email,
          message_type="schedule_periodic_task_created",
          title="新的周期任务",
          body_text=body,
          payload={
            "schedule_id": str(schedule.id),
            "schedule_name": schedule.name,
            "next_run_at": schedule.next_run_at.isoformat(),
            "department_id": str(department.id),
          },
        )
      )

  def _to_read(
    self,
    schedule: WorkflowGraphTemplateSchedule,
    *,
    template: WorkflowGraphTemplate | None = None,
    department: Department | None = None,
  ) -> GraphTemplateScheduleRead:
    return GraphTemplateScheduleRead(
      id=schedule.id,
      template_id=schedule.template_id,
      template_code=template.code if template else None,
      template_name=template.name if template else None,
      name=schedule.name,
      scope_department_id=schedule.scope_department_id,
      scope_department_name=department.name if department else None,
      scope_mode=schedule.scope_mode,  # type: ignore[arg-type]
      cron_expr=schedule.cron_expr,
      timezone=schedule.timezone,
      default_inputs=dict(schedule.default_inputs or {}),
      run_label_template=schedule.run_label_template,
      participant_mode=schedule.participant_mode,  # type: ignore[arg-type]
      participant_user_ids=[UUID(str(value)) for value in schedule.participant_user_ids or []],
      exclude_department_ids=[UUID(str(value)) for value in schedule.exclude_department_ids or []],
      exclude_user_ids=[UUID(str(value)) for value in schedule.exclude_user_ids or []],
      is_active=schedule.is_active,
      created_by=schedule.created_by,
      next_run_at=schedule.next_run_at,
      last_run_at=schedule.last_run_at,
      last_run_status=schedule.last_run_status,
      last_run_message=schedule.last_run_message,
      last_run_instance_count=schedule.last_run_instance_count,
      created_at=schedule.created_at,
      updated_at=schedule.updated_at,
    )

  async def list_schedules(self, *, actor: User) -> list[GraphTemplateScheduleRead]:
    ensure_active_user(actor)
    statement = (
      select(WorkflowGraphTemplateSchedule)
      .options(
        selectinload(WorkflowGraphTemplateSchedule.template),
        selectinload(WorkflowGraphTemplateSchedule.scope_department),
      )
      .order_by(WorkflowGraphTemplateSchedule.updated_at.desc())
    )
    managed_ids = await get_effective_managed_department_ids(self._session, actor.id)
    if not is_management_role(actor):
      expanded = await expand_department_ids(self._session, managed_ids)
      statement = statement.where(WorkflowGraphTemplateSchedule.scope_department_id.in_(expanded))
    schedules = list(await self._session.scalars(statement))
    return [
      self._to_read(
        schedule,
        template=schedule.template,
        department=schedule.scope_department,
      )
      for schedule in schedules
    ]

  async def create_schedule(
    self,
    *,
    actor: User,
    payload: GraphTemplateScheduleCreateRequest,
  ) -> GraphTemplateScheduleRead:
    await self._ensure_can_manage_scope(actor=actor, scope_department_id=payload.scope_department_id)
    template, nodes = await self._load_template_graph(template_id=payload.template_id)
    await self._validate_schedulable_template(template=template, nodes=nodes)

    exclude_department_ids = set(payload.exclude_department_ids)
    target_departments = await self.expand_target_departments(
      scope_department_id=payload.scope_department_id,
      scope_mode=payload.scope_mode,
      exclude_department_ids=exclude_department_ids,
    )
    if not target_departments:
      raise ConflictError("作用域内没有可调度部门（需有在职成员）。")

    if payload.is_active:
      await self.validate_no_active_run_overlap(
        template_id=template.id,
        target_departments=target_departments,
      )

    now = datetime.now(dt_timezone.utc)
    next_run_at = (
      self._compute_next_run_at(
        cron_expr=payload.cron_expr,
        timezone_name=payload.timezone,
        base_time=now,
      )
      if payload.is_active
      else None
    )

    schedule = WorkflowGraphTemplateSchedule(
      template_id=template.id,
      name=payload.name.strip(),
      scope_department_id=payload.scope_department_id,
      scope_mode=payload.scope_mode,
      cron_expr=payload.cron_expr.strip(),
      timezone=payload.timezone.strip(),
      default_inputs=dict(payload.default_inputs or {}),
      run_label_template=payload.run_label_template,
      participant_mode=payload.participant_mode,
      participant_user_ids=[str(user_id) for user_id in payload.participant_user_ids],
      exclude_department_ids=[str(department_id) for department_id in payload.exclude_department_ids],
      exclude_user_ids=[str(user_id) for user_id in payload.exclude_user_ids],
      is_active=payload.is_active,
      created_by=actor.id,
      next_run_at=next_run_at,
    )
    self._session.add(schedule)
    await self._session.flush()
    await self._notify_managers(schedule=schedule, departments=target_departments)
    await self._session.commit()
    await self._session.refresh(schedule)
    department = await self._session.get(Department, schedule.scope_department_id)
    return self._to_read(schedule, template=template, department=department)

  async def _get_schedule_or_raise(
    self,
    *,
    actor: User,
    schedule_id: UUID,
  ) -> WorkflowGraphTemplateSchedule:
    schedule = await self._session.scalar(
      select(WorkflowGraphTemplateSchedule)
      .options(
        selectinload(WorkflowGraphTemplateSchedule.template),
        selectinload(WorkflowGraphTemplateSchedule.scope_department),
      )
      .where(WorkflowGraphTemplateSchedule.id == schedule_id)
    )
    if schedule is None:
      raise NotFoundError("周期任务不存在。")
    await self._ensure_can_manage_scope(actor=actor, scope_department_id=schedule.scope_department_id)
    return schedule

  async def update_schedule(
    self,
    *,
    actor: User,
    schedule_id: UUID,
    payload: GraphTemplateScheduleUpdateRequest,
  ) -> GraphTemplateScheduleRead:
    schedule = await self._get_schedule_or_raise(actor=actor, schedule_id=schedule_id)
    template, nodes = await self._load_template_graph(template_id=schedule.template_id)
    await self._validate_schedulable_template(template=template, nodes=nodes)

    if payload.name is not None:
      schedule.name = payload.name.strip()
    if payload.scope_department_id is not None:
      await self._ensure_can_manage_scope(actor=actor, scope_department_id=payload.scope_department_id)
      schedule.scope_department_id = payload.scope_department_id
    if payload.scope_mode is not None:
      schedule.scope_mode = payload.scope_mode
    if payload.cron_expr is not None:
      schedule.cron_expr = payload.cron_expr.strip()
    if payload.timezone is not None:
      schedule.timezone = payload.timezone.strip()
    if payload.default_inputs is not None:
      schedule.default_inputs = dict(payload.default_inputs)
    if payload.run_label_template is not None:
      schedule.run_label_template = payload.run_label_template
    if payload.participant_mode is not None:
      schedule.participant_mode = payload.participant_mode
    if payload.participant_user_ids is not None:
      schedule.participant_user_ids = [str(user_id) for user_id in payload.participant_user_ids]
    if payload.exclude_department_ids is not None:
      schedule.exclude_department_ids = [str(value) for value in payload.exclude_department_ids]
    if payload.exclude_user_ids is not None:
      schedule.exclude_user_ids = [str(value) for value in payload.exclude_user_ids]
    if payload.is_active is not None:
      schedule.is_active = payload.is_active

    exclude_department_ids = {UUID(str(value)) for value in schedule.exclude_department_ids or []}
    target_departments = await self.expand_target_departments(
      scope_department_id=schedule.scope_department_id,
      scope_mode=schedule.scope_mode,
      exclude_department_ids=exclude_department_ids,
    )
    if schedule.is_active:
      await self.validate_no_active_run_overlap(
        template_id=schedule.template_id,
        target_departments=target_departments,
      )
      schedule.next_run_at = self._compute_next_run_at(
        cron_expr=schedule.cron_expr,
        timezone_name=schedule.timezone,
        base_time=datetime.now(dt_timezone.utc),
      )
    else:
      schedule.next_run_at = None

    await self._session.commit()
    await self._session.refresh(schedule)
    if schedule.is_active:
      await self._notify_managers(schedule=schedule, departments=target_departments)
    return self._to_read(schedule, template=template, department=schedule.scope_department)

  async def run_schedule_now(
    self,
    *,
    actor: User,
    schedule_id: UUID,
  ) -> GraphTemplateScheduleRunNowResponse:
    schedule = await self._get_schedule_or_raise(actor=actor, schedule_id=schedule_id)
    return await self._execute_schedule(
      schedule=schedule,
      current_time=datetime.now(dt_timezone.utc),
      advance_next_run=False,
    )

  async def _execute_schedule(
    self,
    *,
    schedule: WorkflowGraphTemplateSchedule,
    current_time: datetime,
    advance_next_run: bool,
  ) -> GraphTemplateScheduleRunNowResponse:
    if self._instantiation_service is None:
      raise ConflictError("图模板实例化服务未配置。")

    template, nodes = await self._load_template_graph(template_id=schedule.template_id)
    await self._validate_schedulable_template(template=template, nodes=nodes)

    exclude_department_ids = {UUID(str(value)) for value in schedule.exclude_department_ids or []}
    exclude_user_ids = {UUID(str(value)) for value in schedule.exclude_user_ids or []}
    participant_user_ids = [UUID(str(value)) for value in schedule.participant_user_ids or []]
    target_departments = await self.expand_target_departments(
      scope_department_id=schedule.scope_department_id,
      scope_mode=schedule.scope_mode,
      exclude_department_ids=exclude_department_ids,
    )

    details: list[dict[str, Any]] = []
    created_count = 0
    skipped_count = 0
    failed_count = 0

    for department in target_departments:
      detail: dict[str, Any] = {
        "department_id": str(department.id),
        "department_name": department.name,
      }
      if department.manager_id is None:
        detail["status"] = "failed"
        detail["reason"] = "部门未配置负责人。"
        failed_count += 1
        details.append(detail)
        continue
      if await self._has_active_run(template_id=template.id, department_id=department.id):
        detail["status"] = "skipped"
        detail["reason"] = "已有进行中的 Run。"
        skipped_count += 1
        details.append(detail)
        continue

      manager = await self._session.get(User, department.manager_id)
      if manager is None:
        detail["status"] = "failed"
        detail["reason"] = "负责人不存在。"
        failed_count += 1
        details.append(detail)
        continue
      ensure_active_user(manager)

      try:
        participants_snapshot = await self._build_participants_snapshot(
          actor=manager,
          template=template,
          nodes=nodes,
          department_id=department.id,
          participant_mode=schedule.participant_mode,
          participant_user_ids=participant_user_ids,
          exclude_user_ids=exclude_user_ids,
        )
        inputs = dict(schedule.default_inputs or {})
        inputs["manager_user_id"] = str(manager.id)
        result = await self._instantiation_service.instantiate_graph_template(
          actor=manager,
          template_id=template.id,
          inputs=inputs,
          participants_snapshot=participants_snapshot,
          department_id=department.id,
          run_label=self._render_run_label(schedule=schedule, department=department, now=current_time),
          skip_publish_permission=True,
        )
        context = dict(result.instance.context or {})
        context["schedule_id"] = str(schedule.id)
        result.instance.context = context
        await self._session.flush()
        detail["status"] = "created"
        detail["instance_id"] = str(result.instance.id)
        created_count += 1
      except Exception as exc:
        detail["status"] = "failed"
        detail["reason"] = str(exc)
        failed_count += 1
      details.append(detail)

    schedule.last_run_at = current_time
    schedule.last_run_instance_count = created_count
    if failed_count and created_count:
      schedule.last_run_status = "partial"
    elif failed_count:
      schedule.last_run_status = "failed"
    else:
      schedule.last_run_status = "success"
    schedule.last_run_message = json.dumps(details, ensure_ascii=False)
    if advance_next_run and schedule.is_active:
      schedule.next_run_at = self._compute_next_run_at(
        cron_expr=schedule.cron_expr,
        timezone_name=schedule.timezone,
        base_time=current_time,
      )
    await self._session.commit()

    return GraphTemplateScheduleRunNowResponse(
      created_count=created_count,
      skipped_count=skipped_count,
      failed_count=failed_count,
      details=details,
    )

  async def run_due_schedules(self, *, now: datetime | None = None) -> int:
    current_time = now or datetime.now(dt_timezone.utc)
    if current_time.tzinfo is None:
      current_time = current_time.replace(tzinfo=dt_timezone.utc)

    schedules = list(
      await self._session.scalars(
        select(WorkflowGraphTemplateSchedule)
        .where(
          WorkflowGraphTemplateSchedule.is_active.is_(True),
          WorkflowGraphTemplateSchedule.next_run_at.is_not(None),
          WorkflowGraphTemplateSchedule.next_run_at <= current_time,
        )
        .order_by(WorkflowGraphTemplateSchedule.next_run_at.asc())
      )
    )
    executed = 0
    for schedule in schedules:
      await self._execute_schedule(
        schedule=schedule,
        current_time=current_time,
        advance_next_run=True,
      )
      executed += 1
    return executed
