from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Callable, Generic, TypeVar
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
  AttachmentStatus,
  AttachmentTargetType,
  AttachmentVisibility,
  CommentFormat,
  DEFAULT_USER_NOTIFICATION_CHANNELS,
  TaskActionType,
  TaskAssignmentMode,
  TaskPriority,
  TaskSourceType,
  TaskStatus,
  UserRole,
  UserStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
  WorkflowGraphInstanceStatus,
  WorkflowStepRunStatus,
)
from app.core.config import Settings
from app.core.exceptions import AppValidationError, AuthorizationError, ConflictError, NotFoundError
from app.models import (
  Attachment,
  AttachmentLink,
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
  WorkflowGraphTemplateNode,
  WorkflowHumanTaskLink,
  WorkflowInstance,
  WorkflowNodeInstance,
  WorkflowStep,
  WorkflowStepRun,
)
from app.schemas.messages import NotificationMessage
from app.services.notification_source import build_task_source_payload
from app.services.workflow_graph_service import SingleNodeWorkflowSeed, WorkflowGraphService
from app.services.human_task_coordinator import HumanTaskCoordinator
from app.services.workflow_node_config_helpers import resolve_completion_policy
from app.services.workflow_rule_resolver import resolve_user_targets_from_rule
from app.services.access_control import (
  MANAGEMENT_ROLES,
  can_manage_assignee,
  can_publish_org_tasks,
  expand_department_ids,
  ensure_active_user,
  get_actor_department_id,
  get_effective_managed_department_ids,
  get_managed_department_ids,
  is_management_role,
)
from app.services.cross_department_routing_service import resolve_cross_department_boundary_cc_user_ids
from app.services.notification_service import NotificationService
from app.services.condition_evaluator import evaluate_routing_rules
from app.services.task_action_policy import (
  ActionOption,
  WorkItemActionContext,
  build_standalone_action_context,
  derive_execution_mode,
  is_standalone,
  standalone_action_owner_id,
)
from app.services.task_user_facing_state import resolve_task_run_label, resolve_task_user_facing_state

MAX_BATCH_TASK_IDS = 100
TASK_STATS_TIMEZONE = ZoneInfo("Asia/Shanghai")
TASK_STATS_MAX_RANGE_DAYS = 366

TTaskCenterEntry = TypeVar("TTaskCenterEntry")


@dataclass(slots=True)
class TaskCenterListPage(Generic[TTaskCenterEntry]):
  items: list[TTaskCenterEntry]
  next_cursor: UUID | None = None
  has_more: bool = False


def _paginate_task_center_list(
  entries: list[TTaskCenterEntry],
  *,
  limit: int,
  after_task_id: UUID | None,
  task_id_getter: Callable[[TTaskCenterEntry], UUID],
) -> TaskCenterListPage[TTaskCenterEntry]:
  sliced = entries
  if after_task_id is not None:
    start_index = 0
    for index, entry in enumerate(entries):
      if task_id_getter(entry) == after_task_id:
        start_index = index + 1
        break
    sliced = entries[start_index:]
  page_items = sliced[:limit]
  has_more = len(sliced) > limit
  next_cursor = task_id_getter(page_items[-1]) if has_more and page_items else None
  return TaskCenterListPage(items=page_items, next_cursor=next_cursor, has_more=has_more)


def _resolve_task_stats_period(
  *,
  start_date: date | None,
  end_date: date | None,
  now: datetime,
) -> tuple[date, date, datetime, datetime]:
  local_today = now.astimezone(TASK_STATS_TIMEZONE).date()
  resolved_start = start_date or local_today.replace(day=1)
  if end_date is None:
    next_month = (
      resolved_start.replace(year=resolved_start.year + 1, month=1, day=1)
      if resolved_start.month == 12
      else resolved_start.replace(month=resolved_start.month + 1, day=1)
    )
    resolved_end = next_month - timedelta(days=1)
  else:
    resolved_end = end_date

  if resolved_end < resolved_start:
    raise ConflictError("统计结束日期不能早于开始日期。")
  if (resolved_end - resolved_start).days + 1 > TASK_STATS_MAX_RANGE_DAYS:
    raise ConflictError(f"统计周期最长为 {TASK_STATS_MAX_RANGE_DAYS} 天。")

  start_at = datetime.combine(resolved_start, time.min, tzinfo=TASK_STATS_TIMEZONE).astimezone(UTC)
  end_at = datetime.combine(resolved_end + timedelta(days=1), time.min, tzinfo=TASK_STATS_TIMEZONE).astimezone(UTC)
  return resolved_start, resolved_end, start_at, end_at


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
  start_date: date
  end_date: date
  created_tasks: int
  period_completed_tasks: int
  due_tasks: int
  matured_due_tasks: int
  on_time_completed_tasks: int
  on_time_completion_rate: float
  current_open_tasks: int
  period_overdue_tasks: int


@dataclass(slots=True)
class TaskWorkloadEntry:
  assignee_id: UUID
  assignee_email: str
  assignee_label: str
  department_id: UUID | None
  department_name: str | None
  total_tasks: int
  open_tasks: int
  completed_tasks: int
  overdue_tasks: int
  created_tasks: int
  period_completed_tasks: int
  due_tasks: int
  matured_due_tasks: int
  on_time_completed_tasks: int
  on_time_completion_rate: float
  period_overdue_tasks: int


@dataclass(slots=True)
class TaskStatsScopeOption:
  id: UUID
  label: str


@dataclass(slots=True)
class TaskStatsScopes:
  mode: str
  departments: list[TaskStatsScopeOption]


@dataclass(slots=True)
class TaskStatsDetailEntry:
  task_id: UUID
  title: str
  assignee_id: UUID
  assignee_label: str
  department_id: UUID | None
  department_name: str | None
  source_type: TaskSourceType
  run_label: str | None
  due_date: datetime | None
  completed_at: datetime | None
  is_overdue: bool


@dataclass(slots=True)
class TaskStatsDetailsPage:
  items: list[TaskStatsDetailEntry]
  next_cursor: UUID | None = None
  has_more: bool = False


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
  run_label: str | None = None
  user_facing_state: str | None = None
  execution_mode: str | None = None
  assignment_mode: str | None = None
  current_action_owner_id: UUID | None = None
  requires_action: bool = False
  action_type: str | None = None
  available_actions: list[ActionOption] = field(default_factory=list)


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
  run_label: str | None = None
  user_facing_state: str | None = None
  execution_mode: str | None = None
  assignment_mode: str | None = None
  current_action_owner_id: UUID | None = None
  requires_action: bool = False
  action_type: str | None = None
  available_actions: list[ActionOption] = field(default_factory=list)


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
  status: TaskStatus | None = None
  run_label: str | None = None
  user_facing_state: str | None = None


@dataclass(slots=True)
class AssignmentCandidate:
  user_id: UUID
  display_name: str
  department_name: str | None = None
  role_name: str | None = None


@dataclass(slots=True)
class GraphTaskProjection:
  task_id: UUID
  status: TaskStatus
  current_stage_label: str
  current_handler_id: UUID | None
  current_handler_label: str | None
  latest_deliverable_submitted_at: datetime | None
  rework_count: int
  review_quality_score: int | None
  completed_at: datetime | None
  business_state: WorkflowNodeBusinessState | None = None
  node_key: str | None = None


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
_MAX_TASK_ATTACHMENTS = 10


