from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import NotificationChannel, TaskPriority, TaskSourceType, UserRole
from app.core.exceptions import AuthorizationError, NotFoundError
from app.models import Department, Profile, Task, TaskDependency, User
from app.schemas.messages import NotificationMessage
from app.services.access_control import can_manage_assignee, ensure_active_user, get_managed_department_ids
from app.services.notification_service import NotificationService


class TaskService:
  def __init__(
    self,
    session: AsyncSession,
    notification_service: NotificationService | None = None,
  ) -> None:
    self._session = session
    self._notification_service = notification_service

  async def create_task(
    self,
    *,
    actor: User,
    title: str,
    assignee_id: UUID,
    description: str | None = None,
    department_id: UUID | None = None,
    due_date: datetime | None = None,
    priority: TaskPriority = TaskPriority.MEDIUM,
    dependency_ids: list[UUID] | None = None,
  ) -> Task:
    ensure_active_user(actor)

    assignee = await self._session.get(User, assignee_id)
    if assignee is None:
      raise NotFoundError("执行人不存在。")

    if not await can_manage_assignee(self._session, actor, assignee_id):
      raise AuthorizationError("当前账号不能为该执行人创建任务。")

    if department_id is None:
      department_id = await self._session.scalar(
        select(Profile.department_id).where(Profile.user_id == assignee_id)
      )
    elif await self._session.get(Department, department_id) is None:
      raise NotFoundError("所属部门不存在。")

    task = Task(
      title=title,
      description=description,
      creator_id=actor.id,
      assignee_id=assignee_id,
      department_id=department_id,
      due_date=due_date,
      priority=priority,
      source_type=TaskSourceType.MANUAL,
    )
    self._session.add(task)
    await self._session.flush()

    if dependency_ids:
      dependency_task_ids = set(await self._session.scalars(select(Task.id).where(Task.id.in_(dependency_ids))))
      if dependency_task_ids != set(dependency_ids):
        raise NotFoundError("存在无效的前置任务。")
      for dependency_id in dependency_ids:
        self._session.add(
          TaskDependency(
            task_id=task.id,
            depends_on_task_id=dependency_id,
          )
        )

    await self._session.commit()
    await self._session.refresh(task)

    if self._notification_service is not None:
      await self._notification_service.send(
        NotificationMessage(
          source_type="task",
          source_id=task.id,
          recipient_user_id=assignee.id,
          recipient_email=assignee.email,
          message_type="task_assigned",
          title=f"收到新任务：{task.title}",
          body_text=f"任务「{task.title}」已分配给你，请及时处理。",
          channels=[NotificationChannel.WEBSOCKET, NotificationChannel.EMAIL],
        )
      )

    return task

  async def list_tasks(self, *, actor: User) -> list[Task]:
    ensure_active_user(actor)

    statement = (
      select(Task)
      .options(
        selectinload(Task.creator),
        selectinload(Task.assignee),
        selectinload(Task.department),
      )
      .order_by(Task.created_at.desc())
    )
    if actor.role not in {UserRole.ADMIN, UserRole.HR}:
      managed_department_ids = await get_managed_department_ids(self._session, actor.id)
      filters = [Task.creator_id == actor.id, Task.assignee_id == actor.id]
      if managed_department_ids:
        filters.append(Task.department_id.in_(managed_department_ids))
      statement = statement.where(or_(*filters))

    result = await self._session.scalars(statement)
    return list(result)

  async def get_task(self, *, actor: User, task_id: UUID) -> Task:
    tasks = await self.list_tasks(actor=actor)
    for task in tasks:
      if task.id == task_id:
        return task
    raise NotFoundError("任务不存在。")

  async def update_task(
    self,
    *,
    actor: User,
    task_id: UUID,
    title: str | None = None,
    description: str | None = None,
    assignee_id: UUID | None = None,
    department_id: UUID | None = None,
    due_date: datetime | None = None,
    priority: TaskPriority | None = None,
  ) -> Task:
    task = await self.get_task(actor=actor, task_id=task_id)

    previous_assignee_id = task.assignee_id

    if title is not None:
      task.title = title
    if description is not None:
      task.description = description
    if assignee_id is not None:
      assignee = await self._session.get(User, assignee_id)
      if assignee is None:
        raise NotFoundError("执行人不存在。")
      if not await can_manage_assignee(self._session, actor, assignee_id):
        raise AuthorizationError("当前账号不能变更为该执行人。")
      task.assignee_id = assignee_id
    if department_id is not None:
      department = await self._session.get(Department, department_id)
      if department is None:
        raise NotFoundError("所属部门不存在。")
      task.department_id = department_id
    if due_date is not None:
      task.due_date = due_date
    if priority is not None:
      task.priority = priority

    task.updated_at = datetime.now(UTC)
    await self._session.commit()
    await self._session.refresh(task)

    if assignee_id is not None and assignee_id != previous_assignee_id and self._notification_service is not None:
      assignee = await self._session.get(User, assignee_id)
      if assignee is not None:
        await self._notification_service.send(
          NotificationMessage(
            source_type="task",
            source_id=task.id,
            recipient_user_id=assignee.id,
            recipient_email=assignee.email,
            message_type="task_reassigned",
            title=f"任务已重新分配：{task.title}",
            body_text=f"任务「{task.title}」已重新分配给你。",
            channels=[NotificationChannel.WEBSOCKET, NotificationChannel.EMAIL],
          )
        )

    return task
