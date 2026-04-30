from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
  AttachmentStatus,
  AttachmentTargetType,
  AttachmentVisibility,
  CommentFormat,
  DEFAULT_USER_NOTIFICATION_CHANNELS,
  TaskActionType,
  TaskPriority,
  TaskSourceType,
  TaskStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
  WorkflowGraphInstanceStatus,
  WorkflowStepRunStatus,
)
from app.core.config import Settings
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models import (
  Attachment,
  Department,
  Profile,
  Task,
  TaskComment,
  TaskDependency,
  TaskLog,
  TaskTemplate,
  TaskTemplateInstance,
  TaskTemplateStep,
  TaskTemplateStepRun,
  TaskWatcher,
  User,
  WorkflowDeliverable,
  WorkflowGraphInstance,
  WorkflowInstance,
  WorkflowNodeInstance,
  WorkflowStep,
  WorkflowStepRun,
)
from app.schemas.messages import NotificationMessage
from app.services.notification_source import build_task_source_payload
from app.services.workflow_graph_service import SingleNodeWorkflowSeed, WorkflowGraphService
from app.services.workflow_rule_resolver import resolve_user_targets_from_rule
from app.services.access_control import (
  MANAGEMENT_ROLES,
  can_publish_org_tasks,
  can_manage_assignee,
  ensure_active_user,
  get_managed_department_ids,
)
from app.services.notification_service import NotificationService
from app.services.condition_evaluator import evaluate_routing_rules


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


@dataclass(slots=True)
class TaskInboxEntry:
  task_id: UUID
  title: str
  priority: TaskPriority
  status: TaskStatus
  due_date: datetime | None
  department_name: str | None
  current_stage_label: str
  current_handler_label: str | None


@dataclass(slots=True)
class TaskTrackingEntry:
  task_id: UUID
  title: str
  priority: TaskPriority
  status: TaskStatus
  due_date: datetime | None
  department_name: str | None
  relation_types: list[str]
  current_stage_label: str
  current_handler_label: str | None
  latest_deliverable_submitted_at: datetime | None = None
  rework_count: int = 0
  review_quality_score: int | None = None
  is_pending_review: bool = False


@dataclass(slots=True)
class TaskHistoryEntry:
  task_id: UUID
  title: str
  priority: TaskPriority
  due_date: datetime | None
  completed_at: datetime | None
  department_name: str | None
  relation_types: list[str]
  source_type: TaskSourceType


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


def _task_priority_sort_value(priority: TaskPriority) -> int:
  priority_order = {
    TaskPriority.URGENT: 0,
    TaskPriority.HIGH: 1,
    TaskPriority.MEDIUM: 2,
    TaskPriority.LOW: 3,
  }
  return priority_order[priority]


def _task_status_label(status: TaskStatus) -> str:
  labels = {
    TaskStatus.TODO: "待办",
    TaskStatus.DOING: "进行中",
    TaskStatus.REVIEW: "评审中",
    TaskStatus.DONE: "已完成",
  }
  return labels[status]


HANDSHAKE_ASSIGNED = "assigned"
HANDSHAKE_ACCEPTED = "accepted"
HANDSHAKE_REJECTED = "rejected"


def _user_display_label(user: User | None) -> str | None:
  if user is None:
    return None
  if user.profile and user.profile.real_name:
    return user.profile.real_name
  return user.email


