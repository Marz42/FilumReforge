from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
  AttachmentTargetType,
  AttachmentVisibility,
  CommentFormat,
  NotificationChannel,
  TaskActionType,
  TaskPriority,
  TaskSourceType,
  TaskStatus,
)
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models import Department, Profile, Task, TaskComment, TaskDependency, TaskLog, TaskWatcher, User
from app.schemas.messages import NotificationMessage
from app.services.access_control import (
  MANAGEMENT_ROLES,
  can_manage_assignee,
  ensure_active_user,
  get_managed_department_ids,
)
from app.services.notification_service import NotificationService


@dataclass(slots=True)
class CommentAttachmentInput:
  filename: str
  content_type: str
  content: bytes
  visibility: AttachmentVisibility = AttachmentVisibility.PRIVATE


@dataclass(slots=True)
class TaskActivityEntry:
  entry_type: str
  created_at: datetime
  comment: TaskComment | None = None
  log: TaskLog | None = None


@dataclass(slots=True)
class TaskStatsSummary:
  total_tasks: int
  completed_tasks: int
  completion_rate: float
  overdue_tasks: int
  overdue_rate: float
  tasks_by_status: dict[TaskStatus, int]


@dataclass(slots=True)
class TaskWorkloadEntry:
  assignee_id: UUID
  assignee_email: str
  department_id: UUID | None
  department_name: str | None
  total_tasks: int
  open_tasks: int
  completed_tasks: int
  overdue_tasks: int


@dataclass(slots=True)
class TaskBoardColumn:
  status: TaskStatus
  tasks: list[Task]


@dataclass(slots=True)
class TaskGanttEntry:
  task: Task
  dependency_ids: list[UUID]


ALLOWED_TASK_STATUS_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
  TaskStatus.TODO: {TaskStatus.DOING},
  TaskStatus.DOING: {TaskStatus.REVIEW},
  TaskStatus.REVIEW: {TaskStatus.DONE},
  TaskStatus.DONE: set(),
}


def _serialize_datetime(value: datetime | None) -> str | None:
  if value is None:
    return None
  return _normalize_datetime(value).isoformat()


def _normalize_datetime(value: datetime) -> datetime:
  if value.tzinfo is None:
    return value.replace(tzinfo=UTC)
  return value.astimezone(UTC)


def _is_overdue(*, due_date: datetime | None, now: datetime) -> bool:
  if due_date is None:
    return False
  return _normalize_datetime(due_date) < now


