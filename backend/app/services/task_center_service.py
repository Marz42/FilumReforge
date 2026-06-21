from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import DepartmentCapability, UserStatus, WorkflowGraphTemplateStatus
from app.models import Department, Profile, User, WorkflowGraphTemplate, WorkflowGraphTemplateNode
from app.services.access_control import (
  TASK_SCOPE_TYPES,
  can_manage_task_templates,
  can_publish_org_tasks,
  ensure_active_user,
  get_actor_department,
  get_effective_managed_department_ids,
  is_management_role,
)
from app.services.task_memo_service import TaskMemoService
from app.services.task_service import (
  TaskCenterListPage,
  TaskHistoryEntry,
  TaskInboxEntry,
  TaskService,
  TaskTrackingEntry,
)


@dataclass(slots=True)
class TaskCenterDepartmentOption:
  id: UUID
  label: str


@dataclass(slots=True)
class TaskCenterUserOption:
  user_id: UUID
  email: str
  real_name: str | None
  department_id: UUID | None
  department_name: str | None
  label: str


@dataclass(slots=True)
class TaskTemplateSummary:
  id: UUID
  name: str
  category: str
  is_active: bool
  step_count: int


@dataclass(slots=True)
class TaskCenterSnapshot:
  permissions: dict[str, bool]
  template_summaries: list[TaskTemplateSummary]
  publish_department_options: list[TaskCenterDepartmentOption]
  publish_user_options: list[TaskCenterUserOption]
  task_inbox: list[TaskInboxEntry]
  task_tracking: list[TaskTrackingEntry]
  task_history: list[TaskHistoryEntry]
  task_memos: list
  inbox_next_cursor: UUID | None = None
  inbox_has_more: bool = False
  tracking_next_cursor: UUID | None = None
  tracking_has_more: bool = False
  history_next_cursor: UUID | None = None
  history_has_more: bool = False


