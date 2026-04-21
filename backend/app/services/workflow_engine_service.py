from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
  ApprovalMode,
  DEFAULT_USER_NOTIFICATION_CHANNELS,
  DelegationScopeType,
  DelegationStatus,
  WorkflowDefinitionStatus,
  WorkflowInstanceStatus,
  WorkflowStepRunStatus,
  WorkflowStepType,
)
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models import (
  Delegation,
  User,
  WorkflowDefinition,
  WorkflowInstance,
  WorkflowStep,
  WorkflowStepRun,
)
from app.schemas.messages import NotificationMessage
from app.services.access_control import MANAGEMENT_ROLES, ensure_active_user
from app.services.notification_service import NotificationService
from app.services.notification_source import build_workflow_source_payload
from app.services.workflow_rule_resolver import parse_uuid_value, resolve_actor_department_id, resolve_user_targets_from_rule


def _step_iteration_value(step_run: WorkflowStepRun) -> int:
  raw_value = step_run.payload.get("iteration", 1)
  try:
    return int(raw_value)
  except (TypeError, ValueError):  # pragma: no cover - defensive branch
    return 1


class WorkflowEngineService:
  def __init__(
    self,
    session: AsyncSession,
    notification_service: NotificationService | None = None,
  ) -> None:
    self._session = session
    self._notification_service = notification_service

  def _definition_statement(self):
    return select(WorkflowDefinition).options(
      selectinload(WorkflowDefinition.creator),
      selectinload(WorkflowDefinition.steps),
    )

  def _instance_statement(self):
    return select(WorkflowInstance).execution_options(populate_existing=True).options(
      selectinload(WorkflowInstance.definition).selectinload(WorkflowDefinition.steps),
      selectinload(WorkflowInstance.initiator),
      selectinload(WorkflowInstance.step_runs).selectinload(WorkflowStepRun.step),
      selectinload(WorkflowInstance.step_runs).selectinload(WorkflowStepRun.assignee),
      selectinload(WorkflowInstance.step_runs).selectinload(WorkflowStepRun.delegated_from),
    )

  def _step_run_statement(self):
    return select(WorkflowStepRun).execution_options(populate_existing=True).options(
      selectinload(WorkflowStepRun.step),
      selectinload(WorkflowStepRun.assignee),
      selectinload(WorkflowStepRun.delegated_from),
      selectinload(WorkflowStepRun.instance)
      .selectinload(WorkflowInstance.definition)
      .selectinload(WorkflowDefinition.steps),
      selectinload(WorkflowStepRun.instance).selectinload(WorkflowInstance.initiator),
      selectinload(WorkflowStepRun.instance)
      .selectinload(WorkflowInstance.step_runs)
      .selectinload(WorkflowStepRun.step),
    )

  @staticmethod
  def _ensure_management(actor: User) -> None:
    if actor.role not in MANAGEMENT_ROLES:
      raise AuthorizationError("当前账号不能管理审批流定义。")

  @staticmethod
  def _ordered_steps(definition: WorkflowDefinition) -> list[WorkflowStep]:
    return sorted(definition.steps, key=lambda step: (step.sort_order, step.created_at))

  def _find_step_by_key(self, definition: WorkflowDefinition, step_key: str) -> WorkflowStep | None:
    for step in definition.steps:
      if step.step_key == step_key:
        return step
    return None

  def _get_next_step(self, definition: WorkflowDefinition, current_step: WorkflowStep | None) -> WorkflowStep | None:
    ordered_steps = self._ordered_steps(definition)
    if current_step is None:
      return ordered_steps[0] if ordered_steps else None
    for index, step in enumerate(ordered_steps):
      if step.id == current_step.id:
        return ordered_steps[index + 1] if index + 1 < len(ordered_steps) else None
    return None

  def _get_previous_step(self, definition: WorkflowDefinition, current_step: WorkflowStep) -> WorkflowStep | None:
    ordered_steps = self._ordered_steps(definition)
    for index, step in enumerate(ordered_steps):
      if step.id == current_step.id:
        return ordered_steps[index - 1] if index > 0 else None
    return None

  async def _get_definition_or_raise(
    self,
    *,
    actor: User,
    definition_id: UUID,
    require_active: bool = False,
  ) -> WorkflowDefinition:
    statement = self._definition_statement().where(WorkflowDefinition.id == definition_id)
    if require_active or actor.role not in MANAGEMENT_ROLES:
      statement = statement.where(WorkflowDefinition.status == WorkflowDefinitionStatus.ACTIVE)
    definition = await self._session.scalar(statement)
    if definition is None:
      raise NotFoundError("审批流定义不存在。")
    return definition

  async def _get_instance_or_raise(
    self,
    *,
    actor: User,
    instance_id: UUID,
  ) -> WorkflowInstance:
    statement = self._instance_statement().where(WorkflowInstance.id == instance_id)
    if actor.role not in MANAGEMENT_ROLES:
      statement = statement.where(
        or_(
          WorkflowInstance.initiator_user_id == actor.id,
          WorkflowInstance.step_runs.any(WorkflowStepRun.assignee_user_id == actor.id),
        )
      )
    instance = await self._session.scalar(statement)
    if instance is None:
      raise NotFoundError("审批实例不存在。")
    return instance

  async def _resolve_instance_department_id(self, *, instance: WorkflowInstance) -> UUID | None:
    raw_department_id = instance.payload.get("department_id")
    requested_department_id = (
      parse_uuid_value(raw_department_id, field_name="department_id")
      if raw_department_id is not None
      else None
    )
    return await resolve_actor_department_id(
      self._session,
      actor_id=instance.initiator_user_id,
      requested_department_id=requested_department_id,
    )

  async def _find_active_delegate(
    self,
    *,
    delegator_user_id: UUID,
    department_id: UUID | None,
  ) -> User | None:
    now = datetime.now(UTC)
    statement = (
      select(Delegation)
      .options(selectinload(Delegation.delegate))
      .where(
        Delegation.delegator_user_id == delegator_user_id,
        Delegation.status == DelegationStatus.ACTIVE,
        Delegation.scope_type.in_([DelegationScopeType.APPROVAL, DelegationScopeType.ALL]),
        Delegation.starts_at <= now,
        Delegation.ends_at > now,
      )
      .order_by(Delegation.starts_at.desc())
    )
    if department_id is None:
      statement = statement.where(Delegation.scope_department_id.is_(None))
    else:
      statement = statement.where(
        or_(
          Delegation.scope_department_id.is_(None),
          Delegation.scope_department_id == department_id,
        )
      )

    delegation = await self._session.scalar(statement)
    if delegation is None or delegation.delegate is None:
      return None
    ensure_active_user(delegation.delegate)
    return delegation.delegate

  async def _resolve_step_assignees(
    self,
    *,
    instance: WorkflowInstance,
    step: WorkflowStep,
  ) -> list[tuple[User, UUID | None]]:
    department_id = await self._resolve_instance_department_id(instance=instance)
    initiator = instance.initiator
    if initiator is None:
      initiator = await self._session.get(User, instance.initiator_user_id)
    if initiator is None:
      raise NotFoundError("流程发起人不存在。")
    ensure_active_user(initiator)

    allow_multiple = (
      step.step_type == WorkflowStepType.NOTIFY
      or step.approval_mode in {ApprovalMode.PARALLEL_ALL, ApprovalMode.PARALLEL_ANY}
    )
    users = await resolve_user_targets_from_rule(
      self._session,
      actor=initiator,
      assignee_rule=step.assignee_rule,
      department_id=department_id,
      allow_multiple=allow_multiple,
    )

    effective_users: list[tuple[User, UUID | None]] = []
    seen_user_ids: set[UUID] = set()
    for user in users:
      delegate = await self._find_active_delegate(
        delegator_user_id=user.id,
        department_id=department_id,
      )
      assignee = delegate or user
      delegated_from_user_id = user.id if delegate is not None else None
      if assignee.id in seen_user_ids:
        continue
      seen_user_ids.add(assignee.id)
      effective_users.append((assignee, delegated_from_user_id))

    if not effective_users:
      raise ConflictError("当前流程步骤没有可用执行人。")
    return effective_users

  async def _notify_user(
    self,
    *,
    recipient: User,
    instance: WorkflowInstance,
    message_type: str,
    title: str,
    body_text: str,
    payload: dict[str, object] | None = None,
  ) -> None:
    if self._notification_service is None:
      return
    workflow_route_tab = None
    if instance.source_type == "report":
      workflow_route_tab = (
        "initiated"
        if message_type in {"workflow_completed", "workflow_rejected", "workflow_returned"}
        else "pending"
      )
    await self._notification_service.send(
      NotificationMessage(
        source_type="workflow",
        source_id=instance.id,
        recipient_user_id=recipient.id,
        recipient_email=recipient.email,
        message_type=message_type,
        title=title,
        body_text=body_text,
        payload=build_workflow_source_payload(
          instance=instance,
          object_label=instance.definition.name,
          route_tab=workflow_route_tab,
          extra_payload=dict(payload or {}),
        ),
        channels=list(DEFAULT_USER_NOTIFICATION_CHANNELS),
      )
    )

  async def _get_instance_step_runs(self, *, instance: WorkflowInstance) -> list[WorkflowStepRun]:
    loaded_step_runs = instance.__dict__.get("step_runs")
    if loaded_step_runs is not None:
      return list(loaded_step_runs)
    if instance.id is None:
      return []
    return list(
      await self._session.scalars(
        select(WorkflowStepRun).where(WorkflowStepRun.instance_id == instance.id)
      )
    )

  async def _next_iteration(self, *, instance: WorkflowInstance, step: WorkflowStep) -> int:
    step_runs = await self._get_instance_step_runs(instance=instance)
    step_iterations = [
      _step_iteration_value(step_run)
      for step_run in step_runs
      if step_run.step_id == step.id
    ]
    return max(step_iterations, default=0) + 1

  async def _complete_instance(
    self,
    *,
    instance: WorkflowInstance,
    final_step: WorkflowStep | None,
  ) -> None:
    instance.current_step_key = None
    instance.completed_at = datetime.now(UTC)
    instance.status = (
      WorkflowInstanceStatus.APPROVED
      if final_step is not None and final_step.step_type == WorkflowStepType.APPROVAL
      else WorkflowInstanceStatus.COMPLETED
    )
    if instance.initiator is not None:
      await self._notify_user(
        recipient=instance.initiator,
        instance=instance,
        message_type="workflow_completed",
        title=f"审批完成：{instance.definition.name}",
        body_text=f"流程「{instance.definition.name}」已完成。",
        payload={"status": instance.status.value},
      )

  async def _enter_step(
    self,
    *,
    instance: WorkflowInstance,
    step: WorkflowStep,
    preserve_status: bool = False,
  ) -> None:
    iteration = await self._next_iteration(instance=instance, step=step)
    assignees = await self._resolve_step_assignees(instance=instance, step=step)
    now = datetime.now(UTC)
    instance.current_step_key = step.step_key
    if not preserve_status:
      instance.status = WorkflowInstanceStatus.IN_PROGRESS

    if step.step_type == WorkflowStepType.NOTIFY:
      for assignee, delegated_from_user_id in assignees:
        self._session.add(
          WorkflowStepRun(
            instance_id=instance.id,
            step_id=step.id,
            assignee_user_id=assignee.id,
            delegated_from_user_id=delegated_from_user_id,
            status=WorkflowStepRunStatus.SKIPPED,
            acted_at=now,
            comment="通知步骤自动完成。",
            payload={"iteration": iteration, "notify_only": True},
          )
        )
      await self._session.flush()
      for assignee, _ in assignees:
        await self._notify_user(
          recipient=assignee,
          instance=instance,
          message_type="workflow_notify",
          title=f"流程通知：{instance.definition.name}",
          body_text=f"流程「{instance.definition.name}」进入通知步骤「{step.name}」。",
          payload={"step_key": step.step_key, "step_name": step.name},
        )
      next_step = self._get_next_step(instance.definition, step)
      if next_step is None:
        await self._complete_instance(instance=instance, final_step=step)
      else:
        await self._enter_step(instance=instance, step=next_step)
      return

    for assignee, delegated_from_user_id in assignees:
      self._session.add(
        WorkflowStepRun(
          instance_id=instance.id,
          step_id=step.id,
          assignee_user_id=assignee.id,
          delegated_from_user_id=delegated_from_user_id,
          status=WorkflowStepRunStatus.PENDING,
          payload={"iteration": iteration},
        )
      )
    await self._session.flush()

    for assignee, delegated_from_user_id in assignees:
      title = f"待处理审批：{instance.definition.name}"
      if step.step_type == WorkflowStepType.TASK:
        title = f"待处理流程任务：{instance.definition.name}"
      body_text = f"流程「{instance.definition.name}」当前步骤「{step.name}」等待你处理。"
      if delegated_from_user_id is not None:
        body_text = f"流程「{instance.definition.name}」的步骤「{step.name}」已按代理规则转交给你处理。"
      await self._notify_user(
        recipient=assignee,
        instance=instance,
        message_type="workflow_action_required",
        title=title,
        body_text=body_text,
        payload={
          "step_key": step.step_key,
          "step_name": step.name,
          "delegated_from_user_id": str(delegated_from_user_id) if delegated_from_user_id else None,
        },
      )

  async def _advance_after_step(
    self,
    *,
    instance: WorkflowInstance,
    step: WorkflowStep,
  ) -> None:
    next_step = self._get_next_step(instance.definition, step)
    if next_step is None:
      await self._complete_instance(instance=instance, final_step=step)
      return
    await self._enter_step(instance=instance, step=next_step)

  async def _resolve_current_batch_runs(
    self,
    *,
    instance: WorkflowInstance,
    step_run: WorkflowStepRun,
  ) -> list[WorkflowStepRun]:
    step_runs = await self._get_instance_step_runs(instance=instance)
    current_iteration = _step_iteration_value(step_run)
    return [
      current_batch_run
      for current_batch_run in step_runs
      if current_batch_run.step_id == step_run.step_id and _step_iteration_value(current_batch_run) == current_iteration
    ]

  async def list_definitions(self, *, actor: User) -> list[WorkflowDefinition]:
    ensure_active_user(actor)
    statement = self._definition_statement().order_by(WorkflowDefinition.updated_at.desc())
    if actor.role not in MANAGEMENT_ROLES:
      statement = statement.where(WorkflowDefinition.status == WorkflowDefinitionStatus.ACTIVE)
    return list(await self._session.scalars(statement))

  async def get_definition(self, *, actor: User, definition_id: UUID) -> WorkflowDefinition:
    ensure_active_user(actor)
    return await self._get_definition_or_raise(actor=actor, definition_id=definition_id)

  async def create_definition(
    self,
    *,
    actor: User,
    code: str,
    name: str,
    scope_type: str,
    status: WorkflowDefinitionStatus = WorkflowDefinitionStatus.DRAFT,
    version: int = 1,
    config: dict[str, object] | None = None,
    steps: list[dict[str, object]],
  ) -> WorkflowDefinition:
    ensure_active_user(actor)
    self._ensure_management(actor)

    if await self._session.scalar(select(WorkflowDefinition.id).where(WorkflowDefinition.code == code)) is not None:
      raise ConflictError("审批流编码已存在。")

    definition = WorkflowDefinition(
      code=code.strip(),
      name=name.strip(),
      scope_type=scope_type.strip(),
      status=status,
      version=version,
      config=dict(config or {}),
      created_by=actor.id,
    )
    self._session.add(definition)
    await self._session.flush()
    await self._replace_steps(definition=definition, steps=steps)
    await self._session.commit()
    return await self.get_definition(actor=actor, definition_id=definition.id)

  async def _replace_steps(
    self,
    *,
    definition: WorkflowDefinition,
    steps: list[dict[str, object]],
  ) -> None:
    if not steps:
      raise ConflictError("审批流至少需要一个步骤。")

    existing_steps = list(
      await self._session.scalars(
        select(WorkflowStep).where(WorkflowStep.definition_id == definition.id)
      )
    )
    for existing_step in existing_steps:
      await self._session.delete(existing_step)
    await self._session.flush()

    step_map: dict[str, WorkflowStep] = {}
    for index, step_payload in enumerate(steps, start=1):
      step_key = str(step_payload.get("step_key") or "").strip()
      name = str(step_payload.get("name") or "").strip()
      if not step_key or not name:
        raise ConflictError("审批步骤必须包含 step_key 和 name。")
      if step_key in step_map:
        raise ConflictError("审批步骤 step_key 不能重复。")

      try:
        step_type = WorkflowStepType(str(step_payload.get("step_type") or WorkflowStepType.APPROVAL))
      except ValueError as exc:
        raise ConflictError("不支持的审批步骤类型。") from exc

      raw_approval_mode = step_payload.get("approval_mode")
      if step_type == WorkflowStepType.NOTIFY:
        approval_mode = None
      elif raw_approval_mode is None:
        approval_mode = ApprovalMode.SINGLE
      else:
        try:
          approval_mode = ApprovalMode(str(raw_approval_mode))
        except ValueError as exc:
          raise ConflictError("不支持的审批模式。") from exc

      step = WorkflowStep(
        definition_id=definition.id,
        step_key=step_key,
        name=name,
        step_type=step_type,
        approval_mode=approval_mode,
        assignee_rule=dict(step_payload.get("assignee_rule") or {"type": "initiator"}),
        reject_target_step_key=str(step_payload.get("reject_target_step_key") or "").strip() or None,
        sort_order=int(step_payload.get("sort_order") or index),
        config=dict(step_payload.get("config") or {}),
      )
      self._session.add(step)
      step_map[step_key] = step

    await self._session.flush()

    for step in step_map.values():
      if step.reject_target_step_key and step.reject_target_step_key not in step_map:
        raise ConflictError("reject_target_step_key 引用了不存在的步骤。")

  async def update_definition(
    self,
    *,
    actor: User,
    definition_id: UUID,
    code: str | None = None,
    name: str | None = None,
    scope_type: str | None = None,
    status: WorkflowDefinitionStatus | None = None,
    version: int | None = None,
    config: dict[str, object] | None = None,
    steps: list[dict[str, object]] | None = None,
  ) -> WorkflowDefinition:
    ensure_active_user(actor)
    self._ensure_management(actor)
    definition = await self._get_definition_or_raise(actor=actor, definition_id=definition_id)

    if code is not None and code.strip() != definition.code:
      existing_definition_id = await self._session.scalar(
        select(WorkflowDefinition.id).where(WorkflowDefinition.code == code.strip())
      )
      if existing_definition_id is not None and existing_definition_id != definition.id:
        raise ConflictError("审批流编码已存在。")
      definition.code = code.strip()
    if name is not None:
      definition.name = name.strip()
    if scope_type is not None:
      definition.scope_type = scope_type.strip()
    if status is not None:
      definition.status = status
    if version is not None:
      definition.version = version
    if config is not None:
      definition.config = dict(config)
    if steps is not None:
      await self._replace_steps(definition=definition, steps=steps)

    definition.updated_at = datetime.now(UTC)
    await self._session.commit()
    return await self.get_definition(actor=actor, definition_id=definition.id)

  async def list_instances(self, *, actor: User) -> list[WorkflowInstance]:
    ensure_active_user(actor)
    statement = self._instance_statement().order_by(WorkflowInstance.started_at.desc())
    if actor.role not in MANAGEMENT_ROLES:
      statement = statement.where(
        or_(
          WorkflowInstance.initiator_user_id == actor.id,
          WorkflowInstance.step_runs.any(WorkflowStepRun.assignee_user_id == actor.id),
        )
      )
    return list(await self._session.scalars(statement))

  async def get_instance(self, *, actor: User, instance_id: UUID) -> WorkflowInstance:
    ensure_active_user(actor)
    return await self._get_instance_or_raise(actor=actor, instance_id=instance_id)

  async def list_pending_step_runs(self, *, actor: User) -> list[WorkflowStepRun]:
    ensure_active_user(actor)
    statement = (
      self._step_run_statement()
      .where(
        WorkflowStepRun.assignee_user_id == actor.id,
        WorkflowStepRun.status == WorkflowStepRunStatus.PENDING,
      )
      .order_by(WorkflowStepRun.created_at.asc())
    )
    return list(await self._session.scalars(statement))

  async def start_workflow(
    self,
    *,
    actor: User,
    definition_id: UUID,
    source_type: str,
    source_id: UUID | None = None,
    payload: dict[str, object] | None = None,
  ) -> WorkflowInstance:
    ensure_active_user(actor)
    definition = await self._get_definition_or_raise(
      actor=actor,
      definition_id=definition_id,
      require_active=True,
    )
    if not definition.steps:
      raise ConflictError("审批流没有可执行步骤。")

    instance = WorkflowInstance(
      definition_id=definition.id,
      source_type=source_type.strip(),
      source_id=source_id,
      initiator_user_id=actor.id,
      status=WorkflowInstanceStatus.PENDING,
      payload=dict(payload or {}),
      started_at=datetime.now(UTC),
    )
    instance.definition = definition
    instance.initiator = actor
    self._session.add(instance)
    await self._session.flush()
    await self._enter_step(instance=instance, step=self._ordered_steps(definition)[0])
    await self._session.commit()
    return await self.get_instance(actor=actor, instance_id=instance.id)

  async def act_step_run(
    self,
    *,
    actor: User,
    step_run_id: UUID,
    action: str,
    comment: str | None = None,
  ) -> WorkflowInstance:
    ensure_active_user(actor)
    normalized_action = action.strip().lower()
    if normalized_action not in {"approve", "reject", "return"}:
      raise ConflictError("不支持的审批动作。")

    step_run = await self._session.scalar(self._step_run_statement().where(WorkflowStepRun.id == step_run_id))
    if step_run is None:
      raise NotFoundError("审批步骤不存在。")
    if actor.id != step_run.assignee_user_id and actor.role not in MANAGEMENT_ROLES:
      raise AuthorizationError("当前账号不能处理该审批步骤。")
    if step_run.status != WorkflowStepRunStatus.PENDING:
      raise ConflictError("审批步骤已处理，不能重复提交。")

    instance = await self._session.scalar(
      self._instance_statement().where(WorkflowInstance.id == step_run.instance_id)
    )
    if instance is None:
      raise NotFoundError("审批实例不存在。")
    step = step_run.step
    if step is None:
      step = await self._session.get(WorkflowStep, step_run.step_id)
      if step is None:
        raise NotFoundError("审批步骤不存在。")
    current_batch_runs = await self._resolve_current_batch_runs(instance=instance, step_run=step_run)
    now = datetime.now(UTC)

    step_run.acted_at = now
    step_run.comment = comment.strip() if comment else None

    if normalized_action == "approve":
      step_run.status = WorkflowStepRunStatus.APPROVED
      if step.approval_mode == ApprovalMode.PARALLEL_ANY:
        for sibling_run in current_batch_runs:
          if sibling_run.id != step_run.id and sibling_run.status == WorkflowStepRunStatus.PENDING:
            sibling_run.status = WorkflowStepRunStatus.SKIPPED
            sibling_run.acted_at = now
            sibling_run.comment = "同批次已有审批通过，当前节点自动跳过。"
        await self._advance_after_step(instance=instance, step=step)
      elif step.approval_mode == ApprovalMode.PARALLEL_ALL:
        if all(batch_run.status == WorkflowStepRunStatus.APPROVED for batch_run in current_batch_runs):
          await self._advance_after_step(instance=instance, step=step)
      else:
        await self._advance_after_step(instance=instance, step=step)

    elif normalized_action == "reject":
      step_run.status = WorkflowStepRunStatus.REJECTED
      for sibling_run in current_batch_runs:
        if sibling_run.id != step_run.id and sibling_run.status == WorkflowStepRunStatus.PENDING:
          sibling_run.status = WorkflowStepRunStatus.SKIPPED
          sibling_run.acted_at = now
          sibling_run.comment = "同批次步骤因驳回自动跳过。"
      instance.status = WorkflowInstanceStatus.REJECTED
      instance.completed_at = now
      instance.current_step_key = None
      if instance.initiator is not None:
        await self._notify_user(
          recipient=instance.initiator,
          instance=instance,
          message_type="workflow_rejected",
          title=f"审批被驳回：{instance.definition.name}",
          body_text=f"流程「{instance.definition.name}」在步骤「{step.name}」被驳回。",
          payload={"step_key": step.step_key, "comment": step_run.comment},
        )

    else:
      step_run.status = WorkflowStepRunStatus.RETURNED
      for sibling_run in current_batch_runs:
        if sibling_run.id != step_run.id and sibling_run.status == WorkflowStepRunStatus.PENDING:
          sibling_run.status = WorkflowStepRunStatus.SKIPPED
          sibling_run.acted_at = now
          sibling_run.comment = "同批次步骤因打回自动跳过。"

      target_step = (
        self._find_step_by_key(instance.definition, step.reject_target_step_key)
        if step.reject_target_step_key
        else self._get_previous_step(instance.definition, step)
      )
      if target_step is None:
        raise ConflictError("当前步骤没有可打回的目标步骤。")

      instance.status = WorkflowInstanceStatus.RETURNED
      instance.completed_at = None
      await self._enter_step(instance=instance, step=target_step, preserve_status=True)
      if instance.initiator is not None:
        await self._notify_user(
          recipient=instance.initiator,
          instance=instance,
          message_type="workflow_returned",
          title=f"审批被打回：{instance.definition.name}",
          body_text=f"流程「{instance.definition.name}」已被打回到步骤「{target_step.name}」。",
          payload={"step_key": target_step.step_key, "comment": step_run.comment},
        )

    await self._session.commit()
    return await self.get_instance(actor=actor, instance_id=instance.id)