class TaskService:
  def __init__(
    self,
    session: AsyncSession,
    notification_service: NotificationService | None = None,
    attachment_service=None,  # noqa: ANN001
  ) -> None:
    self._session = session
    self._notification_service = notification_service
    self._attachment_service = attachment_service

  async def _resolve_assignee_for_task(
    self,
    *,
    actor: User,
    assignee_id: UUID,
    skip_assignee_permission: bool = False,
  ) -> User:
    assignee = await self._session.get(User, assignee_id)
    if assignee is None:
      raise NotFoundError("执行人不存在。")
    ensure_active_user(assignee)
    if not skip_assignee_permission and not await can_manage_assignee(self._session, actor, assignee_id):
      raise AuthorizationError("当前账号不能为该执行人创建任务。")
    return assignee

  async def _resolve_task_department_id(
    self,
    *,
    assignee_id: UUID,
    department_id: UUID | None,
  ) -> UUID | None:
    if department_id is None:
      return await self._session.scalar(
        select(Profile.department_id).where(Profile.user_id == assignee_id)
      )

    if await self._session.get(Department, department_id) is None:
      raise NotFoundError("所属部门不存在。")
    return department_id

  async def _send_assignment_notification(self, *, task: Task, assignee: User) -> None:
    if self._notification_service is None:
      return

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

  async def create_task_record(
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
    source_type: TaskSourceType = TaskSourceType.MANUAL,
    extra_metadata: dict[str, object] | None = None,
    commit: bool = False,
    skip_assignee_permission: bool = False,
  ) -> tuple[Task, User]:
    ensure_active_user(actor)

    assignee = await self._resolve_assignee_for_task(
      actor=actor,
      assignee_id=assignee_id,
      skip_assignee_permission=skip_assignee_permission,
    )
    resolved_department_id = await self._resolve_task_department_id(
      assignee_id=assignee_id,
      department_id=department_id,
    )

    task = Task(
      title=title,
      description=description,
      creator_id=actor.id,
      assignee_id=assignee_id,
      department_id=resolved_department_id,
      due_date=due_date,
      priority=priority,
      source_type=source_type,
      extra_metadata=extra_metadata or {},
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

    await self._create_task_log(
      task_id=task.id,
      operator_id=actor.id,
      action_type=TaskActionType.CREATED,
      detail={
        "assignee_id": str(assignee_id),
        "priority": priority.value,
        "source_type": source_type.value,
        "dependency_ids": [str(dependency_id) for dependency_id in dependency_ids or []],
      },
    )
    await self._create_task_log(
      task_id=task.id,
      operator_id=actor.id,
      action_type=TaskActionType.ASSIGNED,
      detail={
        "assignee_id": str(assignee_id),
      },
    )

    if commit:
      await self._session.commit()
      await self._session.refresh(task)
      await self._send_assignment_notification(task=task, assignee=assignee)

    return task, assignee

  async def _build_visible_task_statement(self, *, actor: User):
    statement = (
      select(Task)
      .options(
        selectinload(Task.creator),
        selectinload(Task.assignee),
        selectinload(Task.department),
      )
      .order_by(Task.created_at.desc())
    )
    if actor.role in MANAGEMENT_ROLES:
      return statement

    managed_department_ids = await get_managed_department_ids(self._session, actor.id)
    filters = [Task.creator_id == actor.id, Task.assignee_id == actor.id]
    if managed_department_ids:
      filters.append(Task.department_id.in_(managed_department_ids))
    return statement.where(or_(*filters))

  async def _create_task_log(
    self,
    *,
    task_id: UUID,
    operator_id: UUID,
    action_type: TaskActionType,
    from_status: TaskStatus | None = None,
    to_status: TaskStatus | None = None,
    detail: dict[str, object] | None = None,
  ) -> TaskLog:
    log = TaskLog(
      task_id=task_id,
      operator_id=operator_id,
      action_type=action_type,
      from_status=from_status,
      to_status=to_status,
      detail=detail or {},
    )
    self._session.add(log)
    await self._session.flush()
    return log

  async def _load_task_comment(self, comment_id: UUID) -> TaskComment:
    comment = await self._session.scalar(
      select(TaskComment)
      .options(selectinload(TaskComment.user))
      .where(TaskComment.id == comment_id)
    )
    if comment is None:
      raise NotFoundError("任务评论不存在。")
    return comment

  async def _can_operate_task(self, *, actor: User, task: Task) -> bool:
    if actor.role in MANAGEMENT_ROLES or actor.id in {task.creator_id, task.assignee_id}:
      return True
    if task.department_id is None:
      return False
    managed_department_ids = await get_managed_department_ids(self._session, actor.id)
    return task.department_id in managed_department_ids

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
    task, _ = await self.create_task_record(
      actor=actor,
      title=title,
      assignee_id=assignee_id,
      description=description,
      department_id=department_id,
      due_date=due_date,
      priority=priority,
      dependency_ids=dependency_ids,
      source_type=TaskSourceType.MANUAL,
      commit=True,
    )
    return task

  async def list_tasks(self, *, actor: User) -> list[Task]:
    ensure_active_user(actor)

    statement = await self._build_visible_task_statement(actor=actor)
    result = await self._session.scalars(statement)
    return list(result)

  async def get_task(self, *, actor: User, task_id: UUID) -> Task:
    ensure_active_user(actor)

    statement = (await self._build_visible_task_statement(actor=actor)).where(Task.id == task_id)
    task = await self._session.scalar(statement)
    if task is None:
      raise NotFoundError("任务不存在。")
    return task

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
    previous_due_date = task.due_date

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
    if assignee_id is not None and assignee_id != previous_assignee_id:
      await self._create_task_log(
        task_id=task.id,
        operator_id=actor.id,
        action_type=TaskActionType.ASSIGNED,
        detail={
          "previous_assignee_id": str(previous_assignee_id),
          "assignee_id": str(assignee_id),
        },
      )
    if due_date is not None and due_date != previous_due_date:
      await self._create_task_log(
        task_id=task.id,
        operator_id=actor.id,
        action_type=TaskActionType.DUE_DATE_CHANGED,
        detail={
          "previous_due_date": _serialize_datetime(previous_due_date),
          "due_date": _serialize_datetime(due_date),
        },
      )

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

  async def transition_task_status(
    self,
    *,
    actor: User,
    task_id: UUID,
    target_status: TaskStatus,
  ) -> Task:
    task = await self.get_task(actor=actor, task_id=task_id)

    if not await self._can_operate_task(actor=actor, task=task):
      raise AuthorizationError("当前账号不能变更该任务状态。")

    if target_status == task.status:
      raise ConflictError("任务已处于目标状态。")

    allowed_statuses = ALLOWED_TASK_STATUS_TRANSITIONS[task.status]
    if target_status not in allowed_statuses:
      raise ConflictError("不支持的任务状态流转。")

    previous_status = task.status
    now = datetime.now(UTC)
    task.status = target_status
    task.updated_at = now
    if target_status == TaskStatus.DOING and task.started_at is None:
      task.started_at = now
    if target_status == TaskStatus.DONE:
      task.completed_at = now

    await self._create_task_log(
      task_id=task.id,
      operator_id=actor.id,
      action_type=TaskActionType.STATUS_CHANGED,
      from_status=previous_status,
      to_status=target_status,
      detail={
        "previous_status": previous_status.value,
        "status": target_status.value,
      },
    )
    await self._session.commit()
    await self._session.refresh(task)
    return task

  async def create_task_comment(
    self,
    *,
    actor: User,
    task_id: UUID,
    content: str,
    content_format: CommentFormat = CommentFormat.MARKDOWN,
    is_internal: bool = False,
    attachments: list[CommentAttachmentInput] | None = None,
  ) -> TaskComment:
    task = await self.get_task(actor=actor, task_id=task_id)

    if not await self._can_operate_task(actor=actor, task=task):
      raise AuthorizationError("当前账号不能在该任务下评论。")
    if not content.strip():
      raise ConflictError("评论内容不能为空。")
    if is_internal and actor.role not in MANAGEMENT_ROLES:
      raise AuthorizationError("当前账号不能创建内部备注。")
    if attachments and self._attachment_service is None:
      raise ConflictError("附件服务未配置，无法上传评论附件。")

    comment = TaskComment(
      task_id=task.id,
      user_id=actor.id,
      content=content,
      content_format=content_format,
      is_internal=is_internal,
    )
    self._session.add(comment)
    await self._session.flush()
    await self._create_task_log(
      task_id=task.id,
      operator_id=actor.id,
      action_type=TaskActionType.COMMENTED,
      detail={
        "comment_id": str(comment.id),
        "content_format": content_format.value,
        "is_internal": is_internal,
      },
    )

    if not attachments:
      await self._session.commit()
      return await self._load_task_comment(comment.id)

    for attachment_input in attachments:
      attachment = await self._attachment_service.upload_attachment(
        actor=actor,
        filename=attachment_input.filename,
        content_type=attachment_input.content_type,
        content=attachment_input.content,
        visibility=attachment_input.visibility,
        target_type=AttachmentTargetType.TASK_COMMENT,
        target_id=comment.id,
        relation="comment_attachment",
      )
      await self._create_task_log(
        task_id=task.id,
        operator_id=actor.id,
        action_type=TaskActionType.ATTACHMENT_ADDED,
        detail={
          "comment_id": str(comment.id),
          "attachment_id": str(attachment.id),
          "filename": attachment.original_filename,
        },
      )
      await self._session.commit()

    return await self._load_task_comment(comment.id)

  async def list_task_comments(self, *, actor: User, task_id: UUID) -> list[TaskComment]:
    await self.get_task(actor=actor, task_id=task_id)

    statement = (
      select(TaskComment)
      .options(selectinload(TaskComment.user))
      .where(TaskComment.task_id == task_id)
      .order_by(TaskComment.created_at.asc())
    )
    if actor.role not in MANAGEMENT_ROLES:
      statement = statement.where(TaskComment.is_internal.is_(False))

    result = await self._session.scalars(statement)
    return list(result)

  async def list_task_logs(self, *, actor: User, task_id: UUID) -> list[TaskLog]:
    await self.get_task(actor=actor, task_id=task_id)

    result = await self._session.scalars(
      select(TaskLog)
      .where(TaskLog.task_id == task_id)
      .order_by(TaskLog.created_at.asc())
    )
    return list(result)

  async def list_task_activity(self, *, actor: User, task_id: UUID) -> list[TaskActivityEntry]:
    comments = await self.list_task_comments(actor=actor, task_id=task_id)
    logs = await self.list_task_logs(actor=actor, task_id=task_id)

    activity = [
      *(
        TaskActivityEntry(entry_type="comment", created_at=comment.created_at, comment=comment)
        for comment in comments
      ),
      *(
        TaskActivityEntry(entry_type="log", created_at=log.created_at, log=log)
        for log in logs
      ),
    ]
    activity.sort(key=lambda entry: (_normalize_datetime(entry.created_at), entry.entry_type))
    return activity

  async def list_task_watchers(self, *, actor: User, task_id: UUID) -> list[TaskWatcher]:
    task = await self.get_task(actor=actor, task_id=task_id)
    if not await self._can_operate_task(actor=actor, task=task):
      raise AuthorizationError("当前账号不能查看该任务关注人。")

    result = await self._session.scalars(
      select(TaskWatcher)
      .options(selectinload(TaskWatcher.user), selectinload(TaskWatcher.creator))
      .where(TaskWatcher.task_id == task_id)
      .order_by(TaskWatcher.created_at.asc())
    )
    return list(result)

  async def add_task_watchers(
    self,
    *,
    actor: User,
    task_id: UUID,
    watcher_user_ids: list[UUID],
    relation: str = "cc",
  ) -> list[TaskWatcher]:
    task = await self.get_task(actor=actor, task_id=task_id)
    if not await self._can_operate_task(actor=actor, task=task):
      raise AuthorizationError("当前账号不能为该任务添加关注人。")

    unique_user_ids = list(dict.fromkeys(watcher_user_ids))
    existing_bindings = {
      watcher.user_id
      for watcher in await self.list_task_watchers(actor=actor, task_id=task_id)
      if watcher.relation == relation
    }

    added_watchers: list[tuple[TaskWatcher, User]] = []
    for watcher_user_id in unique_user_ids:
      if watcher_user_id in existing_bindings:
        continue
      watcher_user = await self._session.get(User, watcher_user_id)
      if watcher_user is None:
        raise NotFoundError("关注人不存在。")
      ensure_active_user(watcher_user)
      watcher = TaskWatcher(
        task_id=task.id,
        user_id=watcher_user_id,
        relation=relation,
        created_by=actor.id,
      )
      self._session.add(watcher)
      added_watchers.append((watcher, watcher_user))

    await self._session.commit()

    if self._notification_service is not None:
      for _, watcher_user in added_watchers:
        if watcher_user.id == actor.id:
          continue
        await self._notification_service.send(
          NotificationMessage(
            source_type="task",
            source_id=task.id,
            recipient_user_id=watcher_user.id,
            recipient_email=watcher_user.email,
            message_type="task_cc_added",
            title=f"你被加入任务关注：{task.title}",
            body_text=f"任务「{task.title}」已将你加入关注列表。",
            channels=[NotificationChannel.WEBSOCKET, NotificationChannel.EMAIL],
          )
        )

    return await self.list_task_watchers(actor=actor, task_id=task_id)

  async def remove_task_watcher(
    self,
    *,
    actor: User,
    task_id: UUID,
    watcher_id: UUID,
  ) -> None:
    task = await self.get_task(actor=actor, task_id=task_id)
    if not await self._can_operate_task(actor=actor, task=task):
      raise AuthorizationError("当前账号不能移除该任务关注人。")

    watcher = await self._session.get(TaskWatcher, watcher_id)
    if watcher is None or watcher.task_id != task.id:
      raise NotFoundError("关注关系不存在。")
    await self._session.delete(watcher)
    await self._session.commit()

  async def list_overdue_tasks(self) -> list[Task]:
    result = await self._session.scalars(
      select(Task)
      .options(
        selectinload(Task.assignee),
        selectinload(Task.department).selectinload(Department.manager),
      )
      .where(
        Task.due_date.is_not(None),
        Task.due_date < datetime.now(UTC),
        Task.status != TaskStatus.DONE,
      )
      .order_by(Task.due_date.asc())
    )
    return list(result)

  async def get_task_stats_summary(self, *, actor: User) -> TaskStatsSummary:
    tasks = await self.list_tasks(actor=actor)
    now = datetime.now(UTC)
    total_tasks = len(tasks)
    completed_tasks = sum(task.status == TaskStatus.DONE for task in tasks)
    overdue_tasks = sum(
      _is_overdue(due_date=task.due_date, now=now) and task.status != TaskStatus.DONE
      for task in tasks
    )
    tasks_by_status = {status: 0 for status in TaskStatus}
    for task in tasks:
      tasks_by_status[task.status] += 1

    completion_rate = round(completed_tasks / total_tasks, 4) if total_tasks else 0.0
    overdue_rate = round(overdue_tasks / total_tasks, 4) if total_tasks else 0.0
    return TaskStatsSummary(
      total_tasks=total_tasks,
      completed_tasks=completed_tasks,
      completion_rate=completion_rate,
      overdue_tasks=overdue_tasks,
      overdue_rate=overdue_rate,
      tasks_by_status=tasks_by_status,
    )

  async def get_task_workload(self, *, actor: User) -> list[TaskWorkloadEntry]:
    tasks = await self.list_tasks(actor=actor)
    now = datetime.now(UTC)

    workload_map: dict[tuple[UUID, UUID | None], TaskWorkloadEntry] = {}
    for task in tasks:
      assignee = task.assignee
      if assignee is None:
        continue
      key = (assignee.id, task.department_id)
      workload = workload_map.get(key)
      if workload is None:
        workload = TaskWorkloadEntry(
          assignee_id=assignee.id,
          assignee_email=assignee.email,
          department_id=task.department_id,
          department_name=task.department.name if task.department is not None else None,
          total_tasks=0,
          open_tasks=0,
          completed_tasks=0,
          overdue_tasks=0,
        )
        workload_map[key] = workload

      workload.total_tasks += 1
      if task.status == TaskStatus.DONE:
        workload.completed_tasks += 1
      else:
        workload.open_tasks += 1
      if _is_overdue(due_date=task.due_date, now=now) and task.status != TaskStatus.DONE:
        workload.overdue_tasks += 1

    return sorted(
      workload_map.values(),
      key=lambda row: (row.department_name or "", row.assignee_email),
    )

  async def get_task_board(self, *, actor: User) -> list[TaskBoardColumn]:
    tasks = await self.list_tasks(actor=actor)
    grouped: dict[TaskStatus, list[Task]] = {status: [] for status in TaskStatus}
    for task in tasks:
      grouped[task.status].append(task)
    return [TaskBoardColumn(status=status, tasks=grouped[status]) for status in TaskStatus]

  async def get_task_gantt(self, *, actor: User) -> list[TaskGanttEntry]:
    tasks = await self.list_tasks(actor=actor)
    task_ids = [task.id for task in tasks]
    dependency_rows = list(
      await self._session.scalars(
        select(TaskDependency).where(TaskDependency.task_id.in_(task_ids))
      )
    ) if task_ids else []
    dependency_map: dict[UUID, list[UUID]] = {task.id: [] for task in tasks}
    for dependency in dependency_rows:
      dependency_map.setdefault(dependency.task_id, []).append(dependency.depends_on_task_id)

    sorted_tasks = sorted(
      tasks,
      key=lambda task: (
        _normalize_datetime(task.due_date) if task.due_date is not None else datetime.max.replace(tzinfo=UTC),
        _normalize_datetime(task.created_at),
      ),
    )
    return [
      TaskGanttEntry(task=task, dependency_ids=dependency_map.get(task.id, []))
      for task in sorted_tasks
    ]
