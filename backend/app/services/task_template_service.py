from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import TaskPriority
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models import (
  Task,
  TaskTemplate,
  TaskTemplateInstance,
  TaskTemplateStep,
  TaskTemplateStepDependency,
  TaskTemplateStepRun,
  User,
)
from app.services.access_control import can_manage_task_templates, can_publish_org_tasks, ensure_active_user
from app.services.notification_service import NotificationService
from app.services.task_service import TaskService
from app.services.workflow_rule_resolver import (
  parse_uuid_value,
  resolve_actor_department_id,
  resolve_user_targets_from_rule,
)


@dataclass(slots=True)
class TaskTemplateInstantiationResult:
  instance: TaskTemplateInstance
  tasks: list[Task]


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

  def _instance_statement(self):
    return select(TaskTemplateInstance).options(
      selectinload(TaskTemplateInstance.initiator),
      selectinload(TaskTemplateInstance.department),
      selectinload(TaskTemplateInstance.template)
      .selectinload(TaskTemplate.steps)
      .selectinload(TaskTemplateStep.dependencies)
      .selectinload(TaskTemplateStepDependency.depends_on_step),
      selectinload(TaskTemplateInstance.step_runs).selectinload(TaskTemplateStepRun.assignee),
      selectinload(TaskTemplateInstance.step_runs).selectinload(TaskTemplateStepRun.task),
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
      assignment_mode = str(step_payload.get("assignment_mode") or "single").strip()
      join_mode = str(step_payload.get("join_mode") or "all").strip()
      if not step_key or not title:
        raise ConflictError("模板步骤必须包含 step_key 和 title。")
      if step_key in step_map:
        raise ConflictError("模板步骤 step_key 不能重复。")
      if assignment_mode not in {"single", "fan_out"}:
        raise ConflictError("assignment_mode 仅支持 single 或 fan_out。")
      if join_mode not in {"all", "any"}:
        raise ConflictError("join_mode 仅支持 all 或 any。")

      step = TaskTemplateStep(
        template_id=template.id,
        step_key=step_key,
        title=title,
        description=str(step_payload.get("description") or "").strip() or None,
        step_type=str(step_payload.get("step_type") or "task"),
        assignment_mode=assignment_mode,
        join_mode="all" if assignment_mode == "single" else join_mode,
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

  async def list_instances(
    self,
    *,
    actor: User,
    template_id: UUID,
    limit: int = 10,
  ) -> list[TaskTemplateInstance]:
    ensure_active_user(actor)
    await self._get_template_or_raise(actor=actor, template_id=template_id)

    normalized_limit = max(1, min(limit, 20))
    statement = (
      self._instance_statement()
      .where(TaskTemplateInstance.template_id == template_id)
      .order_by(TaskTemplateInstance.created_at.desc())
      .limit(normalized_limit)
    )
    if not await can_manage_task_templates(self._session, actor):
      statement = statement.where(TaskTemplateInstance.initiator_user_id == actor.id)
    return list(await self._session.scalars(statement))

  async def get_instance(
    self,
    *,
    actor: User,
    template_id: UUID,
    instance_id: UUID,
  ) -> TaskTemplateInstance:
    ensure_active_user(actor)
    await self._get_template_or_raise(actor=actor, template_id=template_id)

    statement = self._instance_statement().where(
      TaskTemplateInstance.id == instance_id,
      TaskTemplateInstance.template_id == template_id,
    )
    if not await can_manage_task_templates(self._session, actor):
      statement = statement.where(TaskTemplateInstance.initiator_user_id == actor.id)

    instance = await self._session.scalar(statement)
    if instance is None:
      raise NotFoundError("模板实例不存在。")
    return instance

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
  ) -> TaskTemplateInstantiationResult:
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

    instance_payload = dict(payload_dict)
    instance_payload["watcher_user_ids"] = [str(user.id) for user in watcher_users]
    if assignee_overrides is not None:
      instance_payload["assignee_overrides"] = dict(assignee_overrides)

    instance = TaskTemplateInstance(
      template_id=template.id,
      initiator_user_id=actor.id,
      department_id=resolved_department_id,
      status="in_progress",
      payload=instance_payload,
    )
    self._session.add(instance)
    await self._session.flush()
    tasks = await self._task_service.activate_template_instance_steps(instance_id=instance.id)
    instance_snapshot = await self.get_instance(
      actor=actor,
      template_id=template.id,
      instance_id=instance.id,
    )
    return TaskTemplateInstantiationResult(instance=instance_snapshot, tasks=tasks)
