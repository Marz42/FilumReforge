from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
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


@dataclass(slots=True)
class TaskTemplateViewMetadata:
  latest_version: int
  has_instances: bool


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

  async def _template_has_instances(self, *, template_id: UUID) -> bool:
    existing_instance_id = await self._session.scalar(
      select(TaskTemplateInstance.id)
      .where(TaskTemplateInstance.template_id == template_id)
      .limit(1)
    )
    return existing_instance_id is not None

  async def _get_next_template_version(self, *, base_code: str) -> int:
    latest_version = await self._session.scalar(
      select(func.max(TaskTemplate.version)).where(TaskTemplate.base_code == base_code)
    )
    return (latest_version or 0) + 1

  async def get_template_view_metadata(self, *, template_ids: list[UUID]) -> dict[UUID, TaskTemplateViewMetadata]:
    if not template_ids:
      return {}

    templates = list(
      await self._session.scalars(
        select(TaskTemplate).where(TaskTemplate.id.in_(template_ids))
      )
    )
    if not templates:
      return {}

    base_codes = {template.base_code for template in templates}
    latest_versions = {
      base_code: latest_version
      for base_code, latest_version in (
        await self._session.execute(
          select(TaskTemplate.base_code, func.max(TaskTemplate.version))
          .where(TaskTemplate.base_code.in_(base_codes))
          .group_by(TaskTemplate.base_code)
        )
      ).all()
    }
    instance_template_ids = set(
      await self._session.scalars(
        select(TaskTemplateInstance.template_id)
        .where(TaskTemplateInstance.template_id.in_(template_ids))
        .distinct()
      )
    )

    return {
      template.id: TaskTemplateViewMetadata(
        latest_version=int(latest_versions.get(template.base_code, template.version) or template.version),
        has_instances=template.id in instance_template_ids,
      )
      for template in templates
    }

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

  @staticmethod
  def _canonicalize_step_payloads(steps: list[dict[str, object]]) -> list[dict[str, object]]:
    canonical_steps: list[dict[str, object]] = []
    for index, step_payload in enumerate(steps, start=1):
      assignment_mode = str(step_payload.get("assignment_mode") or "single").strip()
      join_mode = str(step_payload.get("join_mode") or "all").strip()
      raw_downstream = step_payload.get("downstream_trigger")
      canonical_steps.append(
        {
          "step_key": str(step_payload.get("step_key") or "").strip(),
          "title": str(step_payload.get("title") or "").strip(),
          "description": str(step_payload.get("description") or "").strip() or None,
          "step_type": str(step_payload.get("step_type") or "task").strip(),
          "assignment_mode": assignment_mode,
          "join_mode": "all" if assignment_mode == "single" else join_mode,
          "default_assignee_rule": dict(step_payload.get("default_assignee_rule") or {"type": "initiator"}),
          "default_due_offset_hours": (
            int(step_payload["default_due_offset_hours"])
            if step_payload.get("default_due_offset_hours") is not None
            else None
          ),
          "sort_order": int(step_payload.get("sort_order") or index),
          "config": dict(step_payload.get("config") or {}),
          "depends_on_step_keys": sorted(
            dict.fromkeys(str(raw_key) for raw_key in (step_payload.get("depends_on_step_keys") or []))
          ),
          "approval_type": str(step_payload.get("approval_type") or "none").strip(),
          "reject_target_step_key": (
            str(step_payload["reject_target_step_key"]).strip() or None
            if step_payload.get("reject_target_step_key")
            else None
          ),
          "downstream_trigger": dict(raw_downstream) if isinstance(raw_downstream, dict) else None,
        }
      )
    return canonical_steps

  @staticmethod
  def _serialize_existing_steps(template: TaskTemplate) -> list[dict[str, object]]:
    ordered_steps = sorted(template.steps, key=lambda current_step: (current_step.sort_order, current_step.created_at))
    return [
      {
        "step_key": step.step_key,
        "title": step.title,
        "description": step.description,
        "step_type": step.step_type,
        "assignment_mode": step.assignment_mode,
        "join_mode": step.join_mode,
        "default_assignee_rule": dict(step.default_assignee_rule or {}),
        "default_due_offset_hours": step.default_due_offset_hours,
        "sort_order": step.sort_order,
        "config": dict(step.config or {}),
        "depends_on_step_keys": sorted(
          dependency.depends_on_step.step_key
          for dependency in step.dependencies
          if dependency.depends_on_step is not None
        ),
        "approval_type": step.approval_type,
        "reject_target_step_key": step.reject_target_step_key,
        "downstream_trigger": dict(step.downstream_trigger) if step.downstream_trigger is not None else None,
      }
      for step in ordered_steps
    ]

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
        approval_type=str(step_payload.get("approval_type") or "none"),
        reject_target_step_key=(
          str(step_payload["reject_target_step_key"]).strip() or None
          if step_payload.get("reject_target_step_key")
          else None
        ),
        downstream_trigger=(
          dict(step_payload["downstream_trigger"])
          if isinstance(step_payload.get("downstream_trigger"), dict)
          else None
        ),
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
    source_template_id: UUID | None = None,
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

    normalized_code = code.strip()
    if await self._session.scalar(select(TaskTemplate.id).where(TaskTemplate.code == normalized_code)) is not None:
      raise ConflictError("任务模板编码已存在。")

    source_template: TaskTemplate | None = None
    base_code = normalized_code
    version = 1
    if source_template_id is not None:
      source_template = await self._get_template_or_raise(actor=actor, template_id=source_template_id)
      base_code = source_template.base_code
      version = await self._get_next_template_version(base_code=base_code)

    template = TaskTemplate(
      code=normalized_code,
      base_code=base_code,
      version=version,
      name=name.strip(),
      category=category.strip(),
      description=description.strip() if description else None,
      trigger_type=trigger_type.strip(),
      config=dict(config or {}),
      is_active=is_active,
      created_by=actor.id,
      source_template_id=source_template.id if source_template is not None else None,
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
      canonical_steps = self._canonicalize_step_payloads(steps)
      if canonical_steps != self._serialize_existing_steps(template):
        if await self._template_has_instances(template_id=template.id):
          raise ConflictError("模板已有实例运行记录，暂不支持修改步骤结构，请新建模板版本。")
        await self._replace_steps(template=template, steps=canonical_steps)

    template.updated_at = datetime.now(UTC)
    await self._session.commit()
    return await self.get_template(actor=actor, template_id=template.id)

  async def delete_template(self, *, actor: User, template_id: UUID) -> None:
    ensure_active_user(actor)
    await self._ensure_manage_templates(actor=actor)
    template = await self._get_template_or_raise(actor=actor, template_id=template_id)

    if await self._template_has_instances(template_id=template.id):
      raise ConflictError("模板已有实例运行记录，不能删除。")

    await self._session.delete(template)
    await self._session.commit()

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

  async def _get_step_run_for_decide(
    self,
    *,
    actor: User,
    instance_id: UUID,
    step_run_id: UUID,
  ) -> tuple[TaskTemplateStepRun, TaskTemplateInstance, TaskTemplateStep]:
    step_run = await self._session.scalar(
      select(TaskTemplateStepRun)
      .options(
        selectinload(TaskTemplateStepRun.template_step),
        selectinload(TaskTemplateStepRun.instance)
        .selectinload(TaskTemplateInstance.template)
        .selectinload(TaskTemplate.steps)
        .selectinload(TaskTemplateStep.dependencies)
        .selectinload(TaskTemplateStepDependency.depends_on_step),
        selectinload(TaskTemplateStepRun.instance).selectinload(TaskTemplateInstance.initiator),
        selectinload(TaskTemplateStepRun.instance).selectinload(TaskTemplateInstance.department),
      )
      .where(
        TaskTemplateStepRun.id == step_run_id,
        TaskTemplateStepRun.instance_id == instance_id,
      )
    )
    if step_run is None:
      raise NotFoundError("步骤执行记录不存在。")
    if step_run.assignee_user_id != actor.id and not await can_manage_task_templates(self._session, actor):
      raise AuthorizationError("无权操作此步骤执行记录。")
    if step_run.instance is None or step_run.template_step is None:
      raise NotFoundError("步骤执行记录上下文不完整。")
    return step_run, step_run.instance, step_run.template_step

  async def _fire_downstream_triggers(
    self,
    *,
    actor: User,
    instance: TaskTemplateInstance,
    completed_step: TaskTemplateStep,
  ) -> None:
    trigger = completed_step.downstream_trigger
    if not trigger or not isinstance(trigger, dict):
      return
    downstream_code = trigger.get("template_code")
    if not downstream_code:
      return

    downstream_template = await self._session.scalar(
      self._statement().where(TaskTemplate.code == downstream_code, TaskTemplate.is_active.is_(True))
    )
    if downstream_template is None:
      return

    spawn_mode = trigger.get("spawn_mode", "single")
    base_payload = dict(instance.payload)
    base_payload["inherited_context"] = {
      "source_instance_id": str(instance.id),
      "source_template_id": str(instance.template_id),
      "source_step_key": completed_step.step_key,
    }

    if spawn_mode == "per_step_run":
      source_step_key = trigger.get("spawn_source_step_key")
      if not source_step_key:
        return
      source_step = next(
        (s for s in instance.template.steps if s.step_key == source_step_key),
        None,
      )
      if source_step is None:
        return
      # Load completed step runs for the source step
      source_step_runs = list(
        await self._session.scalars(
          select(TaskTemplateStepRun)
          .options(selectinload(TaskTemplateStepRun.assignee))
          .where(
            TaskTemplateStepRun.instance_id == instance.id,
            TaskTemplateStepRun.template_step_id == source_step.id,
            TaskTemplateStepRun.status == "completed",
          )
        )
      )
      # Deduplicate by assignee (take one run per assignee)
      seen_assignees: set[UUID] = set()
      for src_run in source_step_runs:
        if src_run.assignee_user_id in seen_assignees:
          continue
        seen_assignees.add(src_run.assignee_user_id)
        if src_run.assignee is None:
          continue
        spawn_payload = dict(base_payload)
        spawn_payload["inherited_context"]["source_assignee_id"] = str(src_run.assignee_user_id)
        await self._task_service.activate_template_instance_steps(
          instance_id=(
            await self._spawn_downstream_instance(
              actor=src_run.assignee,
              template=downstream_template,
              department_id=instance.department_id,
              payload=spawn_payload,
            )
          ).id
        )
    else:
      await self._task_service.activate_template_instance_steps(
        instance_id=(
          await self._spawn_downstream_instance(
            actor=actor,
            template=downstream_template,
            department_id=instance.department_id,
            payload=base_payload,
          )
        ).id
      )

  async def _spawn_downstream_instance(
    self,
    *,
    actor: User,
    template: TaskTemplate,
    department_id: UUID | None,
    payload: dict[str, object],
  ) -> TaskTemplateInstance:
    new_instance = TaskTemplateInstance(
      template_id=template.id,
      initiator_user_id=actor.id,
      department_id=department_id,
      status="in_progress",
      payload=payload,
    )
    self._session.add(new_instance)
    await self._session.flush()
    return new_instance

  async def decide_step_run(
    self,
    *,
    actor: User,
    template_id: UUID,
    instance_id: UUID,
    step_run_id: UUID,
    decision: str,
    comment: str | None = None,
  ) -> TaskTemplateInstance:
    ensure_active_user(actor)
    if decision not in {"approved", "rejected", "returned"}:
      raise ConflictError("decision 必须为 approved、rejected 或 returned。")

    step_run, instance, step = await self._get_step_run_for_decide(
      actor=actor,
      instance_id=instance_id,
      step_run_id=step_run_id,
    )

    if step.approval_type == "none":
      raise ConflictError("该步骤不是审核步骤，不支持审批操作。")
    if step_run.status != "active":
      raise ConflictError("步骤执行记录当前状态不允许审批操作。")

    now = datetime.now(UTC)
    step_run.decision = decision
    step_run.status = "completed"
    step_run.completed_at = now
    await self._session.flush()

    if decision == "approved":
      # Trigger normal downstream step activation + cross-template trigger
      await self._task_service.activate_template_instance_steps(instance_id=instance.id)
      await self._session.commit()
      await self._fire_downstream_triggers(actor=actor, instance=instance, completed_step=step)
      await self._session.commit()
    else:
      # Rejected or returned: re-activate the target step
      reject_key = step.reject_target_step_key
      if not reject_key:
        raise ConflictError("该审核步骤未配置驳回目标步骤。")
      target_step = next(
        (s for s in instance.template.steps if s.step_key == reject_key),
        None,
      )
      if target_step is None:
        raise ConflictError(f"驳回目标步骤 '{reject_key}' 不存在于当前模板。")

      # Find the most recent completed step_run of the target step to get assignee
      latest_target_run = await self._session.scalar(
        select(TaskTemplateStepRun)
        .options(selectinload(TaskTemplateStepRun.assignee))
        .where(
          TaskTemplateStepRun.instance_id == instance.id,
          TaskTemplateStepRun.template_step_id == target_step.id,
          TaskTemplateStepRun.status == "completed",
        )
        .order_by(TaskTemplateStepRun.iteration.desc())
        .limit(1)
      )
      if latest_target_run is None or latest_target_run.assignee is None:
        raise ConflictError("找不到可驳回的目标步骤执行人。")

      next_iteration = latest_target_run.iteration + 1
      new_step_run = TaskTemplateStepRun(
        instance_id=instance.id,
        template_step_id=target_step.id,
        assignee_user_id=latest_target_run.assignee_user_id,
        iteration=next_iteration,
        status="active",
      )
      self._session.add(new_step_run)
      await self._session.flush()

      # Create a new Task for the re-activated step
      initiator = instance.initiator
      template_obj = instance.template
      if initiator is None or template_obj is None:
        raise NotFoundError("模板实例上下文不完整。")

      from datetime import timedelta
      from app.core.enums import TaskSourceType
      due_date = (
        now + timedelta(hours=target_step.default_due_offset_hours)
        if target_step.default_due_offset_hours is not None
        else None
      )
      task, _ = await self._task_service.create_task_record(
        actor=initiator,
        title=f"{template_obj.name} / {target_step.title}（第 {next_iteration} 次）",
        assignee_id=latest_target_run.assignee_user_id,
        description="\n\n".join(v for v in [template_obj.description, target_step.description, comment] if v) or None,
        department_id=instance.department_id,
        due_date=due_date,
        priority=TaskPriority(str(target_step.config.get("priority") or TaskPriority.MEDIUM)),
        source_type=TaskSourceType.TEMPLATE,
        extra_metadata={
          "template_id": str(template_obj.id),
          "template_code": template_obj.code,
          "template_instance_id": str(instance.id),
          "template_step_id": str(target_step.id),
          "template_step_run_id": str(new_step_run.id),
          "template_step_key": target_step.step_key,
          "template_step_type": target_step.step_type,
          "assignment_mode": target_step.assignment_mode,
          "join_mode": target_step.join_mode,
          "instantiation_payload": dict(instance.payload),
          "reject_iteration": next_iteration,
          "rejected_by_step_key": step.step_key,
        },
        commit=False,
        skip_assignee_permission=True,
        skip_publish_permission=True,
      )
      task.template_instance_id = instance.id
      task.template_step_run_id = new_step_run.id
      await self._session.commit()

    return await self.get_instance(actor=actor, template_id=template_id, instance_id=instance.id)