class TaskCenterService:
  def __init__(
    self,
    session: AsyncSession,
    task_service: TaskService,
    task_memo_service: TaskMemoService,
  ) -> None:
    self._session = session
    self._task_service = task_service
    self._task_memo_service = task_memo_service

  async def _list_publish_department_options(self, *, actor: User) -> list[TaskCenterDepartmentOption]:
    if not await can_publish_org_tasks(self._session, actor):
      return []

    if is_management_role(actor):
      departments = list(
        await self._session.scalars(
          select(Department)
          .where(Department.is_active.is_(True))
          .order_by(Department.sort_order.asc(), Department.name.asc())
        )
      )
      return [TaskCenterDepartmentOption(id=department.id, label=department.name) for department in departments]

    managed_department_ids = await get_effective_managed_department_ids(
      self._session,
      actor.id,
      scope_types=TASK_SCOPE_TYPES,
    )
    if managed_department_ids:
      departments = list(
        await self._session.scalars(
          select(Department)
          .where(Department.id.in_(managed_department_ids), Department.is_active.is_(True))
          .order_by(Department.sort_order.asc(), Department.name.asc())
        )
      )
      return [TaskCenterDepartmentOption(id=department.id, label=department.name) for department in departments]

    actor_department = await get_actor_department(self._session, actor.id)
    if actor_department is None:
      return []
    if DepartmentCapability.PUBLISH_ORG_TASK.value not in set(actor_department.capabilities):
      return []
    return [TaskCenterDepartmentOption(id=actor_department.id, label=actor_department.name)]

  async def _list_publish_user_options(
    self,
    *,
    actor: User,
    department_options: list[TaskCenterDepartmentOption],
  ) -> list[TaskCenterUserOption]:
    if not department_options and not is_management_role(actor):
      return []

    statement = (
      select(User)
      .options(selectinload(User.profile))
      .where(User.status == UserStatus.ACTIVE)
      .order_by(User.created_at.asc())
    )
    if not is_management_role(actor):
      department_ids = [option.id for option in department_options]
      statement = statement.join(Profile, Profile.user_id == User.id).where(Profile.department_id.in_(department_ids))

    users = list(await self._session.scalars(statement))
    department_name_map: dict[UUID, str] = {}
    department_ids = {
      profile.department_id
      for user in users
      if user.profile is not None and user.profile.department_id is not None
      for profile in [user.profile]
    }
    if department_ids:
      departments = list(
        await self._session.scalars(select(Department).where(Department.id.in_(department_ids)))
      )
      department_name_map = {department.id: department.name for department in departments}
    options: list[TaskCenterUserOption] = []
    for user in users:
      profile = user.profile
      real_name = profile.real_name if profile is not None else None
      department_name = (
        department_name_map.get(profile.department_id)
        if profile is not None and profile.department_id is not None
        else None
      )
      label = real_name or user.email
      if real_name:
        label = f"{real_name}（{user.email}）"
      options.append(
        TaskCenterUserOption(
          user_id=user.id,
          email=user.email,
          real_name=real_name,
          department_id=profile.department_id if profile is not None else None,
          department_name=department_name,
          label=label,
        )
      )
    return options

  async def _build_template_summaries(self, *, actor: User) -> list[TaskTemplateSummary]:
    can_manage = await can_manage_task_templates(self._session, actor)
    statement = (
      select(
        WorkflowGraphTemplate,
        func.count(WorkflowGraphTemplateNode.id).label("node_count"),
      )
      .outerjoin(
        WorkflowGraphTemplateNode,
        WorkflowGraphTemplateNode.template_id == WorkflowGraphTemplate.id,
      )
      .group_by(WorkflowGraphTemplate.id)
      .order_by(WorkflowGraphTemplate.name.asc())
    )
    if not can_manage:
      statement = statement.where(WorkflowGraphTemplate.status == WorkflowGraphTemplateStatus.ACTIVE)

    rows = await self._session.execute(statement)
    summaries: list[TaskTemplateSummary] = []
    for template, node_count in rows.all():
      template_config = template.config if isinstance(template.config, dict) else {}
      run_kind = template_config.get("run_kind")
      category = str(run_kind) if run_kind else template.base_code
      summaries.append(
        TaskTemplateSummary(
          id=template.id,
          name=template.name,
          category=category,
          is_active=template.status == WorkflowGraphTemplateStatus.ACTIVE,
          step_count=int(node_count or 0),
        )
      )
    return summaries

  async def get_task_center(self, *, actor: User) -> TaskCenterSnapshot:
    ensure_active_user(actor)
    can_manage_templates = await can_manage_task_templates(self._session, actor)
    can_publish_task = await can_publish_org_tasks(self._session, actor)
    publish_department_options = await self._list_publish_department_options(actor=actor)
    publish_user_options = await self._list_publish_user_options(
      actor=actor,
      department_options=publish_department_options,
    )

    task_inbox_page = await self._task_service.list_task_inbox(actor=actor, limit=50)

    return TaskCenterSnapshot(
      permissions={
        "can_manage_templates": can_manage_templates,
        "can_publish_task": can_publish_task,
      },
      template_summaries=await self._build_template_summaries(actor=actor),
      publish_department_options=publish_department_options,
      publish_user_options=publish_user_options,
      task_inbox=task_inbox_page.items,
      inbox_next_cursor=task_inbox_page.next_cursor,
      inbox_has_more=task_inbox_page.has_more,
      task_tracking=(tracking_page := await self._task_service.list_task_tracking(
        actor=actor,
        limit=50,
        exclude_inbox_task_ids={item.task_id for item in task_inbox_page.items},
      )).items,
      tracking_next_cursor=tracking_page.next_cursor,
      tracking_has_more=tracking_page.has_more,
      task_history=(history_page := await self._task_service.list_task_history(actor=actor, limit=50)).items,
      history_next_cursor=history_page.next_cursor,
      history_has_more=history_page.has_more,
      task_memos=await self._task_memo_service.list_memos(actor=actor),
    )

  async def list_task_inbox_page(
    self,
    *,
    actor: User,
    limit: int = 50,
    cursor: UUID | None = None,
  ) -> TaskCenterListPage[TaskInboxEntry]:
    ensure_active_user(actor)
    return await self._task_service.list_task_inbox(
      actor=actor,
      limit=limit,
      after_task_id=cursor,
    )

  async def list_task_tracking_page(
    self,
    *,
    actor: User,
    limit: int = 50,
    cursor: UUID | None = None,
  ) -> TaskCenterListPage[TaskTrackingEntry]:
    ensure_active_user(actor)
    inbox_page = await self._task_service.list_task_inbox(actor=actor, limit=limit)
    return await self._task_service.list_task_tracking(
      actor=actor,
      limit=limit,
      exclude_inbox_task_ids={item.task_id for item in inbox_page.items},
      after_task_id=cursor,
    )

  async def list_task_history_page(
    self,
    *,
    actor: User,
    limit: int = 50,
    cursor: UUID | None = None,
  ) -> TaskCenterListPage[TaskHistoryEntry]:
    ensure_active_user(actor)
    return await self._task_service.list_task_history(
      actor=actor,
      limit=limit,
      after_task_id=cursor,
    )