class TaskService:
  def __init__(
    self,
    session: AsyncSession,
    notification_service: NotificationService | None = None,
    attachment_service=None,  # noqa: ANN001
    settings: Settings | None = None,
    workflow_graph_service: WorkflowGraphService | None = None,
  ) -> None:
    self._session = session
    self._notification_service = notification_service
    self._attachment_service = attachment_service
    self._settings = settings
    self._workflow_graph_service = workflow_graph_service

  def _workflow_graph_engine_enabled(self) -> bool:
    return bool(self._settings is not None and self._settings.workflow_graph_engine_enabled)

  async def _create_single_node_workflow_projection(
    self,
    *,
    actor: User,
    title: str,
    assignee_id: UUID,
    description: str | None,
    department_id: UUID | None,
    due_date: datetime | None,
    priority: TaskPriority,
    dependency_ids: list[UUID] | None,
    source_type: TaskSourceType,
    extra_metadata: dict[str, object] | None,
  ) -> Task:
    if self._workflow_graph_service is None:
      raise ConflictError("图引擎开关已开启，但 WorkflowGraphService 尚未注入。")

    instance, node_instance = await self._workflow_graph_service.create_single_node_instance(
      seed=SingleNodeWorkflowSeed(
        title=title,
        creator_id=actor.id,
        assignee_id=assignee_id,
        department_id=department_id,
        description=description,
        due_date=due_date,
        priority=priority,
      )
    )

    metadata = dict(extra_metadata or {})
    deep_rejection_cfg = (node_instance.config or {}).get("deep_rejection") or {}
    deep_rejection_reason = deep_rejection_cfg.get("reason")
    metadata.update(
      {
        "workflow_graph_instance_id": str(instance.id),
        "workflow_node_instance_id": str(node_instance.id),
        "workflow_node_iteration": node_instance.iteration,
        "workflow_handshake_state": HANDSHAKE_ASSIGNED,
        "latest_handshake_action": HANDSHAKE_ASSIGNED,
        "latest_handshake_actor_user_id": str(actor.id),
      }
    )
    if deep_rejection_reason:
      metadata["workflow_deep_rejection_reason"] = deep_rejection_reason

    task = Task(
      title=title,
      description=description,
      creator_id=actor.id,
      assignee_id=assignee_id,
      department_id=department_id,
      due_date=due_date,
      priority=priority,
      source_type=source_type,
      extra_metadata=metadata,
    )
    self._session.add(task)
    await self._session.flush()

    instance.source_id = task.id
    instance.source_type = source_type.value
    instance.status = WorkflowGraphInstanceStatus.ACTIVE
    node_instance.config = {
      **node_instance.config,
      "task_id": str(task.id),
    }

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
        "template_instance_id": str(task.template_instance_id) if task.template_instance_id is not None else None,
        "template_step_run_id": str(task.template_step_run_id) if task.template_step_run_id is not None else None,
        "workflow_graph_instance_id": str(instance.id),
        "workflow_node_instance_id": str(node_instance.id),
      },
    )
    await self._create_task_log(
      task_id=task.id,
      operator_id=actor.id,
      action_type=TaskActionType.ASSIGNED,
      detail={
        "action": HANDSHAKE_ASSIGNED,
        "assignee_id": str(assignee_id),
        "workflow_node_instance_id": str(node_instance.id),
      },
    )
    return task

  @staticmethod
  def _is_template_step_satisfied(*, step: TaskTemplateStep, step_runs: list[TaskTemplateStepRun]) -> bool:
    if not step_runs:
      return False
    if getattr(step, "approval_type", "none") not in {None, "none", ""}:
      # Approval steps are satisfied only when approved (not merely completed with a rejection)
      return any(sr.status == "completed" and sr.decision == "approved" for sr in step_runs)
    if step.join_mode == "any":
      return any(sr.status == "completed" for sr in step_runs)
    return all(sr.status == "completed" for sr in step_runs)

  @staticmethod
  def _routing_rules_allow_step_activation(
    *,
    step: TaskTemplateStep,
    dependency_ids: set[UUID],
    steps_by_id: dict[UUID, TaskTemplateStep],
    routing_context: dict[str, Any],
  ) -> bool:
    """Return False if any upstream dependency step has routing_rules that do NOT
    include the current step's step_key as a routing target.

    When an upstream step carries routing_rules, those rules decide which downstream
    step(s) to activate.  Steps not in the routing result are skipped.
    Steps whose upstream dependency has no routing_rules are unaffected (backward-
    compatible with pure dependency-based activation).
    """
    for dep_step_id in dependency_ids:
      dep_step = steps_by_id.get(dep_step_id)
      if dep_step is None:
        continue
      config = dep_step.config or {}
      routing_rules = config.get("routing_rules")
      if not routing_rules:
        continue  # no rules on this upstream step — no restriction
      allowed_keys = evaluate_routing_rules(routing_rules, routing_context)
      # allowed_keys is None  → no rules (shouldn't happen here, but guard)
      # allowed_keys is set() → matched nothing (shouldn't route anywhere)
      if allowed_keys is None:
        continue
      if step.step_key not in allowed_keys:
        return False
    return True

  async def _load_tasks_by_ids(self, *, task_ids: list[UUID]) -> list[Task]:
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

  async def _get_template_instance_or_raise(
    self,
    *,
    instance_id: UUID,
    for_update: bool = False,
  ) -> TaskTemplateInstance:
    statement = (
      select(TaskTemplateInstance)
      .options(
        selectinload(TaskTemplateInstance.template)
        .selectinload(TaskTemplate.steps)
        .selectinload(TaskTemplateStep.dependencies),
        selectinload(TaskTemplateInstance.initiator),
      )
      .where(TaskTemplateInstance.id == instance_id)
    )
    if for_update:
      statement = statement.with_for_update()

    instance = await self._session.scalar(statement)
    if instance is None or instance.template is None:
      raise NotFoundError("模板实例不存在。")
    return instance

  async def _list_template_step_runs(self, *, instance_id: UUID) -> list[TaskTemplateStepRun]:
    return list(
      await self._session.scalars(
        select(TaskTemplateStepRun)
        .options(selectinload(TaskTemplateStepRun.template_step))
        .where(TaskTemplateStepRun.instance_id == instance_id)
      )
    )

  async def _resolve_template_watchers(
    self,
    *,
    instance: TaskTemplateInstance,
    initiator: User,
    department_id: UUID | None,
  ) -> list[User]:
    raw_watcher_user_ids = instance.payload.get("watcher_user_ids")
    if not isinstance(raw_watcher_user_ids, list) or not raw_watcher_user_ids:
      return []
    return await resolve_user_targets_from_rule(
      self._session,
      actor=initiator,
      assignee_rule={"type": "user_ids", "user_ids": raw_watcher_user_ids},
      department_id=department_id,
      allow_multiple=True,
    )

  async def _activate_template_step(
    self,
    *,
    instance: TaskTemplateInstance,
    template: TaskTemplate,
    step: TaskTemplateStep,
    initiator: User,
    department_id: UUID | None,
    watcher_users: list[User],
  ) -> tuple[list[Task], list[TaskTemplateStepRun], list[tuple[Task, User]], list[tuple[Task, User]]]:
    assignee_overrides = instance.payload.get("assignee_overrides")
    override_rule = assignee_overrides.get(step.step_key) if isinstance(assignee_overrides, dict) else None
    assignees = await resolve_user_targets_from_rule(
      self._session,
      actor=initiator,
      assignee_rule=dict(override_rule) if isinstance(override_rule, dict) else step.default_assignee_rule,
      department_id=department_id,
      allow_multiple=step.assignment_mode == "fan_out",
    )

    now = datetime.now(UTC)
    created_tasks: list[Task] = []
    created_step_runs: list[TaskTemplateStepRun] = []
    created_bindings: list[tuple[Task, User]] = []
    watcher_bindings: list[tuple[Task, User]] = []
    for assignee in assignees:
      step_run = TaskTemplateStepRun(
        instance_id=instance.id,
        template_step_id=step.id,
        assignee_user_id=assignee.id,
        status="active",
      )
      self._session.add(step_run)
      await self._session.flush()

      due_date = (
        now + timedelta(hours=step.default_due_offset_hours)
        if step.default_due_offset_hours is not None
        else None
      )
      task, resolved_assignee = await self.create_task_record(
        actor=initiator,
        title=f"{template.name} / {step.title}",
        assignee_id=assignee.id,
        description="\n\n".join(value for value in [template.description, step.description] if value) or None,
        department_id=department_id,
        due_date=due_date,
        priority=TaskPriority(str(step.config.get("priority") or TaskPriority.MEDIUM)),
        source_type=TaskSourceType.TEMPLATE,
        extra_metadata={
          "template_id": str(template.id),
          "template_code": template.code,
          "template_instance_id": str(instance.id),
          "template_step_id": str(step.id),
          "template_step_run_id": str(step_run.id),
          "template_step_key": step.step_key,
          "template_step_type": step.step_type,
          "template_step_approval_type": getattr(step, "approval_type", "none"),
          "assignment_mode": step.assignment_mode,
          "join_mode": step.join_mode,
          "instantiation_payload": dict(instance.payload),
        },
        commit=False,
        skip_assignee_permission=True,
        skip_publish_permission=True,
      )
      task.template_instance_id = instance.id
      task.template_step_run_id = step_run.id
      created_tasks.append(task)
      created_step_runs.append(step_run)
      created_bindings.append((task, resolved_assignee))

      for watcher_user in watcher_users:
        if watcher_user.id == task.assignee_id:
          continue
        self._session.add(
          TaskWatcher(
            task_id=task.id,
            user_id=watcher_user.id,
            relation="cc",
            created_by=initiator.id,
          )
        )
        watcher_bindings.append((task, watcher_user))

    return created_tasks, created_step_runs, created_bindings, watcher_bindings

  async def _dispatch_template_activation_notifications(
    self,
    *,
    created_bindings: list[tuple[Task, User]],
    watcher_bindings: list[tuple[Task, User]],
  ) -> None:
    for task, assignee in created_bindings:
      await self._send_assignment_notification(task=task, assignee=assignee)

    if self._notification_service is None:
      return
    for task, watcher_user in watcher_bindings:
      await self._notification_service.send(
        NotificationMessage(
          source_type="task",
          source_id=task.id,
          recipient_user_id=watcher_user.id,
          recipient_email=watcher_user.email,
          message_type="task_cc_added",
          title=f"你被加入任务关注：{task.title}",
          body_text=f"任务「{task.title}」由模板步骤激活，并已将你加入关注列表。",
          channels=list(DEFAULT_USER_NOTIFICATION_CHANNELS),
        )
      )

  async def _activate_ready_template_steps(
    self,
    *,
    instance: TaskTemplateInstance,
  ) -> tuple[list[UUID], list[tuple[Task, User]], list[tuple[Task, User]]]:
    template = instance.template
    initiator = instance.initiator
    if template is None or initiator is None:
      raise NotFoundError("模板实例上下文不完整。")

    department_id = instance.department_id
    watcher_users = await self._resolve_template_watchers(
      instance=instance,
      initiator=initiator,
      department_id=department_id,
    )
    step_runs = await self._list_template_step_runs(instance_id=instance.id)
    step_runs_by_step_id: dict[UUID, list[TaskTemplateStepRun]] = {}
    for step_run in step_runs:
      step_runs_by_step_id.setdefault(step_run.template_step_id, []).append(step_run)

    satisfied_step_ids = {
      step.id
      for step in template.steps
      if self._is_template_step_satisfied(step=step, step_runs=step_runs_by_step_id.get(step.id, []))
    }

    # Build a quick lookup: step_id → step object (for routing_rules evaluation)
    steps_by_id: dict[UUID, TaskTemplateStep] = {step.id: step for step in template.steps}
    # Context for routing_rules evaluation: use the instance payload
    routing_context: dict[str, Any] = instance.payload or {}

    created_task_ids: list[UUID] = []
    created_bindings: list[tuple[Task, User]] = []
    watcher_bindings: list[tuple[Task, User]] = []
    for step in sorted(template.steps, key=lambda current_step: (current_step.sort_order, current_step.created_at)):
      step_step_runs = step_runs_by_step_id.get(step.id, [])
      # Skip steps that are currently being worked on (have an active run)
      if any(sr.status == "active" for sr in step_step_runs):
        continue
      # Skip steps that are already positively satisfied
      if self._is_template_step_satisfied(step=step, step_runs=step_step_runs):
        continue
      dependency_ids = {dependency.depends_on_step_id for dependency in step.dependencies}
      if not dependency_ids.issubset(satisfied_step_ids):
        continue

      # Phase 11-A: evaluate routing_rules from each upstream (dependency) step.
      # If any upstream step has routing_rules, the current step is only activated
      # when its step_key appears in the evaluated routing target set.
      if not self._routing_rules_allow_step_activation(
        step=step,
        dependency_ids=dependency_ids,
        steps_by_id=steps_by_id,
        routing_context=routing_context,
      ):
        continue

      created_tasks, created_step_runs, step_bindings, step_watchers = await self._activate_template_step(
        instance=instance,
        template=template,
        step=step,
        initiator=initiator,
        department_id=department_id,
        watcher_users=watcher_users,
      )
      created_task_ids.extend(task.id for task in created_tasks)
      created_bindings.extend(step_bindings)
      watcher_bindings.extend(step_watchers)
      step_runs_by_step_id[step.id] = created_step_runs

    if template.steps and all(
      self._is_template_step_satisfied(step=step, step_runs=step_runs_by_step_id.get(step.id, []))
      for step in template.steps
    ):
      instance.status = "completed"
      instance.completed_at = datetime.now(UTC)
    elif created_task_ids or step_runs_by_step_id:
      instance.status = "in_progress"

    return created_task_ids, created_bindings, watcher_bindings

  async def activate_template_instance_steps(self, *, instance_id: UUID) -> list[Task]:
    instance = await self._get_template_instance_or_raise(instance_id=instance_id, for_update=True)
    task_ids, created_bindings, watcher_bindings = await self._activate_ready_template_steps(instance=instance)
    await self._session.commit()
    tasks = await self._load_tasks_by_ids(task_ids=task_ids)
    task_map = {task.id: task for task in tasks}
    await self._dispatch_template_activation_notifications(
      created_bindings=[(task_map[task.id], assignee) for task, assignee in created_bindings if task.id in task_map],
      watcher_bindings=[(task_map[task.id], watcher) for task, watcher in watcher_bindings if task.id in task_map],
    )
    return tasks

  async def _progress_template_instance_after_task_completion(self, *, task: Task) -> None:
    if task.template_step_run_id is None:
      return

    step_run = await self._session.scalar(
      select(TaskTemplateStepRun)
      .where(TaskTemplateStepRun.id == task.template_step_run_id)
    )
    if step_run is None:
      return
    instance = await self._get_template_instance_or_raise(instance_id=step_run.instance_id, for_update=True)
    if step_run.status != "completed":
      step_run.status = "completed"
      step_run.completed_at = datetime.now(UTC)

    task_ids, created_bindings, watcher_bindings = await self._activate_ready_template_steps(instance=instance)
    await self._session.commit()
    tasks = await self._load_tasks_by_ids(task_ids=task_ids)
    task_map = {created_task.id: created_task for created_task in tasks}
    await self._dispatch_template_activation_notifications(
      created_bindings=[(task_map[created_task.id], assignee) for created_task, assignee in created_bindings if created_task.id in task_map],
      watcher_bindings=[(task_map[created_task.id], watcher) for created_task, watcher in watcher_bindings if created_task.id in task_map],
    )

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
        channels=list(DEFAULT_USER_NOTIFICATION_CHANNELS),
        payload=build_task_source_payload(task_id=task.id, task_title=task.title),
      )
    )

  async def _ensure_task_dependencies_ready(self, *, task: Task) -> None:
    blocking_dependencies = list(
      await self._session.scalars(
        select(TaskDependency)
        .options(selectinload(TaskDependency.depends_on_task))
        .where(
          TaskDependency.task_id == task.id,
          TaskDependency.dependency_type == "blocks",
        )
      )
    )
    pending_dependency_titles = [
      dependency.depends_on_task.title
      for dependency in blocking_dependencies
      if dependency.depends_on_task is not None and dependency.depends_on_task.status != TaskStatus.DONE
    ]
    if pending_dependency_titles:
      raise ConflictError(
        f"前置任务尚未完成，当前任务不能开始执行：{', '.join(pending_dependency_titles)}。"
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
    skip_publish_permission: bool = False,
  ) -> tuple[Task, User]:
    ensure_active_user(actor)
    if (
      not skip_publish_permission
      and (actor.id != assignee_id or department_id is not None)
    ) and not await can_publish_org_tasks(self._session, actor):
      raise AuthorizationError("当前账号不能发布组织任务。")

    assignee = await self._resolve_assignee_for_task(
      actor=actor,
      assignee_id=assignee_id,
      skip_assignee_permission=skip_assignee_permission,
    )
    resolved_department_id = await self._resolve_task_department_id(
      assignee_id=assignee_id,
      department_id=department_id,
    )

    if self._workflow_graph_engine_enabled() and source_type == TaskSourceType.MANUAL:
      task = await self._create_single_node_workflow_projection(
        actor=actor,
        title=title,
        assignee_id=assignee_id,
        description=description,
        department_id=resolved_department_id,
        due_date=due_date,
        priority=priority,
        dependency_ids=dependency_ids,
        source_type=source_type,
        extra_metadata=extra_metadata,
      )
      if commit:
        await self._session.commit()
        await self._session.refresh(task)
        await self._send_assignment_notification(task=task, assignee=assignee)
      return task, assignee

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
        "template_instance_id": str(task.template_instance_id) if task.template_instance_id is not None else None,
        "template_step_run_id": str(task.template_step_run_id) if task.template_step_run_id is not None else None,
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
        selectinload(Task.creator).selectinload(User.profile),
        selectinload(Task.assignee).selectinload(User.profile),
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

  async def _task_step_context_map(self, *, task_ids: list[UUID]) -> dict[UUID, tuple[str, str | None]]:
    if not task_ids:
      return {}

    step_runs = list(
      await self._session.scalars(
        select(WorkflowStepRun)
        .join(WorkflowStepRun.instance)
        .join(WorkflowStepRun.step)
        .options(
          selectinload(WorkflowStepRun.assignee).selectinload(User.profile),
          selectinload(WorkflowStepRun.step),
          selectinload(WorkflowStepRun.instance),
        )
        .where(
          WorkflowInstance.source_type == "task",
          WorkflowInstance.source_id.in_(task_ids),
          WorkflowStepRun.status == WorkflowStepRunStatus.PENDING,
        )
        .order_by(WorkflowInstance.source_id.asc(), WorkflowStepRun.created_at.asc())
      )
    )

    context_map: dict[UUID, tuple[str, str | None]] = {}
    pending_counts: dict[UUID, int] = {}
    first_step_run_by_task: dict[UUID, WorkflowStepRun] = {}
    for step_run in step_runs:
      instance = step_run.instance
      step = step_run.step
      if instance is None or step is None or instance.source_id is None:
        continue
      task_id = instance.source_id
      pending_counts[task_id] = pending_counts.get(task_id, 0) + 1
      first_step_run_by_task.setdefault(task_id, step_run)

    for task_id, step_run in first_step_run_by_task.items():
      step = step_run.step
      assignee = step_run.assignee
      pending_count = pending_counts.get(task_id, 1)
      if pending_count > 1:
        current_handler_label = f"{pending_count} 人待处理"
      elif assignee is not None:
        current_handler_label = assignee.profile.real_name if assignee.profile and assignee.profile.real_name else assignee.email
      else:
        current_handler_label = None
      context_map[task_id] = (
        f"审批：{step.name}" if step is not None else "审批处理中",
        current_handler_label,
      )
    return context_map

  def _build_inbox_entry(
    self,
    *,
    task: Task,
    step_context_map: dict[UUID, tuple[str, str | None]],
  ) -> TaskInboxEntry:
    current_stage_label, current_handler_label = step_context_map.get(
      task.id,
      self._manual_graph_context(task=task)
      or (
        f"任务：{_task_status_label(task.status)}",
        _user_display_label(task.assignee),
      ),
    )
    return TaskInboxEntry(
      task_id=task.id,
      title=task.title,
      priority=task.priority,
      status=task.status,
      due_date=task.due_date,
      department_name=task.department.name if task.department is not None else None,
      current_stage_label=current_stage_label,
      current_handler_label=current_handler_label,
    )

  def _build_tracking_entry(
    self,
    *,
    task: Task,
    relation_types: list[str],
    step_context_map: dict[UUID, tuple[str, str | None]],
  ) -> TaskTrackingEntry:
    metadata = self._copy_task_metadata(task)
    review_quality_score = None
    if metadata.get("latest_review_quality_score") is not None:
      review_quality_score = self._read_int_metadata(metadata, "latest_review_quality_score")

    current_stage_label, current_handler_label = step_context_map.get(
      task.id,
      self._manual_graph_context(task=task)
      or (
        f"任务：{_task_status_label(task.status)}",
        _user_display_label(task.assignee),
      ),
    )
    return TaskTrackingEntry(
      task_id=task.id,
      title=task.title,
      priority=task.priority,
      status=task.status,
      due_date=task.due_date,
      department_name=task.department.name if task.department is not None else None,
      relation_types=relation_types,
      current_stage_label=current_stage_label,
      current_handler_label=current_handler_label,
      latest_deliverable_submitted_at=self._read_datetime_metadata(metadata, "latest_deliverable_submitted_at"),
      rework_count=self._read_int_metadata(metadata, "rework_count"),
      review_quality_score=review_quality_score,
      is_pending_review=task.status == TaskStatus.REVIEW,
    )

  @staticmethod
  def _build_history_entry(
    *,
    task: Task,
    relation_types: list[str],
  ) -> TaskHistoryEntry:
    return TaskHistoryEntry(
      task_id=task.id,
      title=task.title,
      priority=task.priority,
      due_date=task.due_date,
      completed_at=task.completed_at,
      department_name=task.department.name if task.department is not None else None,
      relation_types=relation_types,
      source_type=task.source_type,
    )

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

  @staticmethod
  def _read_uuid_metadata(metadata: dict[str, Any], key: str) -> UUID | None:
    raw_value = metadata.get(key)
    if not isinstance(raw_value, str) or not raw_value:
      return None
    try:
      return UUID(raw_value)
    except ValueError:
      return None

  @staticmethod
  def _copy_task_metadata(task: Task) -> dict[str, Any]:
    return dict(task.extra_metadata or {})

  @staticmethod
  def _read_str_metadata(metadata: dict[str, Any], key: str) -> str | None:
    raw_value = metadata.get(key)
    if isinstance(raw_value, str) and raw_value.strip():
      return raw_value.strip()
    return None

  @staticmethod
  def _read_int_metadata(metadata: dict[str, Any], key: str, *, default: int = 0) -> int:
    raw_value = metadata.get(key)
    if isinstance(raw_value, bool):
      return int(raw_value)
    if isinstance(raw_value, int):
      return raw_value
    if isinstance(raw_value, str):
      try:
        return int(raw_value)
      except ValueError:
        return default
    return default

  @staticmethod
  def _read_datetime_metadata(metadata: dict[str, Any], key: str) -> datetime | None:
    raw_value = metadata.get(key)
    if not isinstance(raw_value, str) or not raw_value.strip():
      return None
    try:
      return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
      return None
  async def _load_workflow_graph_projection(
    self,
    *,
    task: Task,
  ) -> tuple[WorkflowGraphInstance | None, WorkflowNodeInstance | None]:
    metadata = self._copy_task_metadata(task)
    instance_id = self._read_uuid_metadata(metadata, "workflow_graph_instance_id")
    node_id = self._read_uuid_metadata(metadata, "workflow_node_instance_id")

    instance: WorkflowGraphInstance | None = None
    node_instance: WorkflowNodeInstance | None = None
    if instance_id is not None:
      instance = await self._session.get(WorkflowGraphInstance, instance_id)
    if instance is None:
      instance = await self._session.scalar(
        select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == task.id)
      )

    if node_id is not None:
      node_instance = await self._session.get(WorkflowNodeInstance, node_id)
      if node_instance is not None and instance is not None and node_instance.instance_id != instance.id:
        node_instance = None
    if node_instance is None and instance is not None:
      node_instance = await self._session.scalar(
        select(WorkflowNodeInstance)
        .where(WorkflowNodeInstance.instance_id == instance.id)
        .order_by(WorkflowNodeInstance.created_at.asc())
      )

    return instance, node_instance

  def _uses_graph_projection(self, *, task: Task) -> bool:
    metadata = self._copy_task_metadata(task)
    return (
      self._read_uuid_metadata(metadata, "workflow_graph_instance_id") is not None
      and self._read_uuid_metadata(metadata, "workflow_node_instance_id") is not None
    )

  def _uses_graph_handshake_cycle(self, *, task: Task) -> bool:
    return task.source_type == TaskSourceType.MANUAL and self._uses_graph_projection(task=task)

  def _handshake_state_for_task(self, *, task: Task) -> str | None:
    if not self._uses_graph_handshake_cycle(task=task):
      return None

    metadata = self._copy_task_metadata(task)
    state = self._read_str_metadata(metadata, "workflow_handshake_state")
    if state in {HANDSHAKE_ASSIGNED, HANDSHAKE_ACCEPTED, HANDSHAKE_REJECTED}:
      return state
    if task.status == TaskStatus.TODO:
      return HANDSHAKE_ACCEPTED
    return None

  def _manual_graph_current_handler_id(self, *, task: Task) -> UUID | None:
    if not self._uses_graph_handshake_cycle(task=task):
      return None
    handshake_state = self._handshake_state_for_task(task=task)
    if task.status == TaskStatus.REVIEW:
      return task.creator_id
    if task.status == TaskStatus.TODO and handshake_state == HANDSHAKE_REJECTED:
      return task.creator_id
    return task.assignee_id

  def _manual_graph_context(self, *, task: Task) -> tuple[str, str | None] | None:
    if not self._uses_graph_handshake_cycle(task=task):
      return None

    metadata = self._copy_task_metadata(task)
    latest_action = self._read_str_metadata(metadata, "latest_handshake_action")
    handshake_state = self._handshake_state_for_task(task=task)
    assignee_label = _user_display_label(task.assignee)
    creator_label = _user_display_label(task.creator)

    if task.status == TaskStatus.TODO:
      if handshake_state == HANDSHAKE_REJECTED:
        return ("任务：已拒绝待调整", creator_label)
      if latest_action == "delegated":
        return ("任务：已转办待确认", assignee_label)
      if latest_action == "reassigned":
        return ("任务：重新派发待确认", assignee_label)
      if handshake_state == HANDSHAKE_ACCEPTED:
        return ("任务：已接受待开工", assignee_label)
      return ("任务：待确认", assignee_label)

    if task.status == TaskStatus.DOING:
      latest_review_state = self._read_str_metadata(metadata, "latest_review_state")
      if latest_review_state == "returned_for_rework":
        return ("任务：返工中", assignee_label)
      return (f"任务：{_task_status_label(task.status)}", assignee_label)

    if task.status == TaskStatus.REVIEW:
      return ("任务：待验收", creator_label)

    return (f"任务：{_task_status_label(task.status)}", assignee_label)

  async def _uses_graph_deliverable_review_cycle(self, *, task: Task) -> bool:
    if task.source_type != TaskSourceType.MANUAL:
      return False

    instance, node_instance = await self._load_workflow_graph_projection(task=task)
    return instance is not None and node_instance is not None

  async def _validate_task_attachment_ids(
    self,
    *,
    task_id: UUID,
    attachment_ids: list[UUID],
  ) -> list[str]:
    if not attachment_ids:
      return []

    stored_attachment_ids = set(
      await self._session.scalars(
        select(Attachment.id).where(
          Attachment.id.in_(attachment_ids),
          Attachment.status != AttachmentStatus.DELETED,
          Attachment.links.any(
            Attachment.target_type == AttachmentTargetType.TASK,
            Attachment.target_id == task_id,
          ),
        )
      )
    )
    if stored_attachment_ids != set(attachment_ids):
      raise NotFoundError("存在无效的任务附件，无法作为交付物提交。")
    return [str(attachment_id) for attachment_id in attachment_ids]

  async def _upsert_task_deliverable(
    self,
    *,
    task: Task,
    actor: User,
    summary: str | None,
    attachment_ids: list[str],
    submitted_at: datetime,
  ) -> None:
    instance, node_instance = await self._load_workflow_graph_projection(task=task)
    if instance is None or node_instance is None:
      return

    submission_entry: dict[str, Any] = {
      "submitted_at": submitted_at.isoformat(),
      "submitted_by_user_id": str(actor.id),
      "summary": summary,
      "attachment_ids": attachment_ids,
    }
    deliverable = await self._session.scalar(
      select(WorkflowDeliverable).where(WorkflowDeliverable.node_instance_id == node_instance.id)
    )
    if deliverable is None:
      deliverable = WorkflowDeliverable(
        node_instance_id=node_instance.id,
        submitted_by_user_id=actor.id,
        submitted_at=submitted_at,
        summary=summary,
        payload={
          "latest_submission": submission_entry,
          "submission_history": [submission_entry],
        },
        signature=f"task:{task.id}:submission:1",
      )
      self._session.add(deliverable)
      await self._session.flush()
      return

    payload = dict(deliverable.payload or {})
    history_raw = payload.get("submission_history")
    history: list[dict[str, Any]] = list(history_raw) if isinstance(history_raw, list) else []
    history.append(submission_entry)
    payload["latest_submission"] = submission_entry
    payload["submission_history"] = history
    deliverable.submitted_by_user_id = actor.id
    deliverable.submitted_at = submitted_at
    deliverable.summary = summary
    deliverable.payload = payload
    deliverable.signature = f"task:{task.id}:submission:{len(history)}"

  async def _record_task_review_result(
    self,
    *,
    task: Task,
    actor: User,
    action: str,
    comment: str | None,
    reviewed_at: datetime,
    rework_count: int | None = None,
  ) -> None:
    instance, node_instance = await self._load_workflow_graph_projection(task=task)
    if instance is None or node_instance is None:
      return

    deliverable = await self._session.scalar(
      select(WorkflowDeliverable).where(WorkflowDeliverable.node_instance_id == node_instance.id)
    )
    if deliverable is None:
      return

    review_entry: dict[str, Any] = {
      "action": action,
      "comment": comment,
      "reviewed_at": reviewed_at.isoformat(),
      "reviewed_by_user_id": str(actor.id),
    }
    if rework_count is not None:
      review_entry["rework_count"] = rework_count

    payload = dict(deliverable.payload or {})
    payload["latest_review"] = review_entry
    if rework_count is not None:
      payload["rework_count"] = rework_count
    deliverable.payload = payload

  async def _sync_graph_projection_for_task_status(
    self,
    *,
    task: Task,
    target_status: TaskStatus,
    reference_time: datetime,
    force_business_state: WorkflowNodeBusinessState | None = None,
  ) -> None:
    instance, node_instance = await self._load_workflow_graph_projection(task=task)
    if instance is None or node_instance is None:
      return

    instance.status = WorkflowGraphInstanceStatus.ACTIVE
    instance.completed_at = None
    instance.current_node_key = node_instance.node_key

    if target_status == TaskStatus.DOING:
      node_instance.engine_state = WorkflowNodeEngineState.ACKNOWLEDGED
      node_instance.acknowledged_at = node_instance.acknowledged_at or reference_time
      node_instance.completed_at = None
      node_instance.business_state = force_business_state or WorkflowNodeBusinessState.DOING
      return

    if target_status == TaskStatus.REVIEW:
      node_instance.engine_state = WorkflowNodeEngineState.ACKNOWLEDGED
      node_instance.acknowledged_at = node_instance.acknowledged_at or reference_time
      node_instance.completed_at = None
      node_instance.business_state = force_business_state or WorkflowNodeBusinessState.PENDING_REVIEW
      return

    if target_status == TaskStatus.DONE:
      node_instance.engine_state = WorkflowNodeEngineState.COMPLETED
      node_instance.acknowledged_at = node_instance.acknowledged_at or reference_time
      node_instance.completed_at = reference_time
      node_instance.business_state = force_business_state or WorkflowNodeBusinessState.DONE
      instance.status = WorkflowGraphInstanceStatus.COMPLETED
      instance.completed_at = reference_time
      instance.current_node_key = None

  async def _sync_graph_projection_for_handshake_state(
    self,
    *,
    task: Task,
    business_state: WorkflowNodeBusinessState,
    reference_time: datetime,
    assignee_id: UUID | None = None,
    reset_acknowledged_at: bool = False,
  ) -> None:
    instance, node_instance = await self._load_workflow_graph_projection(task=task)
    if instance is None or node_instance is None:
      return

    instance.status = WorkflowGraphInstanceStatus.ACTIVE
    instance.completed_at = None
    instance.current_node_key = node_instance.node_key
    node_instance.completed_at = None
    if assignee_id is not None:
      node_instance.assignee_user_id = assignee_id

    if business_state == WorkflowNodeBusinessState.ASSIGNED:
      node_instance.engine_state = WorkflowNodeEngineState.ACTIVATED
      node_instance.business_state = WorkflowNodeBusinessState.ASSIGNED
      if reset_acknowledged_at:
        node_instance.acknowledged_at = None
      return

    node_instance.engine_state = WorkflowNodeEngineState.ACKNOWLEDGED
    node_instance.business_state = business_state
    node_instance.acknowledged_at = reference_time

  async def _ensure_task_assignee_or_manager(self, *, actor: User, task: Task) -> None:
    if actor.role in MANAGEMENT_ROLES or actor.id == task.assignee_id:
      return
    raise AuthorizationError("当前账号不能提交该任务交付物。")

  async def _ensure_task_reviewer(self, *, actor: User, task: Task) -> None:
    if actor.role in MANAGEMENT_ROLES or actor.id == task.creator_id:
      return
    raise AuthorizationError("当前账号不能验收该任务。")

  async def _ensure_task_handshake_actor(self, *, actor: User, task: Task) -> None:
    if actor.role in MANAGEMENT_ROLES or actor.id == task.assignee_id:
      return
    raise AuthorizationError("当前账号不能处理该任务的握手动作。")

  async def _resolve_delegate_assignee(
    self,
    *,
    actor: User,
    task: Task,
    assignee_id: UUID,
  ) -> User:
    assignee = await self._session.get(User, assignee_id)
    if assignee is None:
      raise NotFoundError("转办目标不存在。")
    ensure_active_user(assignee)
    if assignee.id == task.assignee_id:
      raise ConflictError("转办目标不能与当前执行人相同。")
    if actor.id != task.assignee_id and not await can_manage_assignee(self._session, actor, assignee_id):
      raise AuthorizationError("当前账号不能转办给该执行人。")
    return assignee

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

  async def list_task_inbox(self, *, actor: User, limit: int = 10) -> list[TaskInboxEntry]:
    ensure_active_user(actor)

    pending_workflow_task_ids = list(
      await self._session.scalars(
        select(WorkflowInstance.source_id)
        .join(WorkflowInstance.step_runs)
        .where(
          WorkflowInstance.source_type == "task",
          WorkflowInstance.source_id.is_not(None),
          WorkflowStepRun.assignee_user_id == actor.id,
          WorkflowStepRun.status == WorkflowStepRunStatus.PENDING,
        )
      )
    )
    candidate_task_ids = {
      task_id
      for task_id in pending_workflow_task_ids
      if task_id is not None
    }
    tasks = list(
      await self._session.scalars(
        (await self._build_visible_task_statement(actor=actor)).where(Task.status != TaskStatus.DONE)
      )
    )
    step_context_map = await self._task_step_context_map(task_ids=[task.id for task in tasks])
    inbox_tasks = [
      task
      for task in tasks
      if task.id in candidate_task_ids
      or (
        self._uses_graph_handshake_cycle(task=task)
        and self._manual_graph_current_handler_id(task=task) == actor.id
      )
      or (
        not self._uses_graph_handshake_cycle(task=task)
        and task.assignee_id == actor.id
      )
    ]
    sorted_tasks = sorted(
      inbox_tasks,
      key=lambda task: (
        task.due_date is None,
        _normalize_datetime(task.due_date) if task.due_date is not None else datetime.max.replace(tzinfo=UTC),
        _task_priority_sort_value(task.priority),
        -int(task.created_at.timestamp()),
      ),
    )
    return [
      self._build_inbox_entry(task=task, step_context_map=step_context_map)
      for task in sorted_tasks[:limit]
    ]

  async def list_task_tracking(self, *, actor: User, limit: int = 10) -> list[TaskTrackingEntry]:
    ensure_active_user(actor)

    workflow_related_task_ids = {
      task_id
      for task_id in list(
        await self._session.scalars(
          select(WorkflowInstance.source_id)
          .outerjoin(WorkflowInstance.step_runs)
          .where(
            WorkflowInstance.source_type == "task",
            WorkflowInstance.source_id.is_not(None),
            or_(
              WorkflowInstance.initiator_user_id == actor.id,
              WorkflowStepRun.assignee_user_id == actor.id,
            ),
          )
        )
      )
    }

    tracking_filters = [
      Task.creator_id == actor.id,
      Task.assignee_id == actor.id,
      Task.watchers.any(TaskWatcher.user_id == actor.id),
    ]
    if workflow_related_task_ids:
      tracking_filters.append(Task.id.in_(workflow_related_task_ids))

    tasks = list(
      await self._session.scalars(
        select(Task)
        .options(
          selectinload(Task.creator).selectinload(User.profile),
          selectinload(Task.assignee).selectinload(User.profile),
          selectinload(Task.department),
          selectinload(Task.watchers),
        )
        .where(or_(*tracking_filters))
        .order_by(Task.updated_at.desc())
      )
    )

    step_context_map = await self._task_step_context_map(task_ids=[task.id for task in tasks])
    tracking_entries: list[TaskTrackingEntry] = []
    inbox_task_ids = {entry.task_id for entry in await self.list_task_inbox(actor=actor, limit=limit * 2)}
    for task in tasks:
      if task.id in inbox_task_ids:
        continue
      relation_types: list[str] = []
      if task.creator_id == actor.id:
        relation_types.append("发起")
      if task.assignee_id == actor.id:
        relation_types.append("执行")
      if any(watcher.user_id == actor.id for watcher in task.watchers):
        relation_types.append("关注")
      if task.id in workflow_related_task_ids:
        relation_types.append("流程")
      tracking_entries.append(
        self._build_tracking_entry(
          task=task,
          relation_types=relation_types or ["相关"],
          step_context_map=step_context_map,
        )
      )

    sorted_entries = sorted(
      tracking_entries,
      key=lambda item: (
        item.status == TaskStatus.DONE,
        item.due_date is None,
        _normalize_datetime(item.due_date) if item.due_date is not None else datetime.max.replace(tzinfo=UTC),
        _task_priority_sort_value(item.priority),
      ),
    )
    return sorted_entries[:limit]

  async def list_task_history(self, *, actor: User, limit: int = 20) -> list[TaskHistoryEntry]:
    ensure_active_user(actor)

    workflow_related_task_ids = {
      task_id
      for task_id in list(
        await self._session.scalars(
          select(WorkflowInstance.source_id)
          .outerjoin(WorkflowInstance.step_runs)
          .where(
            WorkflowInstance.source_type == "task",
            WorkflowInstance.source_id.is_not(None),
            or_(
              WorkflowInstance.initiator_user_id == actor.id,
              WorkflowStepRun.assignee_user_id == actor.id,
            ),
          )
        )
      )
      if task_id is not None
    }
    history_filters = [
      Task.creator_id == actor.id,
      Task.assignee_id == actor.id,
      Task.watchers.any(TaskWatcher.user_id == actor.id),
    ]
    if workflow_related_task_ids:
      history_filters.append(Task.id.in_(workflow_related_task_ids))

    tasks = list(
      await self._session.scalars(
        select(Task)
        .options(
          selectinload(Task.department),
          selectinload(Task.watchers),
        )
        .where(or_(*history_filters), Task.status == TaskStatus.DONE)
        .order_by(Task.completed_at.desc(), Task.updated_at.desc())
      )
    )

    entries: list[TaskHistoryEntry] = []
    for task in tasks:
      relation_types: list[str] = []
      if task.creator_id == actor.id:
        relation_types.append("发起")
      if task.assignee_id == actor.id:
        relation_types.append("执行")
      if any(watcher.user_id == actor.id for watcher in task.watchers):
        relation_types.append("关注")
      if task.id in workflow_related_task_ids:
        relation_types.append("流程")
      entries.append(self._build_history_entry(task=task, relation_types=relation_types or ["相关"]))

    return entries[:limit]

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

    if assignee_id is not None and assignee_id != previous_assignee_id and self._uses_graph_handshake_cycle(task=task):
      metadata = self._copy_task_metadata(task)
      metadata.update(
        {
          "workflow_handshake_state": HANDSHAKE_ASSIGNED,
          "latest_handshake_action": "reassigned",
          "latest_handshake_actor_user_id": str(actor.id),
          "latest_delegate_to_user_id": str(assignee_id),
        }
      )
      task.extra_metadata = metadata
      if task.status == TaskStatus.TODO:
        await self._sync_graph_projection_for_handshake_state(
          task=task,
          business_state=WorkflowNodeBusinessState.ASSIGNED,
          reference_time=task.updated_at,
          assignee_id=assignee_id,
          reset_acknowledged_at=True,
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
            channels=list(DEFAULT_USER_NOTIFICATION_CHANNELS),
            payload=build_task_source_payload(task_id=task.id, task_title=task.title),
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
    if self._uses_graph_handshake_cycle(task=task):
      handshake_state = self._handshake_state_for_task(task=task)
      if task.status == TaskStatus.TODO and target_status == TaskStatus.DOING and handshake_state != HANDSHAKE_ACCEPTED:
        raise ConflictError("图引擎任务必须先由执行人接受任务，才能开始处理。")
    if (
      self._uses_graph_handshake_cycle(task=task)
      and target_status in {TaskStatus.REVIEW, TaskStatus.DONE}
    ):
      raise ConflictError("图引擎任务必须通过提交交付物和验收动作推进到评审或完成状态。")
    if target_status == TaskStatus.DOING:
      await self._ensure_task_dependencies_ready(task=task)

    previous_status = task.status
    now = datetime.now(UTC)
    task.status = target_status
    task.updated_at = now
    if target_status == TaskStatus.DOING and task.started_at is None:
      task.started_at = now
    if target_status == TaskStatus.DONE:
      task.completed_at = now

    await self._sync_graph_projection_for_task_status(
      task=task,
      target_status=target_status,
      reference_time=now,
    )

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
    if target_status == TaskStatus.DONE:
      await self._progress_template_instance_after_task_completion(task=task)
    return task

  async def submit_task_deliverable(
    self,
    *,
    actor: User,
    task_id: UUID,
    summary: str | None,
    attachment_ids: list[UUID] | None = None,
  ) -> Task:
    task = await self.get_task(actor=actor, task_id=task_id)
    await self._ensure_task_assignee_or_manager(actor=actor, task=task)
    if task.status != TaskStatus.DOING:
      raise ConflictError("只有进行中的任务才能提交交付物。")

    normalized_summary = summary.strip() if summary is not None else None
    validated_attachment_ids = await self._validate_task_attachment_ids(
      task_id=task.id,
      attachment_ids=attachment_ids or [],
    )
    if not normalized_summary and not validated_attachment_ids:
      raise ConflictError("交付说明或附件至少提供一项。")

    now = datetime.now(UTC)
    await self._upsert_task_deliverable(
      task=task,
      actor=actor,
      summary=normalized_summary,
      attachment_ids=validated_attachment_ids,
      submitted_at=now,
    )

    metadata = self._copy_task_metadata(task)
    metadata.update(
      {
        "latest_deliverable_summary": normalized_summary,
        "latest_deliverable_attachment_ids": validated_attachment_ids,
        "latest_deliverable_submitted_at": now.isoformat(),
        "latest_deliverable_submitted_by_user_id": str(actor.id),
        "latest_review_state": "pending_review",
      }
    )
    task.extra_metadata = metadata
    task.status = TaskStatus.REVIEW
    task.updated_at = now
    task.started_at = task.started_at or now
    task.completed_at = None
    await self._sync_graph_projection_for_task_status(
      task=task,
      target_status=TaskStatus.REVIEW,
      reference_time=now,
    )
    await self._create_task_log(
      task_id=task.id,
      operator_id=actor.id,
      action_type=TaskActionType.STATUS_CHANGED,
      from_status=TaskStatus.DOING,
      to_status=TaskStatus.REVIEW,
      detail={
        "action": "submit_deliverable",
        "summary": normalized_summary,
        "attachment_ids": validated_attachment_ids,
        "status": TaskStatus.REVIEW.value,
      },
    )
    await self._session.commit()
    await self._session.refresh(task)
    return task

  async def accept_task_assignment(
    self,
    *,
    actor: User,
    task_id: UUID,
  ) -> Task:
    task = await self.get_task(actor=actor, task_id=task_id)
    if not self._uses_graph_handshake_cycle(task=task):
      raise ConflictError("当前任务不使用图引擎握手流程。")
    await self._ensure_task_handshake_actor(actor=actor, task=task)
    if task.status != TaskStatus.TODO:
      raise ConflictError("只有待处理任务才能执行接受动作。")

    handshake_state = self._handshake_state_for_task(task=task)
    if handshake_state != HANDSHAKE_ASSIGNED:
      raise ConflictError("当前任务已不处于待确认状态。")

    now = datetime.now(UTC)
    metadata = self._copy_task_metadata(task)
    metadata.update(
      {
        "workflow_handshake_state": HANDSHAKE_ACCEPTED,
        "latest_handshake_action": HANDSHAKE_ACCEPTED,
        "latest_handshake_actor_user_id": str(actor.id),
        "latest_handshake_at": now.isoformat(),
      }
    )
    task.extra_metadata = metadata
    task.updated_at = now
    await self._sync_graph_projection_for_handshake_state(
      task=task,
      business_state=WorkflowNodeBusinessState.ACCEPTED,
      reference_time=now,
    )
    await self._create_task_log(
      task_id=task.id,
      operator_id=actor.id,
      action_type=TaskActionType.ASSIGNED,
      detail={
        "action": HANDSHAKE_ACCEPTED,
        "status": task.status.value,
      },
    )
    await self._session.commit()
    await self._session.refresh(task)
    return task

  async def reject_task_assignment(
    self,
    *,
    actor: User,
    task_id: UUID,
    reason: str,
  ) -> Task:
    task = await self.get_task(actor=actor, task_id=task_id)
    if not self._uses_graph_handshake_cycle(task=task):
      raise ConflictError("当前任务不使用图引擎握手流程。")
    await self._ensure_task_handshake_actor(actor=actor, task=task)
    if task.status != TaskStatus.TODO:
      raise ConflictError("只有待处理任务才能执行退回协商。")

    normalized_reason = reason.strip()
    if not normalized_reason:
      raise ConflictError("退回协商时必须填写原因。")

    handshake_state = self._handshake_state_for_task(task=task)
    if handshake_state not in {HANDSHAKE_ASSIGNED, HANDSHAKE_ACCEPTED}:
      raise ConflictError("当前任务不能执行退回协商。")

    now = datetime.now(UTC)
    metadata = self._copy_task_metadata(task)
    metadata.update(
      {
        "workflow_handshake_state": HANDSHAKE_REJECTED,
        "latest_handshake_action": HANDSHAKE_REJECTED,
        "latest_handshake_actor_user_id": str(actor.id),
        "latest_handshake_at": now.isoformat(),
        "latest_reject_reason": normalized_reason,
      }
    )
    task.extra_metadata = metadata
    task.updated_at = now
    await self._sync_graph_projection_for_handshake_state(
      task=task,
      business_state=WorkflowNodeBusinessState.REJECTED,
      reference_time=now,
    )
    await self._create_task_log(
      task_id=task.id,
      operator_id=actor.id,
      action_type=TaskActionType.ASSIGNED,
      detail={
        "action": HANDSHAKE_REJECTED,
        "reason": normalized_reason,
        "status": task.status.value,
      },
    )
    await self._session.commit()
    await self._session.refresh(task)
    return task

  async def delegate_task_assignment(
    self,
    *,
    actor: User,
    task_id: UUID,
    assignee_id: UUID,
    reason: str,
  ) -> Task:
    task = await self.get_task(actor=actor, task_id=task_id)
    if not self._uses_graph_handshake_cycle(task=task):
      raise ConflictError("当前任务不使用图引擎握手流程。")
    await self._ensure_task_handshake_actor(actor=actor, task=task)
    if task.status != TaskStatus.TODO:
      raise ConflictError("只有待处理任务才能执行转办。")

    normalized_reason = reason.strip()
    if not normalized_reason:
      raise ConflictError("转办时必须填写原因。")

    handshake_state = self._handshake_state_for_task(task=task)
    if handshake_state not in {HANDSHAKE_ASSIGNED, HANDSHAKE_ACCEPTED}:
      raise ConflictError("当前任务不能执行转办。")

    next_assignee = await self._resolve_delegate_assignee(actor=actor, task=task, assignee_id=assignee_id)
    previous_assignee_id = task.assignee_id
    now = datetime.now(UTC)
    task.assignee_id = next_assignee.id
    task.updated_at = now
    metadata = self._copy_task_metadata(task)
    metadata.update(
      {
        "workflow_handshake_state": HANDSHAKE_ASSIGNED,
        "latest_handshake_action": "delegated",
        "latest_handshake_actor_user_id": str(actor.id),
        "latest_handshake_at": now.isoformat(),
        "latest_delegate_reason": normalized_reason,
        "latest_delegate_from_user_id": str(previous_assignee_id),
        "latest_delegate_to_user_id": str(next_assignee.id),
      }
    )
    task.extra_metadata = metadata
    await self._sync_graph_projection_for_handshake_state(
      task=task,
      business_state=WorkflowNodeBusinessState.ASSIGNED,
      reference_time=now,
      assignee_id=next_assignee.id,
      reset_acknowledged_at=True,
    )
    await self._create_task_log(
      task_id=task.id,
      operator_id=actor.id,
      action_type=TaskActionType.ASSIGNED,
      detail={
        "action": "delegated",
        "reason": normalized_reason,
        "previous_assignee_id": str(previous_assignee_id),
        "assignee_id": str(next_assignee.id),
        "assignee_email": next_assignee.email,
        "status": task.status.value,
      },
    )
    await self._session.commit()
    await self._session.refresh(task)
    await self._send_assignment_notification(task=task, assignee=next_assignee)
    return task

  async def review_task_deliverable(
    self,
    *,
    actor: User,
    task_id: UUID,
    approve: bool,
    comment: str | None = None,
    quality_score: int | None = None,
  ) -> Task:
    task = await self.get_task(actor=actor, task_id=task_id)
    await self._ensure_task_reviewer(actor=actor, task=task)
    if task.status != TaskStatus.REVIEW:
      raise ConflictError("只有评审中的任务才能执行验收动作。")

    normalized_comment = comment.strip() if comment is not None else None
    now = datetime.now(UTC)
    metadata = self._copy_task_metadata(task)
    metadata.update(
      {
        "latest_reviewed_at": now.isoformat(),
        "latest_reviewer_user_id": str(actor.id),
      }
    )

    if approve:
      if quality_score is not None and quality_score not in {1, 2, 3, 4, 5}:
        raise ConflictError("完成质量评分必须在 1 到 5 之间。")
      metadata.update(
        {
          "latest_review_state": "approved",
          "latest_review_comment": normalized_comment,
          "latest_review_quality_score": quality_score,
        }
      )
      task.extra_metadata = metadata
      task.status = TaskStatus.DONE
      task.updated_at = now
      task.completed_at = now
      await self._record_task_review_result(
        task=task,
        actor=actor,
        action="approve_completion",
        comment=normalized_comment,
        reviewed_at=now,
      )
      await self._sync_graph_projection_for_task_status(
        task=task,
        target_status=TaskStatus.DONE,
        reference_time=now,
      )
      await self._create_task_log(
        task_id=task.id,
        operator_id=actor.id,
        action_type=TaskActionType.STATUS_CHANGED,
        from_status=TaskStatus.REVIEW,
        to_status=TaskStatus.DONE,
        detail={
          "action": "approve_completion",
          "comment": normalized_comment,
          "quality_score": quality_score,
          "status": TaskStatus.DONE.value,
        },
      )
      await self._session.commit()
      await self._session.refresh(task)
      await self._progress_template_instance_after_task_completion(task=task)
      return task

    if not normalized_comment:
      raise ConflictError("打回返工时必须填写返工原因。")

    rework_count = self._read_int_metadata(metadata, "rework_count") + 1
    metadata.update(
      {
        "latest_review_state": "returned_for_rework",
        "latest_review_comment": normalized_comment,
        "latest_rework_reason": normalized_comment,
        "rework_count": rework_count,
      }
    )
    task.extra_metadata = metadata
    task.status = TaskStatus.DOING
    task.updated_at = now
    task.completed_at = None
    task.started_at = task.started_at or now
    await self._record_task_review_result(
      task=task,
      actor=actor,
      action="return_for_rework",
      comment=normalized_comment,
      reviewed_at=now,
      rework_count=rework_count,
    )
    await self._sync_graph_projection_for_task_status(
      task=task,
      target_status=TaskStatus.DOING,
      reference_time=now,
      force_business_state=WorkflowNodeBusinessState.RETURNED_FOR_REWORK,
    )
    await self._create_task_log(
      task_id=task.id,
      operator_id=actor.id,
      action_type=TaskActionType.STATUS_CHANGED,
      from_status=TaskStatus.REVIEW,
      to_status=TaskStatus.DOING,
      detail={
        "action": "return_for_rework",
        "comment": normalized_comment,
        "rework_count": rework_count,
        "status": TaskStatus.DOING.value,
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
            channels=list(DEFAULT_USER_NOTIFICATION_CHANNELS),
            payload=build_task_source_payload(task_id=task.id, task_title=task.title),
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