def _user_display_label(user: User | None) -> str | None:
  if user is None:
    return None
  from app.services.user_display import user_display_label

  return user_display_label(user)


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
    self._human_task_coordinator = HumanTaskCoordinator(session)

  def _workflow_graph_engine_enabled(self) -> bool:
    return bool(self._settings is not None and self._settings.workflow_graph_engine_enabled)

  def _task_center_v2_enabled(self) -> bool:
    return bool(self._settings is not None and self._settings.task_center_v2_enabled)

  @staticmethod
  def _read_payload_datetime(payload: dict[str, Any], key: str) -> datetime | None:
    raw_value = payload.get(key)
    if not isinstance(raw_value, str) or not raw_value.strip():
      return None
    try:
      return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
      return None

  @staticmethod
  def _read_payload_int(payload: dict[str, Any], key: str) -> int | None:
    raw_value = payload.get(key)
    if isinstance(raw_value, bool):
      return int(raw_value)
    if isinstance(raw_value, int):
      return raw_value
    if isinstance(raw_value, str):
      try:
        return int(raw_value)
      except ValueError:
        return None
    return None

  @staticmethod
  def _resolve_graph_task_status(
    *,
    task: Task | None = None,
    instance: WorkflowGraphInstance,
    node_instance: WorkflowNodeInstance,
  ) -> TaskStatus:
    if task is not None and TaskService._is_batch_graph_root_shell_task(task):
      if instance.status == WorkflowGraphInstanceStatus.COMPLETED:
        return TaskStatus.DONE
      if instance.status in {
        WorkflowGraphInstanceStatus.ACTIVE,
        WorkflowGraphInstanceStatus.PENDING,
      }:
        return TaskStatus.DOING

    if instance.status == WorkflowGraphInstanceStatus.COMPLETED or node_instance.engine_state == WorkflowNodeEngineState.COMPLETED:
      return TaskStatus.DONE
    if node_instance.business_state == WorkflowNodeBusinessState.PENDING_REVIEW:
      return TaskStatus.REVIEW
    if node_instance.business_state in {
      WorkflowNodeBusinessState.DOING,
      WorkflowNodeBusinessState.RETURNED_FOR_REWORK,
    }:
      return TaskStatus.DOING
    return TaskStatus.TODO

  def _build_graph_stage_label(
    self,
    *,
    task: Task,
    instance: WorkflowGraphInstance,
    node_instance: WorkflowNodeInstance,
  ) -> str:
    metadata = self._copy_task_metadata(task)
    latest_action = self._read_str_metadata(metadata, "latest_handshake_action")
    step_title = (node_instance.title or node_instance.node_key or "当前步骤").strip()

    if self._is_batch_graph_root_shell_task(task) and instance.status == WorkflowGraphInstanceStatus.ACTIVE:
      context = instance.context if isinstance(instance.context, dict) else {}
      if str(context.get("fork_status") or "") == "completed":
        return "批次跟进：制作进行中"
      return "汇总派发：待确认派发"

    if node_instance.business_state == WorkflowNodeBusinessState.REJECTED:
      return f"{step_title}：已拒绝待调整"
    if node_instance.business_state == WorkflowNodeBusinessState.ASSIGNED:
      if latest_action == "takeover":
        return f"{step_title}：管理员接管待确认"
      if latest_action == "delegated":
        return f"{step_title}：已转办待确认"
      if latest_action == "reassigned":
        return f"{step_title}：重新派发待确认"
      return f"{step_title}：待确认"
    if node_instance.business_state == WorkflowNodeBusinessState.ACCEPTED:
      return f"{step_title}：已接受待开工"
    if node_instance.business_state == WorkflowNodeBusinessState.RETURNED_FOR_REWORK:
      return f"{step_title}：返工中"
    if node_instance.business_state == WorkflowNodeBusinessState.PENDING_REVIEW:
      return f"{step_title}：待验收"
    if node_instance.business_state == WorkflowNodeBusinessState.DONE:
      return f"{step_title}：已完成"
    status_label = _task_status_label(
      self._resolve_graph_task_status(task=task, instance=instance, node_instance=node_instance)
    )
    return f"{step_title}：{status_label}"

  def _build_graph_projection(
    self,
    *,
    task: Task,
    instance: WorkflowGraphInstance,
    node_instance: WorkflowNodeInstance,
  ) -> GraphTaskProjection:
    deliverable = node_instance.deliverables[0] if node_instance.deliverables else None
    payload = dict(deliverable.payload or {}) if deliverable is not None else {}
    latest_review = payload.get("latest_review") if isinstance(payload.get("latest_review"), dict) else {}

    status = self._resolve_graph_task_status(task=task, instance=instance, node_instance=node_instance)
    current_handler_id = task.creator_id if node_instance.business_state in {
      WorkflowNodeBusinessState.PENDING_REVIEW,
      WorkflowNodeBusinessState.REJECTED,
    } else (node_instance.assignee_user_id or task.assignee_id)
    if current_handler_id == task.creator_id:
      current_handler_label = _user_display_label(task.creator)
    elif current_handler_id == task.assignee_id:
      current_handler_label = _user_display_label(task.assignee)
    else:
      current_handler_label = _user_display_label(task.assignee)

    latest_deliverable_submitted_at = None
    if deliverable is not None:
      latest_deliverable_submitted_at = deliverable.submitted_at
      if latest_deliverable_submitted_at is None and isinstance(payload.get("latest_submission"), dict):
        latest_deliverable_submitted_at = self._read_payload_datetime(payload["latest_submission"], "submitted_at")

    review_quality_score = None
    if latest_review:
      review_quality_score = self._read_payload_int(latest_review, "quality_score")
    if review_quality_score is None:
      review_quality_score = self._read_int_metadata(self._copy_task_metadata(task), "latest_review_quality_score", default=-1)
      if review_quality_score < 0:
        review_quality_score = None

    rework_count = self._read_payload_int(payload, "rework_count")
    if rework_count is None:
      rework_count = self._read_int_metadata(self._copy_task_metadata(task), "rework_count")

    completed_at = None
    if status == TaskStatus.DONE:
      completed_at = node_instance.completed_at or instance.completed_at or task.completed_at

    return GraphTaskProjection(
      task_id=task.id,
      status=status,
      current_stage_label=self._build_graph_stage_label(
        task=task,
        instance=instance,
        node_instance=node_instance,
      ),
      current_handler_id=current_handler_id,
      current_handler_label=current_handler_label,
      latest_deliverable_submitted_at=latest_deliverable_submitted_at,
      rework_count=rework_count,
      review_quality_score=review_quality_score,
      completed_at=completed_at,
      business_state=node_instance.business_state,
      node_key=node_instance.node_key,
    )

  def _select_graph_task_node(
    self,
    *,
    task: Task,
    instance: WorkflowGraphInstance,
  ) -> WorkflowNodeInstance | None:
    metadata = self._copy_task_metadata(task)
    node_instance_id = self._read_uuid_metadata(metadata, "workflow_node_instance_id")
    if node_instance_id is not None:
      for node_instance in instance.node_instances:
        if node_instance.id == node_instance_id:
          return node_instance

    active_nodes = [
      node_instance
      for node_instance in instance.node_instances
      if node_instance.engine_state not in {
        WorkflowNodeEngineState.COMPLETED,
        WorkflowNodeEngineState.TERMINATED,
      }
    ]
    if instance.current_node_key:
      keyed_nodes = [
        node_instance
        for node_instance in active_nodes
        if node_instance.node_key == instance.current_node_key
      ]
      if keyed_nodes:
        keyed_nodes.sort(key=lambda node: (node.iteration, node.created_at), reverse=True)
        return keyed_nodes[0]

    if active_nodes:
      active_nodes.sort(key=lambda node: (node.iteration, node.created_at), reverse=True)
      return active_nodes[0]

    if instance.node_instances:
      finished_nodes = sorted(
        instance.node_instances,
        key=lambda node: (node.iteration, node.created_at),
        reverse=True,
      )
      return finished_nodes[0]
    return None

  async def _graph_task_projection_map(self, *, tasks: list[Task]) -> dict[UUID, GraphTaskProjection]:
    if not tasks:
      return {}

    task_map = {task.id: task for task in tasks}
    projections: dict[UUID, GraphTaskProjection] = {}

    links = list(
      await self._session.scalars(
        select(WorkflowHumanTaskLink)
        .options(
          selectinload(WorkflowHumanTaskLink.instance),
          selectinload(WorkflowHumanTaskLink.node_instance).selectinload(
            WorkflowNodeInstance.deliverables
          ),
        )
        .where(WorkflowHumanTaskLink.task_id.in_(list(task_map.keys())))
      )
    )
    for link in links:
      task = task_map.get(link.task_id)
      if task is None or link.instance is None or link.node_instance is None:
        continue
      projections[task.id] = self._build_graph_projection(
        task=task,
        instance=link.instance,
        node_instance=link.node_instance,
      )

    instances = list(
      await self._session.scalars(
        select(WorkflowGraphInstance)
        .options(
          selectinload(WorkflowGraphInstance.node_instances).selectinload(WorkflowNodeInstance.deliverables)
        )
        .where(WorkflowGraphInstance.source_id.in_(list(task_map.keys())))
      )
    )
    for instance in instances:
      if instance.source_id is None:
        continue
      task = task_map.get(instance.source_id)
      if task is None or task.id in projections:
        continue
      node_instance = self._select_graph_task_node(task=task, instance=instance)
      if node_instance is None:
        continue
      projections[task.id] = self._build_graph_projection(
        task=task,
        instance=instance,
        node_instance=node_instance,
      )

    node_instance_ids: list[UUID] = []
    node_id_to_task: dict[UUID, Task] = {}
    for task in tasks:
      if task.id in projections:
        continue
      metadata = self._copy_task_metadata(task)
      node_instance_id = self._read_uuid_metadata(metadata, "workflow_node_instance_id")
      if node_instance_id is None:
        continue
      node_instance_ids.append(node_instance_id)
      node_id_to_task[node_instance_id] = task

    if node_instance_ids:
      node_instances = list(
        await self._session.scalars(
          select(WorkflowNodeInstance)
          .options(
            selectinload(WorkflowNodeInstance.instance),
            selectinload(WorkflowNodeInstance.deliverables),
          )
          .where(WorkflowNodeInstance.id.in_(node_instance_ids))
        )
      )
      for node_instance in node_instances:
        task = node_id_to_task.get(node_instance.id)
        if task is None or node_instance.instance is None:
          continue
        projections[task.id] = self._build_graph_projection(
          task=task,
          instance=node_instance.instance,
          node_instance=node_instance,
        )

    return projections

  @staticmethod
  def _list_scan_limit(*, limit: int, multiplier: int = 10, ceiling: int = 500) -> int:
    return min(max(limit * multiplier, limit), ceiling)

  async def _load_graph_run_label_by_task_id(self, *, tasks: list[Task]) -> dict[UUID, str | None]:
    task_instance_ids: dict[UUID, UUID] = {}
    for task in tasks:
      metadata = self._copy_task_metadata(task)
      instance_id = self._read_uuid_metadata(metadata, "workflow_graph_instance_id")
      if instance_id is not None:
        task_instance_ids[task.id] = instance_id
    if not task_instance_ids:
      return {}

    instances = list(
      await self._session.scalars(
        select(WorkflowGraphInstance).where(
          WorkflowGraphInstance.id.in_(set(task_instance_ids.values()))
        )
      )
    )
    run_label_by_instance_id: dict[UUID, str | None] = {}
    for instance in instances:
      label = instance.run_label
      if (not label or not str(label).strip()) and isinstance(instance.context, dict):
        raw = instance.context.get("run_label")
        if raw is not None:
          label = str(raw)
      run_label_by_instance_id[instance.id] = str(label).strip() if label else None

    return {
      task_id: run_label_by_instance_id.get(instance_id)
      for task_id, instance_id in task_instance_ids.items()
    }

  def _list_item_extras(
    self,
    *,
    task: Task,
    status: TaskStatus,
    graph_run_labels: dict[UUID, str | None],
    graph_business_state: WorkflowNodeBusinessState | None = None,
    graph_node_key: str | None = None,
  ) -> tuple[str | None, str]:
    metadata = self._copy_task_metadata(task)
    run_label = resolve_task_run_label(
      title=task.title,
      metadata=metadata,
      graph_run_label=graph_run_labels.get(task.id),
    )
    user_facing_state = resolve_task_user_facing_state(
      task=task,
      status=status,
      graph_business_state=graph_business_state,
      graph_node_key=graph_node_key,
    )
    return run_label, user_facing_state

  def _work_item_action_context(
    self,
    *,
    task: Task,
    actor: User,
    projection: GraphTaskProjection | None = None,
  ) -> WorkItemActionContext:
    """Unified, per-actor Work Item capability snapshot.

    Standalone tasks derive the full action set (the Iteration 3 fix); workflow
    (graph-projected) tasks report execution_mode + current action owner so the
    task center can bucket them, while their detailed action rendering stays on
    the existing graph-aware path for this pass.
    """
    is_mgmt = actor.role in MANAGEMENT_ROLES
    if projection is not None:
      owner = projection.current_handler_id
      actor_is_owner = owner is not None and owner == actor.id
      action_type: str | None = None
      if actor_is_owner:
        if projection.status == TaskStatus.REVIEW:
          action_type = "review_deliverable"
        elif projection.status == TaskStatus.DOING:
          action_type = "submit_deliverable"
        elif projection.status == TaskStatus.TODO:
          action_type = "handshake"
      return WorkItemActionContext(
        execution_mode=derive_execution_mode(task),
        assignment_mode=task.assignment_mode or "direct",
        current_action_owner_id=owner,
        requires_action=actor_is_owner and action_type is not None,
        action_type=action_type,
        available_actions=[],
      )
    if is_standalone(task):
      return build_standalone_action_context(task=task, actor=actor, is_management=is_mgmt)
    return WorkItemActionContext(
      execution_mode=derive_execution_mode(task),
      assignment_mode=task.assignment_mode or "direct",
      current_action_owner_id=task.assignee_id if task.status != TaskStatus.DONE else None,
      requires_action=False,
      action_type=None,
      available_actions=[],
    )

  async def resolve_task_action_context(self, *, actor: User, task: Task) -> WorkItemActionContext:
    """Public entry: per-actor Work Item action contract for a task detail view.

    Standalone tasks derive the full action set (the Iteration 3 fix). Workflow
    (graph-projected) tasks report execution_mode only; their detailed action
    rendering stays on the existing graph-aware frontend path for this pass, so
    we avoid recomputing the graph projection here (which would require eager
    relationship loading that a freshly mutated task may not carry).
    """
    if is_standalone(task):
      return build_standalone_action_context(
        task=task,
        actor=actor,
        is_management=actor.role in MANAGEMENT_ROLES,
      )
    return self._work_item_action_context(task=task, actor=actor)

  @staticmethod
  def _apply_action_context(entry: TaskInboxEntry | TaskTrackingEntry, ctx: WorkItemActionContext) -> None:
    entry.execution_mode = ctx.execution_mode
    entry.assignment_mode = ctx.assignment_mode
    entry.current_action_owner_id = ctx.current_action_owner_id
    entry.requires_action = ctx.requires_action
    entry.action_type = ctx.action_type
    entry.available_actions = list(ctx.available_actions)

  def _build_graph_inbox_entry(
    self,
    *,
    task: Task,
    projection: GraphTaskProjection,
    graph_run_labels: dict[UUID, str | None],
    actor: User,
  ) -> TaskInboxEntry:
    run_label, user_facing_state = self._list_item_extras(
      task=task,
      status=projection.status,
      graph_run_labels=graph_run_labels,
      graph_business_state=projection.business_state,
      graph_node_key=projection.node_key,
    )
    entry = TaskInboxEntry(
      task_id=task.id,
      title=task.title,
      priority=task.priority,
      status=projection.status,
      due_date=task.due_date,
      department_name=task.department.name if task.department is not None else None,
      current_stage_label=projection.current_stage_label,
      current_handler_label=projection.current_handler_label,
      run_label=run_label,
      user_facing_state=user_facing_state,
    )
    self._apply_action_context(
      entry,
      self._work_item_action_context(task=task, actor=actor, projection=projection),
    )
    return entry

  def _build_graph_tracking_entry(
    self,
    *,
    task: Task,
    relation_types: list[str],
    projection: GraphTaskProjection,
    graph_run_labels: dict[UUID, str | None],
    actor: User,
  ) -> TaskTrackingEntry:
    run_label, user_facing_state = self._list_item_extras(
      task=task,
      status=projection.status,
      graph_run_labels=graph_run_labels,
      graph_business_state=projection.business_state,
      graph_node_key=projection.node_key,
    )
    entry = TaskTrackingEntry(
      task_id=task.id,
      title=task.title,
      priority=task.priority,
      status=projection.status,
      due_date=task.due_date,
      department_name=task.department.name if task.department is not None else None,
      relation_types=relation_types,
      current_stage_label=projection.current_stage_label,
      current_handler_label=projection.current_handler_label,
      latest_deliverable_submitted_at=projection.latest_deliverable_submitted_at,
      rework_count=projection.rework_count,
      review_quality_score=projection.review_quality_score,
      is_pending_review=projection.status == TaskStatus.REVIEW,
      run_label=run_label,
      user_facing_state=user_facing_state,
    )
    self._apply_action_context(
      entry,
      self._work_item_action_context(task=task, actor=actor, projection=projection),
    )
    return entry

  def _build_graph_history_entry(
    self,
    *,
    task: Task,
    relation_types: list[str],
    projection: GraphTaskProjection,
    graph_run_labels: dict[UUID, str | None],
  ) -> TaskHistoryEntry:
    run_label, user_facing_state = self._list_item_extras(
      task=task,
      status=projection.status,
      graph_run_labels=graph_run_labels,
      graph_business_state=projection.business_state,
      graph_node_key=projection.node_key,
    )
    return TaskHistoryEntry(
      task_id=task.id,
      title=task.title,
      priority=task.priority,
      due_date=task.due_date,
      completed_at=projection.completed_at,
      department_name=task.department.name if task.department is not None else None,
      relation_types=relation_types,
      source_type=task.source_type,
      status=projection.status,
      run_label=run_label,
      user_facing_state=user_facing_state,
    )

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

    await self._human_task_coordinator.coordinate_mutations(
      graph_instance=instance,
      instance_changes={
        "source_id": task.id,
        "source_type": source_type.value,
        "status": WorkflowGraphInstanceStatus.ACTIVE,
      },
    )
    await self._human_task_coordinator.bind_projection_task(
      task=task,
      node_instance=node_instance,
      source="manual_compat",
    )

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
    # Step config is operator-supplied JSON: an invalid priority string must
    # surface as a 422 validation error instead of an uncaught ValueError (500).
    try:
      step_priority = TaskPriority(str(step.config.get("priority") or TaskPriority.MEDIUM))
    except ValueError as exc:
      raise AppValidationError("Invalid priority value") from exc
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
        priority=step_priority,
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
    if skip_assignee_permission:
      return assignee
    if await can_manage_assignee(self._session, actor, assignee_id):
      return assignee
    # F-21: cross-department routing — org publishers may assign outside subtree.
    if await can_publish_org_tasks(self._session, actor):
      return assignee
    raise AuthorizationError("当前账号不能为该执行人创建任务。")

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
    attachment_ids: list[UUID] | None = None,
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

    use_legacy_manual_graph = (
      self._workflow_graph_engine_enabled()
      and source_type == TaskSourceType.MANUAL
      and self._settings is not None
      and not self._settings.workflow_standalone_manual_tasks_enabled
    )
    if use_legacy_manual_graph:
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
    else:
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

    if attachment_ids:
      await self._bind_attachments_to_task(actor=actor, task_id=task.id, attachment_ids=attachment_ids)

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
        selectinload(Task.watchers),
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

  def _standalone_context(self, *, task: Task) -> tuple[str, str | None] | None:
    """Stage label / current handler for a standalone Task (no graph metadata)."""
    if not is_standalone(task):
      return None
    assignee_label = _user_display_label(task.assignee)
    creator_label = _user_display_label(task.creator)
    if task.status == TaskStatus.TODO:
      return ("任务：待处理", assignee_label)
    if task.status == TaskStatus.DOING:
      metadata = self._copy_task_metadata(task)
      if self._read_str_metadata(metadata, "latest_review_state") == "returned_for_rework":
        return ("任务：返工中", assignee_label)
      return ("任务：进行中", assignee_label)
    if task.status == TaskStatus.REVIEW:
      return ("任务：待验收", creator_label)
    return ("任务：已完成", assignee_label)

  def _build_inbox_entry(
    self,
    *,
    task: Task,
    step_context_map: dict[UUID, tuple[str, str | None]],
    graph_run_labels: dict[UUID, str | None],
    actor: User,
  ) -> TaskInboxEntry:
    current_stage_label, current_handler_label = step_context_map.get(
      task.id,
      self._manual_graph_context(task=task)
      or self._standalone_context(task=task)
      or (
        f"任务：{_task_status_label(task.status)}",
        _user_display_label(task.assignee),
      ),
    )
    run_label, user_facing_state = self._list_item_extras(
      task=task,
      status=task.status,
      graph_run_labels=graph_run_labels,
    )
    entry = TaskInboxEntry(
      task_id=task.id,
      title=task.title,
      priority=task.priority,
      status=task.status,
      due_date=task.due_date,
      department_name=task.department.name if task.department is not None else None,
      current_stage_label=current_stage_label,
      current_handler_label=current_handler_label,
      run_label=run_label,
      user_facing_state=user_facing_state,
    )
    self._apply_action_context(
      entry,
      self._work_item_action_context(task=task, actor=actor),
    )
    return entry

  def _build_tracking_entry(
    self,
    *,
    task: Task,
    relation_types: list[str],
    step_context_map: dict[UUID, tuple[str, str | None]],
    graph_run_labels: dict[UUID, str | None],
    actor: User,
  ) -> TaskTrackingEntry:
    metadata = self._copy_task_metadata(task)
    review_quality_score = None
    if metadata.get("latest_review_quality_score") is not None:
      review_quality_score = self._read_int_metadata(metadata, "latest_review_quality_score")

    current_stage_label, current_handler_label = step_context_map.get(
      task.id,
      self._manual_graph_context(task=task)
      or self._standalone_context(task=task)
      or (
        f"任务：{_task_status_label(task.status)}",
        _user_display_label(task.assignee),
      ),
    )
    run_label, user_facing_state = self._list_item_extras(
      task=task,
      status=task.status,
      graph_run_labels=graph_run_labels,
    )
    entry = TaskTrackingEntry(
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
      run_label=run_label,
      user_facing_state=user_facing_state,
    )
    self._apply_action_context(
      entry,
      self._work_item_action_context(task=task, actor=actor),
    )
    return entry

  def _build_history_entry(
    self,
    *,
    task: Task,
    relation_types: list[str],
    graph_run_labels: dict[UUID, str | None],
    status: TaskStatus,
  ) -> TaskHistoryEntry:
    run_label, user_facing_state = self._list_item_extras(
      task=task,
      status=status,
      graph_run_labels=graph_run_labels,
    )
    return TaskHistoryEntry(
      task_id=task.id,
      title=task.title,
      priority=task.priority,
      due_date=task.due_date,
      completed_at=task.completed_at,
      department_name=task.department.name if task.department is not None else None,
      relation_types=relation_types,
      source_type=task.source_type,
      status=status,
      run_label=run_label,
      user_facing_state=user_facing_state,
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
  def _is_graph_run_root_shell_task(task: Task) -> bool:
    """Batch/production ROOT tasks are tracking shells — not actionable inbox items."""
    return TaskService._copy_task_metadata(task).get("workflow_graph_root_task") is True

  @staticmethod
  def _is_production_graph_root_shell_task(task: Task) -> bool:
    metadata = TaskService._copy_task_metadata(task)
    if metadata.get("workflow_graph_root_task") is not True:
      return False
    return str(metadata.get("run_kind") or "") == "production"

  @staticmethod
  def _is_batch_graph_root_shell_task(task: Task) -> bool:
    metadata = TaskService._copy_task_metadata(task)
    if metadata.get("workflow_graph_root_task") is not True:
      return False
    return str(metadata.get("run_kind") or "") == "batch"

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
    resolution = await self._human_task_coordinator.resolve_for_task(task=task)
    if resolution.instance is not None and resolution.node_instance is not None:
      return resolution.instance, resolution.node_instance

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

  async def _load_template_graph_node_context(
    self,
    *,
    task: Task,
  ) -> tuple[
    WorkflowGraphInstance | None,
    WorkflowNodeInstance | None,
    WorkflowGraphTemplateNode | None,
    str | None,
  ]:
    from app.services.workflow_orchestration_service import WorkflowOrchestrationService

    if not WorkflowOrchestrationService.is_template_graph_projection(task):
      return None, None, None, None

    instance, node_instance = await self._load_workflow_graph_projection(task=task)
    if instance is None or node_instance is None:
      return None, None, None, None

    template_node = None
    if node_instance.template_node_id is not None:
      template_node = await self._session.get(
        WorkflowGraphTemplateNode,
        node_instance.template_node_id,
      )
    from app.services.workflow_node_config_helpers import reconcile_node_instance_config_from_template

    reconcile_node_instance_config_from_template(
      node_instance=node_instance,
      template_node=template_node,
    )
    policy = resolve_completion_policy(
      node_instance=node_instance,
      template_node=template_node,
    )
    return instance, node_instance, template_node, policy

  async def _maybe_progress_template_graph_after_completion(
    self,
    *,
    actor: User,
    task: Task,
    expected_policy: str,
  ) -> None:
    from app.services.workflow_orchestration_service import WorkflowOrchestrationService

    instance, node_instance, _template_node, policy = await self._load_template_graph_node_context(
      task=task,
    )
    if instance is None or node_instance is None or policy != expected_policy:
      return
    if node_instance.engine_state != WorkflowNodeEngineState.COMPLETED:
      return

    orchestration = WorkflowOrchestrationService(
      self._session,
      workflow_graph_service=self._workflow_graph_service,
      task_service=self,
    )
    await orchestration.after_node_completed(
      actor=actor,
      task=task,
      instance=instance,
      node_instance=node_instance,
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
      if latest_action == "takeover":
        return ("任务：管理员接管待确认", assignee_label)
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

  async def _bind_attachments_to_task(
    self,
    *,
    actor: User,
    task_id: UUID,
    attachment_ids: list[UUID],
  ) -> None:
    if not attachment_ids:
      return
    if len(attachment_ids) > _MAX_TASK_ATTACHMENTS:
      raise ConflictError(f"任务附件最多 {_MAX_TASK_ATTACHMENTS} 个。")

    unique: list[UUID] = []
    seen: set[UUID] = set()
    for raw in attachment_ids:
      if raw in seen:
        continue
      seen.add(raw)
      unique.append(raw)

    for att_id in unique:
      att = await self._session.scalar(
        select(Attachment)
        .options(selectinload(Attachment.links))
        .where(Attachment.id == att_id)
      )
      if att is None:
        raise ConflictError("附件不存在。")
      if att.uploader_id != actor.id:
        raise ConflictError("只能绑定本人上传的附件。")
      if att.status != AttachmentStatus.UPLOADED:
        raise ConflictError("附件不可用。")
      if att.links:
        raise ConflictError("附件已绑定其他业务对象，请先使用新上传的附件。")
      self._session.add(
        AttachmentLink(
          attachment_id=att.id,
          target_type=AttachmentTargetType.TASK,
          target_id=task_id,
          relation="primary",
          created_by=actor.id,
        )
      )
    await self._session.flush()

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
            and_(
              AttachmentLink.target_type == AttachmentTargetType.TASK,
              AttachmentLink.target_id == task_id,
            )
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
    await self._human_task_coordinator.sync_runtime_for_task_status(
      task=task,
      target_status=target_status,
      reference_time=reference_time,
      force_business_state=force_business_state,
    )

  async def _sync_graph_projection_for_handshake_state(
    self,
    *,
    task: Task,
    business_state: WorkflowNodeBusinessState,
    reference_time: datetime,
    assignee_id: UUID | None = None,
    reset_acknowledged_at: bool = False,
  ) -> None:
    await self._human_task_coordinator.sync_runtime_for_handshake_state(
      task=task,
      business_state=business_state,
      reference_time=reference_time,
      assignee_id=assignee_id,
      reset_acknowledged_at=reset_acknowledged_at,
    )

  async def _ensure_task_assignee_or_manager(self, *, actor: User, task: Task) -> None:
    if actor.role in MANAGEMENT_ROLES or actor.id == task.assignee_id:
      return
    raise AuthorizationError("当前账号不能提交该任务交付物。")

  async def _ensure_task_reviewer(self, *, actor: User, task: Task) -> None:
    if actor.role in MANAGEMENT_ROLES or actor.id == task.creator_id:
      return
    from app.services.workflow_orchestration_service import WorkflowOrchestrationService

    if actor.id == task.assignee_id and WorkflowOrchestrationService.is_template_graph_projection(task):
      return
    raise AuthorizationError("当前账号不能验收该任务。")

  async def _ensure_task_handshake_actor(self, *, actor: User, task: Task) -> None:
    if actor.role in MANAGEMENT_ROLES or actor.id == task.assignee_id:
      return
    raise AuthorizationError("当前账号不能处理该任务的握手动作。")

  @staticmethod
  def _has_task_admin_override(actor: User) -> bool:
    """Task admin override, currently mapped to ADMIN/HR.

    Deliberately NOT extended to task creators: once a direct assignment is
    made, execution responsibility belongs to the assignee. Department-manager
    delegation authority, if ever needed, must go through the managed-scope
    policy rather than a creator_id shortcut.
    """
    return actor.role in MANAGEMENT_ROLES

  async def _ensure_standalone_delegate_authority(self, *, actor: User, task: Task) -> None:
    if actor.id == task.assignee_id or self._has_task_admin_override(actor):
      return
    raise AuthorizationError("仅当前执行人或任务管理员可以转办该任务。")

  async def _refresh_task_row_with_lock(self, *, task_id: UUID) -> None:
    """Serialise standalone Work Item state commands via a row lock.

    Re-reads the task under ``FOR UPDATE`` and repopulates the identity-mapped
    instance, so permission/status checks that follow see committed state
    instead of a stale snapshot. Concurrent delegate/submit/start commands are
    thereby ordered: the loser re-validates against the winner's result and
    fails with a stable business error instead of silently overwriting it.
    (``FOR UPDATE`` is a no-op on SQLite, which is single-writer anyway.)
    """
    await self._session.scalar(
      select(Task)
      .where(Task.id == task_id)
      .with_for_update()
      .execution_options(populate_existing=True)
    )

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
    # A stable business conflict, not AuthenticationError: the *target* being
    # inactive must never surface as a 401 for the acting user.
    if assignee.status != UserStatus.ACTIVE:
      raise ConflictError("转办目标账号不可用。")
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
    attachment_ids: list[UUID] | None = None,
    watcher_user_ids: list[UUID] | None = None,
    assignment_mode: str | None = None,
  ) -> Task:
    # Invariant: standalone manual tasks are created with direct assignment.
    # The handshake state machine (PENDING_ACCEPTANCE / DECLINED) is a later
    # batch; requesting it must fail loudly, never silently fall back.
    if assignment_mode is not None and assignment_mode != TaskAssignmentMode.DIRECT.value:
      raise ConflictError(f"unsupported_assignment_mode: 暂不支持 {assignment_mode} 指派模式。")
    task, _ = await self.create_task_record(
      actor=actor,
      title=title,
      assignee_id=assignee_id,
      description=description,
      department_id=department_id,
      due_date=due_date,
      priority=priority,
      dependency_ids=dependency_ids,
      attachment_ids=attachment_ids,
      source_type=TaskSourceType.MANUAL,
      commit=True,
    )
    merged_watcher_ids = list(dict.fromkeys(watcher_user_ids or []))
    actor_department_id = await get_actor_department_id(self._session, actor.id)
    assignee_department_id = await get_actor_department_id(self._session, assignee_id)
    path_cc_ids = await resolve_cross_department_boundary_cc_user_ids(
      self._session,
      origin_department_id=actor_department_id,
      target_department_id=assignee_department_id,
      exclude_user_ids={actor.id, assignee_id},
    )
    merged_watcher_ids = list(dict.fromkeys([*merged_watcher_ids, *path_cc_ids]))
    if merged_watcher_ids:
      await self.add_task_watchers(
        actor=actor,
        task_id=task.id,
        watcher_user_ids=merged_watcher_ids,
      )
    return task

  async def list_tasks(self, *, actor: User) -> list[Task]:
    ensure_active_user(actor)

    statement = await self._build_visible_task_statement(actor=actor)
    result = await self._session.scalars(statement)
    return list(result)

  async def list_tasks_by_ids(self, *, actor: User, task_ids: list[UUID]) -> list[Task]:
    ensure_active_user(actor)
    if not task_ids:
      return []
    if len(task_ids) > MAX_BATCH_TASK_IDS:
      raise ConflictError(f"单次最多查询 {MAX_BATCH_TASK_IDS} 个任务。")

    unique_task_ids = list(dict.fromkeys(task_ids))
    statement = (await self._build_visible_task_statement(actor=actor)).where(
      Task.id.in_(unique_task_ids)
    )
    tasks = list(await self._session.scalars(statement))
    task_map = {task.id: task for task in tasks}
    return [task_map[task_id] for task_id in unique_task_ids if task_id in task_map]

  async def search_tasks(self, *, actor: User, query: str, limit: int = 30) -> list[Task]:
    ensure_active_user(actor)
    normalized = query.strip()
    if not normalized:
      return []

    pattern = f"%{normalized}%"
    statement = (
      (await self._build_visible_task_statement(actor=actor))
      .where(
        or_(
          Task.title.ilike(pattern),
          Task.description.ilike(pattern),
        )
      )
      .order_by(Task.updated_at.desc())
      .limit(max(1, min(limit, 100)))
    )
    return list(await self._session.scalars(statement))

  async def get_task(self, *, actor: User, task_id: UUID) -> Task:
    ensure_active_user(actor)

    statement = (await self._build_visible_task_statement(actor=actor)).where(Task.id == task_id)
    task = await self._session.scalar(statement)
    if task is None:
      raise NotFoundError("任务不存在。")
    return task

  async def list_task_inbox(
    self,
    *,
    actor: User,
    limit: int = 10,
    after_task_id: UUID | None = None,
  ) -> TaskCenterListPage[TaskInboxEntry]:
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
        (await self._build_visible_task_statement(actor=actor)).limit(
          self._list_scan_limit(limit=limit)
        )
      )
    )
    graph_projection_map = (
      await self._graph_task_projection_map(tasks=tasks)
      if self._task_center_v2_enabled()
      else {}
    )
    graph_run_labels = await self._load_graph_run_label_by_task_id(tasks=tasks)
    step_context_map = await self._task_step_context_map(
      task_ids=[task.id for task in tasks if task.id not in graph_projection_map]
    )

    graph_entries: list[tuple[Task, TaskInboxEntry]] = []
    legacy_tasks: list[Task] = []
    for task in tasks:
      if self._is_admin_archived_task(task):
        continue
      if self._is_graph_run_root_shell_task(task):
        continue
      projection = graph_projection_map.get(task.id)
      if projection is not None:
        if projection.status != TaskStatus.DONE and projection.current_handler_id == actor.id:
          graph_entries.append(
            (
              task,
              self._build_graph_inbox_entry(
                task=task,
                projection=projection,
                graph_run_labels=graph_run_labels,
                actor=actor,
              ),
            )
          )
        continue
      if task.status == TaskStatus.DONE:
        continue
      if task.id in candidate_task_ids:
        legacy_tasks.append(task)
        continue
      if self._uses_graph_handshake_cycle(task=task) and self._manual_graph_current_handler_id(task=task) == actor.id:
        legacy_tasks.append(task)
        continue
      # Standalone Work Item: the inbox owner is whoever must act next
      # (assignee while TODO/DOING, creator while REVIEW), not merely the assignee.
      if is_standalone(task):
        if standalone_action_owner_id(task) == actor.id:
          legacy_tasks.append(task)
        continue
      # Legacy fallback for non-standalone tasks without a graph projection.
      if task.assignee_id == actor.id:
        legacy_tasks.append(task)

    # task id as final tiebreaker: cursor pagination requires a fully deterministic order.
    sorted_graph_entries = sorted(
      graph_entries,
      key=lambda item: (
        item[0].due_date is None,
        _normalize_datetime(item[0].due_date) if item[0].due_date is not None else datetime.max.replace(tzinfo=UTC),
        _task_priority_sort_value(item[0].priority),
        -int(item[0].created_at.timestamp()),
        item[0].id,
      ),
    )
    sorted_legacy_tasks = sorted(
      legacy_tasks,
      key=lambda task: (
        task.due_date is None,
        _normalize_datetime(task.due_date) if task.due_date is not None else datetime.max.replace(tzinfo=UTC),
        _task_priority_sort_value(task.priority),
        -int(task.created_at.timestamp()),
        task.id,
      ),
    )
    entries = [entry for _, entry in sorted_graph_entries]
    entries.extend(
      self._build_inbox_entry(
        task=task,
        step_context_map=step_context_map,
        graph_run_labels=graph_run_labels,
        actor=actor,
      )
      for task in sorted_legacy_tasks
    )
    return _paginate_task_center_list(
      entries,
      limit=limit,
      after_task_id=after_task_id,
      task_id_getter=lambda entry: entry.task_id,
    )

  async def list_task_tracking(
    self,
    *,
    actor: User,
    limit: int = 10,
    exclude_inbox_task_ids: set[UUID] | None = None,
    after_task_id: UUID | None = None,
  ) -> TaskCenterListPage[TaskTrackingEntry]:
    ensure_active_user(actor)
    is_management = actor.role in MANAGEMENT_ROLES

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

    if is_management:
      tasks = list(
        await self._session.scalars(
          (await self._build_visible_task_statement(actor=actor))
          .where(Task.status != TaskStatus.DONE)
          .order_by(Task.updated_at.desc())
          .limit(self._list_scan_limit(limit=limit))
        )
      )
      inbox_task_ids: set[UUID] = set()
    else:
      tracking_filters = [
        Task.creator_id == actor.id,
        Task.assignee_id == actor.id,
        Task.watchers.any(TaskWatcher.user_id == actor.id),
      ]
      managed_department_ids = await get_managed_department_ids(self._session, actor.id)
      if managed_department_ids:
        tracking_filters.append(Task.department_id.in_(managed_department_ids))
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
          .limit(self._list_scan_limit(limit=limit))
        )
      )
      if exclude_inbox_task_ids is None:
        inbox_page = await self.list_task_inbox(actor=actor, limit=limit)
        inbox_task_ids = {entry.task_id for entry in inbox_page.items}
      else:
        inbox_task_ids = set(exclude_inbox_task_ids)

    graph_projection_map = (
      await self._graph_task_projection_map(tasks=tasks)
      if self._task_center_v2_enabled()
      else {}
    )
    graph_run_labels = await self._load_graph_run_label_by_task_id(tasks=tasks)
    step_context_map = await self._task_step_context_map(
      task_ids=[task.id for task in tasks if task.id not in graph_projection_map]
    )
    tracking_entries: list[TaskTrackingEntry] = []
    for task in tasks:
      if self._is_admin_archived_task(task):
        continue
      if not is_management and task.id in inbox_task_ids:
        continue
      if not is_management and self._is_production_graph_root_shell_task(task):
        continue
      relation_types: list[str] = []
      if task.creator_id == actor.id:
        relation_types.append("发起")
      if task.assignee_id == actor.id:
        relation_types.append("执行")
      if any(watcher.user_id == actor.id for watcher in task.watchers):
        relation_types.append("关注")
      if task.id in workflow_related_task_ids or task.id in graph_projection_map:
        relation_types.append("流程")
      is_personally_related = (
        task.creator_id == actor.id
        or task.assignee_id == actor.id
        or any(watcher.user_id == actor.id for watcher in task.watchers)
      )
      has_workflow_participation = task.id in workflow_related_task_ids or task.id in graph_projection_map
      # Iteration 3 fix: a standalone Task legitimately has no workflow participation.
      # Personally-related tasks (creator / assignee / watcher) must not be dropped
      # just because they carry no graph projection.
      if (
        self._task_center_v2_enabled()
        and not has_workflow_participation
        and not is_personally_related
        and not is_management
      ):
        continue
      if is_management and not is_personally_related:
        relation_types.append("督办")

      projection = graph_projection_map.get(task.id)
      if projection is not None:
        if projection.status == TaskStatus.DONE:
          continue
        tracking_entries.append(
          self._build_graph_tracking_entry(
            task=task,
            relation_types=relation_types or ["流程"],
            projection=projection,
            graph_run_labels=graph_run_labels,
            actor=actor,
          )
        )
      elif task.status != TaskStatus.DONE:
        tracking_entries.append(
          self._build_tracking_entry(
            task=task,
            relation_types=relation_types or ["流程"],
            step_context_map=step_context_map,
            graph_run_labels=graph_run_labels,
            actor=actor,
          )
        )

    # task id as final tiebreaker: cursor pagination requires a fully deterministic order.
    sorted_entries = sorted(
      tracking_entries,
      key=lambda item: (
        item.status == TaskStatus.DONE,
        item.due_date is None,
        _normalize_datetime(item.due_date) if item.due_date is not None else datetime.max.replace(tzinfo=UTC),
        _task_priority_sort_value(item.priority),
        item.task_id,
      ),
    )
    return _paginate_task_center_list(
      sorted_entries,
      limit=limit,
      after_task_id=after_task_id,
      task_id_getter=lambda entry: entry.task_id,
    )

  async def list_task_history(
    self,
    *,
    actor: User,
    limit: int = 20,
    after_task_id: UUID | None = None,
  ) -> TaskCenterListPage[TaskHistoryEntry]:
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
          selectinload(Task.creator).selectinload(User.profile),
          selectinload(Task.assignee).selectinload(User.profile),
          selectinload(Task.department),
          selectinload(Task.watchers),
        )
        .where(or_(*history_filters))
        .order_by(Task.completed_at.desc(), Task.updated_at.desc())
      )
    )

    graph_projection_map = (
      await self._graph_task_projection_map(tasks=tasks)
      if self._task_center_v2_enabled()
      else {}
    )
    graph_run_labels = await self._load_graph_run_label_by_task_id(tasks=tasks)

    entries: list[TaskHistoryEntry] = []
    for task in tasks:
      if self._is_admin_archived_task(task):
        continue
      relation_types: list[str] = []
      if task.creator_id == actor.id:
        relation_types.append("发起")
      if task.assignee_id == actor.id:
        relation_types.append("执行")
      if any(watcher.user_id == actor.id for watcher in task.watchers):
        relation_types.append("关注")
      if task.id in workflow_related_task_ids or task.id in graph_projection_map:
        relation_types.append("流程")
      projection = graph_projection_map.get(task.id)
      if projection is not None:
        if projection.status != TaskStatus.DONE:
          continue
        entries.append(
          self._build_graph_history_entry(
            task=task,
            relation_types=relation_types or ["相关"],
            projection=projection,
            graph_run_labels=graph_run_labels,
          )
        )
      elif task.status == TaskStatus.DONE:
        entries.append(
          self._build_history_entry(
            task=task,
            relation_types=relation_types or ["相关"],
            graph_run_labels=graph_run_labels,
            status=task.status,
          )
        )

    # task id as final tiebreaker: cursor pagination requires a fully deterministic order.
    sorted_entries = sorted(
      entries,
      key=lambda item: (
        item.completed_at is None,
        _normalize_datetime(item.completed_at) if item.completed_at is not None else datetime.max.replace(tzinfo=UTC),
        item.task_id,
      ),
      reverse=True,
    )
    return _paginate_task_center_list(
      sorted_entries,
      limit=limit,
      after_task_id=after_task_id,
      task_id_getter=lambda entry: entry.task_id,
    )

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
    # Order this update (notably the assignee transfer path) against concurrent
    # delegates/transitions (see the lock helper).
    await self._refresh_task_row_with_lock(task_id=task.id)
    if not await self._can_operate_task(actor=actor, task=task):
      raise AuthorizationError("当前账号不能修改该任务。")

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
    # Normalize both sides to aware UTC before comparing: the incoming value may be
    # naive while the stored one is aware (or vice versa on SQLite), and comparing
    # naive with aware datetimes raises TypeError.
    normalized_due_date = _normalize_datetime(due_date) if due_date is not None else None
    normalized_previous_due_date = _normalize_datetime(previous_due_date) if previous_due_date is not None else None
    due_date_changed = due_date is not None and normalized_due_date != normalized_previous_due_date
    if due_date is not None:
      if due_date_changed and _is_overdue(due_date=previous_due_date, now=datetime.now(UTC)):
        if normalized_previous_due_date is not None and normalized_due_date <= normalized_previous_due_date:
          raise ConflictError("逾期任务延期时必须设置更晚的截止时间。")
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
    if due_date_changed:
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
    # Order this command against concurrent delegates/transitions for both
    # standalone and workflow tasks (see the lock helper).
    await self._refresh_task_row_with_lock(task_id=task.id)

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
    if target_status == TaskStatus.DONE:
      await self._maybe_progress_template_graph_after_completion(
        actor=actor,
        task=task,
        expected_policy="on_review_approved",
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
    if self._is_admin_archived_task(task):
      raise ConflictError("任务已归档，无法继续操作。")
    # Order this command against concurrent delegates/submits for both
    # standalone and workflow tasks before the DOING→REVIEW/DONE transition.
    await self._refresh_task_row_with_lock(task_id=task.id)
    await self._ensure_task_assignee_or_manager(actor=actor, task=task)
    if self._is_graph_run_root_shell_task(task):
      raise ConflictError("请在待办中打开具体步骤任务后再提交，不要在使用制作/批次根任务提交。")
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

    _instance, _node, _template_node, completion_policy = await self._load_template_graph_node_context(
      task=task,
    )
    direct_complete = completion_policy == "on_submit_deliverable"

    metadata = self._copy_task_metadata(task)
    metadata.update(
      {
        "latest_deliverable_summary": normalized_summary,
        "latest_deliverable_attachment_ids": validated_attachment_ids,
        "latest_deliverable_submitted_at": now.isoformat(),
        "latest_deliverable_submitted_by_user_id": str(actor.id),
      }
    )
    if direct_complete:
      metadata["latest_review_state"] = "approved"
      task.extra_metadata = metadata
      task.status = TaskStatus.DONE
      task.updated_at = now
      task.started_at = task.started_at or now
      task.completed_at = now
      await self._sync_graph_projection_for_task_status(
        task=task,
        target_status=TaskStatus.DONE,
        reference_time=now,
      )
      await self._create_task_log(
        task_id=task.id,
        operator_id=actor.id,
        action_type=TaskActionType.STATUS_CHANGED,
        from_status=TaskStatus.DOING,
        to_status=TaskStatus.DONE,
        detail={
          "action": "submit_deliverable",
          "summary": normalized_summary,
          "attachment_ids": validated_attachment_ids,
          "status": TaskStatus.DONE.value,
        },
      )
      await self._maybe_progress_template_graph_after_completion(
        actor=actor,
        task=task,
        expected_policy="on_submit_deliverable",
      )
      await self._session.commit()
      await self._session.refresh(task)
      return task

    metadata["latest_review_state"] = "pending_review"
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
    from app.services.workflow_orchestration_service import WorkflowOrchestrationService

    if WorkflowOrchestrationService.is_template_graph_projection(task):
      orchestration = WorkflowOrchestrationService(
        self._session,
        workflow_graph_service=self._workflow_graph_service,
        task_service=self,
      )
      await orchestration.on_task_accepted(actor=actor, task=task)
      await self._create_task_log(
        task_id=task.id,
        operator_id=actor.id,
        action_type=TaskActionType.ASSIGNED,
        detail={
          "action": HANDSHAKE_ACCEPTED,
          "status": task.status.value,
          "source": "template_graph",
        },
      )
      await self._session.commit()
      await self._session.refresh(task)
      return task

    if not self._uses_graph_handshake_cycle(task=task):
      await self._ensure_task_handshake_actor(actor=actor, task=task)
      if task.status != TaskStatus.TODO:
        raise ConflictError("只有待处理任务才能执行接受动作。")
      now = datetime.now(UTC)
      metadata = self._copy_task_metadata(task)
      metadata.update(
        {
          "work_item_acceptance_state": HANDSHAKE_ACCEPTED,
          "latest_acceptance_actor_user_id": str(actor.id),
          "latest_acceptance_at": now.isoformat(),
        }
      )
      task.extra_metadata = metadata
      task.updated_at = now
      await self._create_task_log(
        task_id=task.id,
        operator_id=actor.id,
        action_type=TaskActionType.ASSIGNED,
        detail={
          "action": HANDSHAKE_ACCEPTED,
          "status": task.status.value,
          "source": "standalone_work_item",
        },
      )
      await self._session.commit()
      await self._session.refresh(task)
      return task
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

  async def _build_assignment_candidates(
    self,
    *,
    department_ids: set[UUID] | None,
    exclude_user_ids: set[UUID],
    query: str | None,
    limit: int,
  ) -> list[AssignmentCandidate]:
    statement = (
      select(User)
      .options(selectinload(User.profile))
      .where(User.status == UserStatus.ACTIVE)
    )
    profile_joined = False
    if department_ids is not None:
      if not department_ids:
        return []
      statement = statement.join(Profile, Profile.user_id == User.id).where(
        Profile.department_id.in_(department_ids)
      )
      profile_joined = True
    normalized_query = (query or "").strip()
    if normalized_query:
      pattern = f"%{normalized_query}%"
      if not profile_joined:
        statement = statement.outerjoin(Profile, Profile.user_id == User.id)
      statement = statement.where(or_(User.email.ilike(pattern), Profile.real_name.ilike(pattern)))
    statement = statement.order_by(User.created_at.asc()).limit(max(1, min(limit, 100)))

    users = list(await self._session.scalars(statement))
    department_name_map: dict[UUID, str] = {}
    dept_ids = {
      user.profile.department_id
      for user in users
      if user.profile is not None and user.profile.department_id is not None
    }
    if dept_ids:
      departments = list(
        await self._session.scalars(select(Department).where(Department.id.in_(dept_ids)))
      )
      department_name_map = {department.id: department.name for department in departments}

    candidates: list[AssignmentCandidate] = []
    for user in users:
      if user.id in exclude_user_ids:
        continue
      profile = user.profile
      department_name = (
        department_name_map.get(profile.department_id)
        if profile is not None and profile.department_id is not None
        else None
      )
      candidates.append(
        AssignmentCandidate(
          user_id=user.id,
          display_name=_user_display_label(user),
          department_name=department_name,
          role_name=user.role.value if user.role is not None else None,
        )
      )
    return candidates

  async def _candidate_scope_department_ids(self, *, actor: User) -> set[UUID]:
    """Managed-scope department set for a non-management actor."""
    managed = await get_effective_managed_department_ids(
      self._session,
      actor.id,
    )
    department_ids: set[UUID] = set(managed) if managed else set()
    actor_department_id = await get_actor_department_id(self._session, actor.id)
    if actor_department_id is not None:
      department_ids.add(actor_department_id)
    return department_ids

  async def list_assignee_candidates(
    self,
    *,
    actor: User,
    scope: str = "managed",
    query: str | None = None,
    limit: int = 20,
  ) -> list[AssignmentCandidate]:
    """Candidates for creating a task.

    ``organization`` scope is only available to actors with org publish rights,
    keeping candidate discovery consistent with ``_resolve_assignee_for_task``.
    """
    ensure_active_user(actor)
    if scope == "organization":
      if not (is_management_role(actor) or await can_publish_org_tasks(self._session, actor)):
        raise AuthorizationError("当前账号无权跨部门指派任务。")
      department_ids: set[UUID] | None = None
    elif is_management_role(actor):
      department_ids = None
    else:
      department_ids = await self._candidate_scope_department_ids(actor=actor)
    return await self._build_assignment_candidates(
      department_ids=department_ids,
      exclude_user_ids=set(),
      query=query,
      limit=limit,
    )

  async def list_delegate_candidates(
    self,
    *,
    actor: User,
    task_id: UUID,
    query: str | None = None,
    limit: int = 20,
  ) -> list[AssignmentCandidate]:
    """Candidates a delegator may transfer this task to.

    Scope reflects delegation authority: managers / org publishers see the
    organization, a plain assignee sees their own org unit. The delegate command
    re-validates authorization; this list is not an authorization token.
    """
    task = await self.get_task(actor=actor, task_id=task_id)
    if is_standalone(task):
      await self._ensure_standalone_delegate_authority(actor=actor, task=task)
    else:
      await self._ensure_task_handshake_actor(actor=actor, task=task)
    if is_management_role(actor) or await can_publish_org_tasks(self._session, actor):
      department_ids: set[UUID] | None = None
    else:
      department_ids = await self._candidate_scope_department_ids(actor=actor)
    exclude = {task.assignee_id}
    return await self._build_assignment_candidates(
      department_ids=department_ids,
      exclude_user_ids=exclude,
      query=query,
      limit=limit,
    )

  async def delegate_task_assignment(
    self,
    *,
    actor: User,
    task_id: UUID,
    assignee_id: UUID,
    reason: str,
  ) -> Task:
    """Delegate a Work Item.

    Assignment capabilities belong to the Work Item, not to the existence of a
    graph node. Standalone and workflow-human tasks share permission and audit
    logic but have different side effects (a standalone delegate must never
    touch graph runtime).
    """
    task = await self.get_task(actor=actor, task_id=task_id)
    if is_standalone(task):
      return await self._delegate_standalone_task(
        actor=actor,
        task=task,
        assignee_id=assignee_id,
        reason=reason,
      )
    if self._uses_graph_handshake_cycle(task=task):
      return await self._delegate_workflow_human_task(
        actor=actor,
        task=task,
        assignee_id=assignee_id,
        reason=reason,
      )
    raise ConflictError("当前任务不支持转办。")

  async def _delegate_standalone_task(
    self,
    *,
    actor: User,
    task: Task,
    assignee_id: UUID,
    reason: str,
  ) -> Task:
    # Compare-and-set on the assignee observed when this command entered: a
    # delegate decision made against a snapshot that another transfer has
    # already invalidated must fail with a stable conflict instead of quietly
    # re-transferring (e.g. assignee and admin delegating simultaneously).
    expected_assignee_id = task.assignee_id
    await self._refresh_task_row_with_lock(task_id=task.id)
    if task.assignee_id != expected_assignee_id:
      raise ConflictError("任务执行人已变更，请刷新后重试。")
    await self._ensure_standalone_delegate_authority(actor=actor, task=task)
    # Product decision: REVIEW is the creator's acceptance step, not a delegable
    # execution responsibility. DONE tasks are terminal.
    if task.status not in {TaskStatus.TODO, TaskStatus.DOING}:
      raise ConflictError("只有待处理或进行中的任务才能转办。")

    normalized_reason = reason.strip()
    if not normalized_reason:
      raise ConflictError("转办时必须填写原因。")

    next_assignee = await self._resolve_delegate_assignee(actor=actor, task=task, assignee_id=assignee_id)
    previous_assignee_id = task.assignee_id
    now = datetime.now(UTC)
    task.assignee_id = next_assignee.id
    task.updated_at = now
    metadata = self._copy_task_metadata(task)
    metadata.update(
      {
        "latest_delegate_reason": normalized_reason,
        "latest_delegate_from_user_id": str(previous_assignee_id),
        "latest_delegate_to_user_id": str(next_assignee.id),
        "latest_delegate_at": now.isoformat(),
        "latest_delegate_actor_user_id": str(actor.id),
      }
    )
    task.extra_metadata = metadata
    await self._create_task_log(
      task_id=task.id,
      operator_id=actor.id,
      action_type=TaskActionType.ASSIGNED,
      detail={
        "action": "delegated",
        "execution_mode": "standalone",
        "reason": normalized_reason,
        "previous_assignee_id": str(previous_assignee_id),
        "assignee_id": str(next_assignee.id),
        "assignee_email": next_assignee.email,
        "status": task.status.value,
        # Audit distinction: forced transfer by task admin vs self-initiated.
        "delegated_by_admin": actor.id != previous_assignee_id,
      },
    )
    await self._session.commit()
    await self._session.refresh(task)
    await self._send_assignment_notification(task=task, assignee=next_assignee)
    return task

  async def _delegate_workflow_human_task(
    self,
    *,
    actor: User,
    task: Task,
    assignee_id: UUID,
    reason: str,
  ) -> Task:
    # Same compare-and-set as the standalone delegate: lock the row and fail
    # with a stable conflict if another transfer already changed the assignee.
    expected_assignee_id = task.assignee_id
    await self._refresh_task_row_with_lock(task_id=task.id)
    if task.assignee_id != expected_assignee_id:
      raise ConflictError("任务执行人已变更，请刷新后重试。")
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
    if is_standalone(task):
      # Order this command against concurrent reviews / delegates.
      await self._refresh_task_row_with_lock(task_id=task.id)
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
      await self._maybe_progress_template_graph_after_completion(
        actor=actor,
        task=task,
        expected_policy="on_review_approved",
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
    self._session.expire(task, ["watchers"])

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

  @staticmethod
  def _is_admin_archived_task(task: Task) -> bool:
    return TaskService._copy_task_metadata(task).get("admin_archived") is True

  async def _resolve_graph_instance_id_for_archive(self, *, task: Task) -> UUID | None:
    metadata = self._copy_task_metadata(task)
    instance_id = self._read_uuid_metadata(metadata, "workflow_graph_instance_id")
    if instance_id is not None:
      return instance_id
    instance = await self._session.scalar(
      select(WorkflowGraphInstance.id).where(WorkflowGraphInstance.source_id == task.id)
    )
    return instance

  async def _mark_task_admin_archived(
    self,
    *,
    task: Task,
    actor: User,
    reason: str,
    source_task_id: UUID,
    now: datetime,
  ) -> None:
    if self._is_admin_archived_task(task):
      return

    metadata = self._copy_task_metadata(task)
    previous_status = task.status
    metadata.update(
      {
        "admin_archived": True,
        "admin_archived_at": now.isoformat(),
        "admin_archived_by_user_id": str(actor.id),
        "admin_archive_reason": reason,
        "admin_archive_source_task_id": str(source_task_id),
      }
    )
    task.extra_metadata = metadata
    task.status = TaskStatus.DONE
    task.completed_at = now
    task.updated_at = now

    await self._create_task_log(
      task_id=task.id,
      operator_id=actor.id,
      action_type=TaskActionType.CLOSED,
      from_status=previous_status,
      to_status=TaskStatus.DONE,
      detail={
        "action": "admin_archive",
        "reason": reason,
        "source_task_id": str(source_task_id),
      },
    )

  async def archive_task_by_admin(
    self,
    *,
    actor: User,
    task_id: UUID,
    reason: str,
  ) -> tuple[Task, int, list[UUID]]:
    if actor.role != UserRole.ADMIN:
      raise AuthorizationError("仅管理员可以归档任务。")

    task = await self.get_task(actor=actor, task_id=task_id)
    if self._is_admin_archived_task(task):
      raise ConflictError("任务已归档。")

    now = datetime.now(UTC)
    task_ids: set[UUID] = {task.id}
    cancelled_instance_ids: list[UUID] = []

    instance_id = await self._resolve_graph_instance_id_for_archive(task=task)
    if instance_id is not None:
      if self._workflow_graph_service is None:
        raise ConflictError("工作流图引擎未启用，无法终止关联任务流。")
      cancel_children = self._is_graph_run_root_shell_task(task)
      linked_task_ids, cancelled_instance_ids = await self._workflow_graph_service.cancel_instance_by_admin(
        actor_id=actor.id,
        instance_id=instance_id,
        reason=reason,
        cancel_active_child_runs=cancel_children,
      )
      task_ids |= linked_task_ids

    for linked_task_id in task_ids:
      linked_task = await self._session.get(Task, linked_task_id)
      if linked_task is None:
        continue
      await self._mark_task_admin_archived(
        task=linked_task,
        actor=actor,
        reason=reason,
        source_task_id=task.id,
        now=now,
      )

    await self._session.commit()
    await self._session.refresh(task)
    return task, len(task_ids), cancelled_instance_ids

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

  async def get_task_stats_summary(
    self,
    *,
    actor: User,
    department_id: UUID | None = None,
    include_subtree: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
  ) -> TaskStatsSummary:
    now = datetime.now(UTC)
    resolved_start, resolved_end, start_at, end_at = _resolve_task_stats_period(
      start_date=start_date,
      end_date=end_date,
      now=now,
    )
    filters = await self._build_task_stats_filters(
      actor=actor,
      department_id=department_id,
      include_subtree=include_subtree,
    )
    created_condition = and_(Task.created_at >= start_at, Task.created_at < end_at)
    completed_condition = and_(Task.completed_at >= start_at, Task.completed_at < end_at)
    due_condition = and_(Task.due_date >= start_at, Task.due_date < end_at)
    matured_cutoff = min(now, end_at)
    matured_due_condition = and_(due_condition, Task.due_date < matured_cutoff)
    on_time_condition = and_(
      matured_due_condition,
      Task.completed_at.is_not(None),
      Task.completed_at <= Task.due_date,
    )
    period_overdue_condition = and_(
      matured_due_condition,
      or_(Task.completed_at.is_(None), Task.completed_at > Task.due_date),
    )
    current_overdue_condition = and_(
      Task.due_date.is_not(None),
      Task.due_date < now,
      Task.status != TaskStatus.DONE,
    )
    aggregate = select(
      func.count(Task.id),
      func.count(Task.id).filter(Task.status == TaskStatus.DONE),
      func.count(Task.id).filter(current_overdue_condition),
      func.count(Task.id).filter(created_condition),
      func.count(Task.id).filter(completed_condition),
      func.count(Task.id).filter(due_condition),
      func.count(Task.id).filter(matured_due_condition),
      func.count(Task.id).filter(on_time_condition),
      func.count(Task.id).filter(period_overdue_condition),
      func.count(Task.id).filter(Task.status != TaskStatus.DONE),
      *[
        func.count(Task.id).filter(Task.status == status).label(f"status_{status.value}")
        for status in TaskStatus
      ],
    ).where(*filters)
    row = (await self._session.execute(aggregate)).one()
    (
      total_tasks,
      completed_tasks,
      overdue_tasks,
      created_tasks,
      period_completed_tasks,
      due_tasks,
      matured_due_tasks,
      on_time_completed_tasks,
      period_overdue_tasks,
      current_open_tasks,
      *status_counts,
    ) = [int(value or 0) for value in row]
    tasks_by_status = dict(zip(TaskStatus, status_counts, strict=True))
    completion_rate = round(completed_tasks / total_tasks, 4) if total_tasks else 0.0
    overdue_rate = round(overdue_tasks / total_tasks, 4) if total_tasks else 0.0
    on_time_completion_rate = (
      round(on_time_completed_tasks / matured_due_tasks, 4)
      if matured_due_tasks
      else 0.0
    )
    return TaskStatsSummary(
      total_tasks=total_tasks,
      completed_tasks=completed_tasks,
      completion_rate=completion_rate,
      overdue_tasks=overdue_tasks,
      overdue_rate=overdue_rate,
      tasks_by_status=tasks_by_status,
      start_date=resolved_start,
      end_date=resolved_end,
      created_tasks=created_tasks,
      period_completed_tasks=period_completed_tasks,
      due_tasks=due_tasks,
      matured_due_tasks=matured_due_tasks,
      on_time_completed_tasks=on_time_completed_tasks,
      on_time_completion_rate=on_time_completion_rate,
      current_open_tasks=current_open_tasks,
      period_overdue_tasks=period_overdue_tasks,
    )

  async def get_task_workload(
    self,
    *,
    actor: User,
    department_id: UUID | None = None,
    include_subtree: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
  ) -> list[TaskWorkloadEntry]:
    now = datetime.now(UTC)
    _, _, start_at, end_at = _resolve_task_stats_period(
      start_date=start_date,
      end_date=end_date,
      now=now,
    )
    filters = await self._build_task_stats_filters(
      actor=actor,
      department_id=department_id,
      include_subtree=include_subtree,
    )
    created_condition = and_(Task.created_at >= start_at, Task.created_at < end_at)
    completed_condition = and_(Task.completed_at >= start_at, Task.completed_at < end_at)
    due_condition = and_(Task.due_date >= start_at, Task.due_date < end_at)
    matured_due_condition = and_(due_condition, Task.due_date < min(now, end_at))
    on_time_condition = and_(
      matured_due_condition,
      Task.completed_at.is_not(None),
      Task.completed_at <= Task.due_date,
    )
    period_overdue_condition = and_(
      matured_due_condition,
      or_(Task.completed_at.is_(None), Task.completed_at > Task.due_date),
    )
    current_overdue_condition = and_(
      Task.due_date.is_not(None),
      Task.due_date < now,
      Task.status != TaskStatus.DONE,
    )
    assignee_label = func.coalesce(Profile.real_name, User.email)
    rows = (
      await self._session.execute(
        select(
          User.id,
          User.email,
          assignee_label,
          Profile.department_id,
          Department.name,
          func.count(Task.id),
          func.count(Task.id).filter(Task.status != TaskStatus.DONE),
          func.count(Task.id).filter(Task.status == TaskStatus.DONE),
          func.count(Task.id).filter(current_overdue_condition),
          func.count(Task.id).filter(created_condition),
          func.count(Task.id).filter(completed_condition),
          func.count(Task.id).filter(due_condition),
          func.count(Task.id).filter(matured_due_condition),
          func.count(Task.id).filter(on_time_condition),
          func.count(Task.id).filter(period_overdue_condition),
        )
        .join(User, User.id == Task.assignee_id)
        .outerjoin(Profile, Profile.user_id == User.id)
        .outerjoin(Department, Department.id == Profile.department_id)
        .where(*filters)
        .group_by(User.id, User.email, Profile.real_name, Profile.department_id, Department.name)
        .order_by(Department.name.asc().nulls_first(), assignee_label.asc())
      )
    ).all()
    result: list[TaskWorkloadEntry] = []
    for row in rows:
      matured_due_tasks = int(row[12] or 0)
      on_time_completed_tasks = int(row[13] or 0)
      result.append(
        TaskWorkloadEntry(
          assignee_id=row[0],
          assignee_email=row[1],
          assignee_label=row[2],
          department_id=row[3],
          department_name=row[4],
          total_tasks=int(row[5] or 0),
          open_tasks=int(row[6] or 0),
          completed_tasks=int(row[7] or 0),
          overdue_tasks=int(row[8] or 0),
          created_tasks=int(row[9] or 0),
          period_completed_tasks=int(row[10] or 0),
          due_tasks=int(row[11] or 0),
          matured_due_tasks=matured_due_tasks,
          on_time_completed_tasks=on_time_completed_tasks,
          on_time_completion_rate=(
            round(on_time_completed_tasks / matured_due_tasks, 4)
            if matured_due_tasks
            else 0.0
          ),
          period_overdue_tasks=int(row[14] or 0),
        )
      )
    return result

  async def list_task_stats_scopes(self, *, actor: User) -> TaskStatsScopes:
    ensure_active_user(actor)
    if is_management_role(actor):
      departments = list(
        await self._session.scalars(
          select(Department)
          .where(Department.is_active.is_(True))
          .order_by(Department.sort_order.asc(), Department.name.asc())
        )
      )
      return TaskStatsScopes(
        mode="organization",
        departments=[TaskStatsScopeOption(id=item.id, label=item.name) for item in departments],
      )

    department_ids = await get_effective_managed_department_ids(self._session, actor.id)
    if not department_ids:
      return TaskStatsScopes(mode="personal", departments=[])
    departments = list(
      await self._session.scalars(
        select(Department)
        .where(Department.id.in_(department_ids), Department.is_active.is_(True))
        .order_by(Department.sort_order.asc(), Department.name.asc())
      )
    )
    return TaskStatsScopes(
      mode="organization",
      departments=[TaskStatsScopeOption(id=item.id, label=item.name) for item in departments],
    )

  async def list_task_stats_details(
    self,
    *,
    actor: User,
    metric: str,
    department_id: UUID | None = None,
    include_subtree: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
    assignee_id: UUID | None = None,
    cursor: UUID | None = None,
    limit: int = 50,
  ) -> TaskStatsDetailsPage:
    now = datetime.now(UTC)
    _, _, start_at, end_at = _resolve_task_stats_period(
      start_date=start_date,
      end_date=end_date,
      now=now,
    )
    filters = await self._build_task_stats_filters(
      actor=actor,
      department_id=department_id,
      include_subtree=include_subtree,
    )
    due_condition = and_(Task.due_date >= start_at, Task.due_date < end_at)
    matured_due_condition = and_(due_condition, Task.due_date < min(now, end_at))
    metric_conditions = {
      "created": and_(Task.created_at >= start_at, Task.created_at < end_at),
      "completed": and_(Task.completed_at >= start_at, Task.completed_at < end_at),
      "due": due_condition,
      "overdue": and_(
        matured_due_condition,
        or_(Task.completed_at.is_(None), Task.completed_at > Task.due_date),
      ),
      "on_time": and_(
        matured_due_condition,
        Task.completed_at.is_not(None),
        Task.completed_at <= Task.due_date,
      ),
      "open": Task.status != TaskStatus.DONE,
    }
    metric_condition = metric_conditions.get(metric)
    if metric_condition is None:
      raise ConflictError("不支持的统计明细指标。")
    statement = select(Task).where(*filters, metric_condition)
    if assignee_id is not None:
      statement = statement.where(Task.assignee_id == assignee_id)
    if cursor is not None:
      statement = statement.where(Task.id > cursor)
    tasks = list(
      await self._session.scalars(
        statement
        .options(
          selectinload(Task.assignee).selectinload(User.profile),
          selectinload(Task.department),
        )
        .order_by(Task.id.asc())
        .limit(limit + 1)
      )
    )
    has_more = len(tasks) > limit
    page_tasks = tasks[:limit]
    graph_run_labels = await self._load_graph_run_label_by_task_id(tasks=page_tasks)
    items = [
      TaskStatsDetailEntry(
        task_id=task.id,
        title=task.title,
        assignee_id=task.assignee_id,
        assignee_label=_user_display_label(task.assignee) or task.assignee.email,
        department_id=task.department_id,
        department_name=task.department.name if task.department is not None else None,
        source_type=task.source_type,
        run_label=resolve_task_run_label(
          title=task.title,
          metadata=self._copy_task_metadata(task),
          graph_run_label=graph_run_labels.get(task.id),
        ),
        due_date=task.due_date,
        completed_at=task.completed_at,
        is_overdue=bool(
          task.due_date is not None
          and _normalize_datetime(task.due_date) < now
          and (
            task.completed_at is None
            or _normalize_datetime(task.completed_at) > _normalize_datetime(task.due_date)
          )
        ),
      )
      for task in page_tasks
    ]
    return TaskStatsDetailsPage(
      items=items,
      next_cursor=page_tasks[-1].id if has_more and page_tasks else None,
      has_more=has_more,
    )

  async def _build_task_stats_filters(
    self,
    *,
    actor: User,
    department_id: UUID | None,
    include_subtree: bool,
  ):
    ensure_active_user(actor)
    filters: list[Any] = [
      Task.extra_metadata["admin_archived"].as_boolean().is_not(True),
      Task.extra_metadata["workflow_graph_root_task"].as_boolean().is_not(True),
    ]
    if is_management_role(actor):
      if department_id is None:
        return filters
      department_ids = (
        await expand_department_ids(self._session, {department_id})
        if include_subtree
        else {department_id}
      )
      return [*filters, Task.department_id.in_(department_ids)]

    managed_department_ids = await get_effective_managed_department_ids(self._session, actor.id)
    if not managed_department_ids:
      if department_id is not None:
        raise AuthorizationError("普通员工仅可查看本人任务统计。")
      return [*filters, Task.assignee_id == actor.id]

    if department_id is None:
      return [*filters, Task.department_id.in_(managed_department_ids)]
    if department_id not in managed_department_ids:
      raise AuthorizationError("无权查看该部门统计。")
    selected_ids = (
      (await expand_department_ids(self._session, {department_id})) & managed_department_ids
      if include_subtree
      else {department_id}
    )
    return [*filters, Task.department_id.in_(selected_ids)]

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
