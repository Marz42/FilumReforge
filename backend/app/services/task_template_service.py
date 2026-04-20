from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import DEFAULT_USER_NOTIFICATION_CHANNELS, TaskPriority, TaskSourceType
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models import Task, TaskDependency, TaskTemplate, TaskTemplateStep, TaskTemplateStepDependency, TaskWatcher, User
from app.schemas.messages import NotificationMessage
from app.services.access_control import can_manage_task_templates, can_publish_org_tasks, ensure_active_user
from app.services.notification_service import NotificationService
from app.services.task_service import TaskService
from app.services.workflow_rule_resolver import (
  parse_uuid_value,
  resolve_actor_department_id,
  resolve_user_targets_from_rule,
)


class TaskTemplateService:
  def __init__(
    self,
    session: AsyncSession,
    task_service: TaskService,
    notification_service: NotificationService | None = None,
  ) -> None:
    self._session = session
    self._task_service = task_service
    self._notification_service = notification_service

  def _statement(self):
    return select(TaskTemplate).options(
      selectinload(TaskTemplate.creator),
      selectinload(TaskTemplate.steps)
      .selectinload(TaskTemplateStep.dependencies)
      .selectinload(TaskTemplateStepDependency.depends_on_step),
      selectinload(TaskTemplate.schedules),
    )

  async def _ensure_manage_templates(self, *, actor: User) -> None:
    if not await can_manage_task_templates(self._session, actor):
      raise AuthorizationError("当前账号不能管理任务模板。")

  async def _get_template_or_raise(self, *, actor: User, template_id: UUID) -> TaskTemplate:
    statement = self._statement().where(TaskTemplate.id == template_id)
    if not await can_manage_task_templates(self._session, actor):
      statement = statement.where(TaskTemplate.is_active.is_(True))
    template = await self._session.scalar(statement)
    if template is None:
      raise NotFoundError("任务模板不存在。")
    return template

  @staticmethod
  def _normalize_step_payloads(steps: list[dict[str, object]]) -> list[dict[str, object]]:
    if not steps:
      raise ConflictError("任务模板至少需要一个步骤。")
    return steps

  async def _replace_steps(
    self,
    *,
    template: TaskTemplate,
    steps: list[dict[str, object]],
  ) -> None:
    existing_steps = list(
      await self._session.scalars(
        select(TaskTemplateStep).where(TaskTemplateStep.template_id == template.id)
      )
    )
    for existing_step in existing_steps:
      await self._session.delete(existing_step)
    await self._session.flush()

    step_map: dict[str, TaskTemplateStep] = {}
    for index, step_payload in enumerate(self._normalize_step_payloads(steps), start=1):
      step_key = str(step_payload.get("step_key") or "").strip()
      title = str(step_payload.get("title") or "").strip()
      if not step_key or not title:
        raise ConflictError("模板步骤必须包含 step_key 和 title。")
      if step_key in step_map:
        raise ConflictError("模板步骤 step_key 不能重复。")

      step = TaskTemplateStep(
        template_id=template.id,
        step_key=step_key,
        title=title,
        description=str(step_payload.get("description") or "").strip() or None,
        step_type=str(step_payload.get("step_type") or "task"),
        default_assignee_rule=dict(step_payload.get("default_assignee_rule") or {"type": "initiator"}),
        default_due_offset_hours=(
          int(step_payload["default_due_offset_hours"])
          if step_payload.get("default_due_offset_hours") is not None
          else None
        ),
        sort_order=int(step_payload.get("sort_order") or index),
        config=dict(step_payload.get("config") or {}),
      )
      self._session.add(step)
      step_map[step_key] = step

    await self._session.flush()

    for step_payload in steps:
      step = step_map[str(step_payload["step_key"])]
      depends_on_step_keys = step_payload.get("depends_on_step_keys") or []
      if not isinstance(depends_on_step_keys, list):
        raise ConflictError("depends_on_step_keys 必须是数组。")
      for depends_on_step_key in dict.fromkeys(str(raw_key) for raw_key in depends_on_step_keys):
        depends_on_step = step_map.get(depends_on_step_key)
        if depends_on_step is None:
          raise ConflictError("模板步骤依赖引用了不存在的步骤。")
        self._session.add(
          TaskTemplateStepDependency(
            step_id=step.id,
            depends_on_step_id=depends_on_step.id,
            dependency_type="blocks",
          )
        )

  async def list_templates(self, *, actor: User) -> list[TaskTemplate]:
    ensure_active_user(actor)
    statement = self._statement().order_by(TaskTemplate.updated_at.desc())
    if not await can_manage_task_templates(self._session, actor):
      statement = statement.where(TaskTemplate.is_active.is_(True))
    return list(await self._session.scalars(statement))

  async def get_template(self, *, actor: User, template_id: UUID) -> TaskTemplate:
    ensure_active_user(actor)
    return await self._get_template_or_raise(actor=actor, template_id=template_id)

  async def create_template(
    self,
    *,
    actor: User,
    code: str,
    name: str,
    category: str,
    description: str | None = None,
    trigger_type: str = "manual",
    config: dict[str, object] | None = None,
    is_active: bool = True,
    steps: list[dict[str, object]],
  ) -> TaskTemplate:
    ensure_active_user(actor)
    await self._ensure_manage_templates(actor=actor)

    if await self._session.scalar(select(TaskTemplate.id).where(TaskTemplate.code == code)) is not None:
      raise ConflictError("任务模板编码已存在。")

    template = TaskTemplate(
      code=code.strip(),
      name=name.strip(),
      category=category.strip(),
      description=description.strip() if description else None,
      trigger_type=trigger_type.strip(),
      config=dict(config or {}),
      is_active=is_active,
      created_by=actor.id,
    )
    self._session.add(template)
    await self._session.flush()
    await self._replace_steps(template=template, steps=steps)
    await self._session.commit()
    return await self.get_template(actor=actor, template_id=template.id)

  async def update_template(
    self,
    *,
    actor: User,
    template_id: UUID,
    code: str | None = None,
    name: str | None = None,
    category: str | None = None,
    description: str | None = None,
    trigger_type: str | None = None,
    config: dict[str, object] | None = None,
    is_active: bool | None = None,
    steps: list[dict[str, object]] | None = None,
  ) -> TaskTemplate:
    ensure_active_user(actor)
    await self._ensure_manage_templates(actor=actor)
    template = await self._get_template_or_raise(actor=actor, template_id=template_id)

    if code is not None and code.strip() != template.code:
      existing_template_id = await self._session.scalar(select(TaskTemplate.id).where(TaskTemplate.code == code.strip()))
      if existing_template_id is not None and existing_template_id != template.id:
        raise ConflictError("任务模板编码已存在。")
      template.code = code.strip()
    if name is not None:
      template.name = name.strip()
    if category is not None:
      template.category = category.strip()
    if description is not None:
      template.description = description.strip() or None
    if trigger_type is not None:
      template.trigger_type = trigger_type.strip()
    if config is not None:
      template.config = dict(config)
    if is_active is not None:
      template.is_active = is_active
    if steps is not None:
      await self._replace_steps(template=template, steps=steps)

    template.updated_at = datetime.now(UTC)
    await self._session.commit()
    return await self.get_template(actor=actor, template_id=template.id)

  async def instantiate_template(
    self,
    *,
    actor: User,
    template_id: UUID,
    department_id: UUID | None = None,
    watcher_user_ids: list[UUID] | None = None,
    payload: dict[str, object] | None = None,
  ) -> list[Task]:
    ensure_active_user(actor)
    if not await can_publish_org_tasks(self._session, actor):
      raise AuthorizationError("当前账号不能发布模板任务。")
    template = await self._get_template_or_raise(actor=actor, template_id=template_id)
    if not template.is_active:
      raise ConflictError("任务模板未启用，不能实例化。")
    if not template.steps:
      raise ConflictError("任务模板没有可执行步骤。")

    payload_dict = dict(payload or {})
    payload_department_id = payload_dict.get("department_id")
    resolved_department_id = await resolve_actor_department_id(
      self._session,
      actor_id=actor.id,
      requested_department_id=(
        parse_uuid_value(payload_department_id, field_name="department_id")
        if payload_department_id is not None
        else department_id
      ),
    )

    raw_watcher_user_ids = payload_dict.get("watcher_user_ids") if watcher_user_ids is None else watcher_user_ids
    watcher_ids = [
      parse_uuid_value(raw_user_id, field_name="watcher_user_ids")
      for raw_user_id in (raw_watcher_user_ids or [])
    ]
    watcher_users = (
      await resolve_user_targets_from_rule(
        self._session,
        actor=actor,
        assignee_rule={"type": "user_ids", "user_ids": [str(user_id) for user_id in watcher_ids]},
        department_id=resolved_department_id,
        allow_multiple=True,
      )
      if watcher_ids
      else []
    )
    assignee_overrides = payload_dict.get("assignee_overrides")
    if assignee_overrides is not None and not isinstance(assignee_overrides, dict):
      raise ConflictError("assignee_overrides 必须是对象。")

    created_tasks: list[tuple[Task, User]] = []
    task_by_step_key: dict[str, Task] = {}
    now = datetime.now(UTC)
    for step in sorted(template.steps, key=lambda current_step: (current_step.sort_order, current_step.created_at)):
      override_rule = assignee_overrides.get(step.step_key) if isinstance(assignee_overrides, dict) else None
      assignees = await resolve_user_targets_from_rule(
        self._session,
        actor=actor,
        assignee_rule=dict(override_rule) if isinstance(override_rule, dict) else step.default_assignee_rule,
        department_id=resolved_department_id,
        allow_multiple=False,
      )
      assignee = assignees[0]
      due_date = (
        now + timedelta(hours=step.default_due_offset_hours)
        if step.default_due_offset_hours is not None
        else None
      )
      task_title = f"{template.name} / {step.title}"
      task_description = "\n\n".join(
        value for value in [template.description, step.description] if value
      ) or None
      task, resolved_assignee = await self._task_service.create_task_record(
        actor=actor,
        title=task_title,
        assignee_id=assignee.id,
        description=task_description,
        department_id=resolved_department_id,
        due_date=due_date,
        priority=TaskPriority(str(step.config.get("priority") or TaskPriority.MEDIUM)),
        source_type=TaskSourceType.TEMPLATE,
        extra_metadata={
          "template_id": str(template.id),
          "template_code": template.code,
          "template_step_id": str(step.id),
          "template_step_key": step.step_key,
          "template_step_type": step.step_type,
          "instantiation_payload": payload_dict,
        },
        commit=False,
        skip_assignee_permission=True,
      )
      created_tasks.append((task, resolved_assignee))
      task_by_step_key[step.step_key] = task

    for step in template.steps:
      task = task_by_step_key[step.step_key]
      for dependency in step.dependencies:
        depends_on_task = task_by_step_key.get(dependency.depends_on_step.step_key)
        if depends_on_task is None:
          raise ConflictError("模板依赖缺少对应任务实例。")
        self._session.add(
          TaskDependency(
            task_id=task.id,
            depends_on_task_id=depends_on_task.id,
          )
        )

    watcher_bindings: list[tuple[Task, User]] = []
    for task, _ in created_tasks:
      for watcher_user in watcher_users:
        if watcher_user.id == task.assignee_id:
          continue
        self._session.add(
          TaskWatcher(
            task_id=task.id,
            user_id=watcher_user.id,
            relation="cc",
            created_by=actor.id,
          )
        )
        watcher_bindings.append((task, watcher_user))

    await self._session.commit()

    for task, assignee in created_tasks:
      await self._task_service._send_assignment_notification(task=task, assignee=assignee)

    if self._notification_service is not None:
      for task, watcher_user in watcher_bindings:
        await self._notification_service.send(
          NotificationMessage(
            source_type="task",
            source_id=task.id,
            recipient_user_id=watcher_user.id,
            recipient_email=watcher_user.email,
            message_type="task_cc_added",
            title=f"你被加入任务关注：{task.title}",
            body_text=f"任务「{task.title}」由模板实例化，并已将你加入关注列表。",
            channels=list(DEFAULT_USER_NOTIFICATION_CHANNELS),
          )
        )

    task_ids = [task.id for task, _ in created_tasks]
    if not task_ids:
      return []
    tasks = list(
      await self._session.scalars(
        select(Task)
        .options(
          selectinload(Task.creator),
          selectinload(Task.assignee),
          selectinload(Task.department),
          selectinload(Task.watchers).selectinload(TaskWatcher.user),
        )
        .where(Task.id.in_(task_ids))
      )
    )
    task_order = {task_id: index for index, task_id in enumerate(task_ids)}
    return sorted(tasks, key=lambda task: task_order[task.id])
