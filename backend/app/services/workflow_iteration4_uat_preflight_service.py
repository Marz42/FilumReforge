"""Read-only target-environment preparation checks for Iteration 4 UAT."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
  DepartmentCapability,
  TaskStatus,
  UserStatus,
  WorkflowGraphTemplateStatus,
)
from app.models import (
  Department,
  Profile,
  Task,
  User,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateEdge,
  WorkflowGraphTemplateNode,
)
from app.schemas.workflow_graph import (
  WorkflowIteration4UatCheckRead,
  WorkflowIteration4UatDepartmentCandidateRead,
  WorkflowIteration4UatPreflightRead,
  WorkflowIteration4UatStatsSampleRead,
  WorkflowIteration4UatTemplateCandidateRead,
)
from app.services.access_control import (
  TASK_SCOPE_TYPES,
  get_actor_department_id,
  get_effective_managed_department_ids,
  has_department_capability,
  is_management_role,
)
from app.services.workflow_access_policy import WorkflowAccessPolicy
from app.services.workflow_graph_template_capabilities import (
  build_fork_target_code_index,
  compute_template_capabilities,
)
from app.services.workflow_graph_template_governance_service import (
  WorkflowGraphTemplateGovernanceService,
)
from app.services.workflow_video_template_seed_data import (
  TOPIC_MEETING_BATCH_CODE,
  VIDEO_PRODUCTION_CODE,
)


_SHANGHAI = ZoneInfo("Asia/Shanghai")
_OPEN_STATS_STATUSES = {TaskStatus.TODO, TaskStatus.DOING, TaskStatus.REVIEW}


class WorkflowIteration4UatPreflightService:
  """Report whether manual UAT prerequisites exist; never claim that UAT passed."""

  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def build_report(self, *, actor: User) -> WorkflowIteration4UatPreflightRead:
    policy = WorkflowAccessPolicy(self._session)
    await policy.ensure_can_manage_templates(actor=actor)

    all_templates = list(await self._session.scalars(select(WorkflowGraphTemplate)))
    operational = [
      template
      for template in all_templates
      if template.status in {
        WorkflowGraphTemplateStatus.DRAFT,
        WorkflowGraphTemplateStatus.ACTIVE,
      }
    ]
    manageable = await policy.filter_manageable_templates(actor=actor, templates=operational)
    active_templates = [
      template
      for template in all_templates
      if template.status == WorkflowGraphTemplateStatus.ACTIVE
    ]
    readable_active = await policy.filter_readable_templates(
      actor=actor,
      templates=active_templates,
    )
    inspected_ids = {
      template.id for template in [*manageable, *readable_active]
    }
    nodes = (
      list(
        await self._session.scalars(
          select(WorkflowGraphTemplateNode).where(
            WorkflowGraphTemplateNode.template_id.in_(inspected_ids)
          )
        )
      )
      if inspected_ids
      else []
    )
    edges = (
      list(
        await self._session.scalars(
          select(WorkflowGraphTemplateEdge).where(
            WorkflowGraphTemplateEdge.template_id.in_(inspected_ids)
          )
        )
      )
      if inspected_ids
      else []
    )
    nodes_by_template: dict[UUID, list[WorkflowGraphTemplateNode]] = {}
    edges_by_template: dict[UUID, list[WorkflowGraphTemplateEdge]] = {}
    for node in nodes:
      nodes_by_template.setdefault(node.template_id, []).append(node)
    for edge in edges:
      edges_by_template.setdefault(edge.template_id, []).append(edge)

    fork_target_codes = build_fork_target_code_index(
      [template for template in all_templates if template.status == WorkflowGraphTemplateStatus.ACTIVE]
    )
    active_direct = [
      template
      for template in readable_active
      if compute_template_capabilities(
        template=template,
        nodes=nodes_by_template.get(template.id, []),
        edges=edges_by_template.get(template.id, []),
        fork_target_codes=fork_target_codes,
      ).can_instantiate_directly
    ]
    domain_neutral = next(
      (template for template in active_direct if self._is_domain_neutral_candidate(template)),
      None,
    )
    video_batch = next(
      (
        template
        for template in readable_active
        if template.base_code == TOPIC_MEETING_BATCH_CODE
      ),
      None,
    )
    video_child = next(
      (
        template
        for template in readable_active
        if template.base_code == VIDEO_PRODUCTION_CODE
      ),
      None,
    )
    designer_draft = next(
      (template for template in manageable if template.status == WorkflowGraphTemplateStatus.DRAFT),
      None,
    )

    governance = await WorkflowGraphTemplateGovernanceService(
      self._session
    ).audit_manageable_templates(actor=actor)
    department_candidates, visible_department_ids = await self._department_candidates(actor=actor)
    stats_sample = await self._stats_sample(
      actor=actor,
      visible_department_ids=visible_department_ids,
    )

    checks = self._build_checks(
      governance_error_count=governance.error_count,
      governance_warning_count=governance.warning_count + governance.review_count,
      department_candidates=department_candidates,
      domain_neutral=domain_neutral,
      video_batch=video_batch,
      video_child=video_child,
      designer_draft=designer_draft,
      stats_sample=stats_sample,
    )
    candidates: list[WorkflowIteration4UatTemplateCandidateRead] = []
    for kind, template in (
      ("domain_neutral", domain_neutral),
      ("video_batch", video_batch),
      ("video_child", video_child),
      ("designer_draft", designer_draft),
    ):
      if template is not None:
        candidates.append(self._template_candidate(kind=kind, template=template))

    blocking_count = sum(check.status == "blocked" for check in checks)
    warning_count = sum(check.status == "warning" for check in checks)
    return WorkflowIteration4UatPreflightRead(
      generated_at=datetime.now(UTC),
      preflight_ready=blocking_count == 0,
      manual_uat_required=True,
      blocking_count=blocking_count,
      warning_count=warning_count,
      checks=checks,
      template_candidates=candidates,
      department_candidates=department_candidates,
      stats_sample=stats_sample,
    )

  async def _department_candidates(
    self,
    *,
    actor: User,
  ) -> tuple[list[WorkflowIteration4UatDepartmentCandidateRead], set[UUID]]:
    departments = list(
      await self._session.scalars(select(Department).where(Department.is_active.is_(True)))
    )
    if is_management_role(actor):
      visible_ids = {department.id for department in departments}
    else:
      visible_ids = await get_effective_managed_department_ids(
        self._session,
        actor.id,
        scope_types=TASK_SCOPE_TYPES,
      )
      if await has_department_capability(
        self._session,
        actor_id=actor.id,
        capability=DepartmentCapability.MANAGE_TEMPLATES,
      ):
        actor_department_id = await get_actor_department_id(self._session, actor.id)
        if actor_department_id is not None:
          visible_ids.add(actor_department_id)

    user_rows = list(
      (
        await self._session.execute(
          select(Profile.department_id, User.id)
          .join(User, User.id == Profile.user_id)
          .where(
            Profile.department_id.in_(visible_ids),
            User.status == UserStatus.ACTIVE,
          )
        )
      ).all()
    ) if visible_ids else []
    member_ids_by_department: dict[UUID, set[UUID]] = {}
    for department_id, user_id in user_rows:
      member_ids_by_department.setdefault(department_id, set()).add(user_id)

    candidates = [
      WorkflowIteration4UatDepartmentCandidateRead(
        department_id=department.id,
        department_name=department.name,
        active_member_count=len(member_ids_by_department.get(department.id, set())),
        manager_user_id=department.manager_id,
      )
      for department in departments
      if department.id in visible_ids
      and department.manager_id is not None
      and department.manager_id in member_ids_by_department.get(department.id, set())
      and len(member_ids_by_department.get(department.id, set())) >= 3
    ]
    candidates.sort(key=lambda item: item.department_name)
    return candidates, visible_ids

  async def _stats_sample(
    self,
    *,
    actor: User,
    visible_department_ids: set[UUID],
  ) -> WorkflowIteration4UatStatsSampleRead:
    local_now = datetime.now(_SHANGHAI)
    local_start = datetime.combine(local_now.date().replace(day=1), time.min, tzinfo=_SHANGHAI)
    next_month = (local_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    start = local_start.astimezone(UTC)
    end = next_month.astimezone(UTC)

    statement = select(Task)
    if not is_management_role(actor):
      if visible_department_ids:
        statement = statement.where(Task.department_id.in_(visible_department_ids))
      else:
        statement = statement.where(Task.assignee_id == actor.id)
    tasks = list(await self._session.scalars(statement))
    eligible = [task for task in tasks if self._is_stats_eligible(task)]
    return WorkflowIteration4UatStatsSampleRead(
      start_date=local_start.date().isoformat(),
      end_date=(next_month.date() - timedelta(days=1)).isoformat(),
      created_count=sum(self._in_period(task.created_at, start=start, end=end) for task in eligible),
      completed_count=sum(
        self._in_period(task.completed_at, start=start, end=end) for task in eligible
      ),
      due_count=sum(self._in_period(task.due_date, start=start, end=end) for task in eligible),
      current_open_count=sum(task.status in _OPEN_STATS_STATUSES for task in eligible),
    )

  def _build_checks(
    self,
    *,
    governance_error_count: int,
    governance_warning_count: int,
    department_candidates: list[WorkflowIteration4UatDepartmentCandidateRead],
    domain_neutral: WorkflowGraphTemplate | None,
    video_batch: WorkflowGraphTemplate | None,
    video_child: WorkflowGraphTemplate | None,
    designer_draft: WorkflowGraphTemplate | None,
    stats_sample: WorkflowIteration4UatStatsSampleRead,
  ) -> list[WorkflowIteration4UatCheckRead]:
    checks: list[WorkflowIteration4UatCheckRead] = []
    if governance_error_count:
      checks.append(
        self._check(
          "P-01",
          "templates",
          "blocked",
          "模板数据治理",
          f"仍有 {governance_error_count} 项确定错误。",
          "先在“数据检查”中处理确定错误。",
        )
      )
    elif governance_warning_count:
      checks.append(
        self._check(
          "P-01",
          "templates",
          "warning",
          "模板数据治理",
          f"无确定错误，仍有 {governance_warning_count} 项需清理或人工确认。",
          "确认 intentional global，并记录结论。",
        )
      )
    else:
      checks.append(self._check("P-01", "templates", "pass", "模板数据治理", "未发现范围或依赖问题。"))

    checks.append(
      self._check(
        "P-02",
        "accounts",
        "pass" if department_candidates else "blocked",
        "协同账号与部门",
        (
          f"找到 {len(department_candidates)} 个具备部门负责人和至少 3 名活跃成员的候选部门。"
          if department_candidates
          else "没有找到同时具备部门负责人和至少 3 名活跃成员的可管理部门。"
        ),
        None if department_candidates else "补齐部门负责人和 A/B/C 三个活跃成员账号。",
      )
    )
    checks.append(
      self._check(
        "P-03",
        "templates",
        "pass" if domain_neutral else "warning",
        "非视频通用模板",
        (
          f"可使用「{domain_neutral.name}」执行领域中立黄金路径。"
          if domain_neutral
          else "尚无可直接发起且不依赖 legacy run_kind 的通用 ACTIVE 模板。"
        ),
        None if domain_neutral else "按 D-01 新建“材料收集”草稿并发布，这也是验收步骤的一部分。",
      )
    )
    video_ready = video_batch is not None and video_child is not None
    checks.append(
      self._check(
        "P-04",
        "templates",
        "pass" if video_ready else "blocked",
        "视频兼容黄金路径",
        (
          "视频批次与制作子模板均已发布。"
          if video_ready
          else "视频批次或制作子模板缺失/未发布，无法执行 N-06。"
        ),
        None if video_ready else "先恢复或发布视频参考模板包，再重新检查。",
      )
    )
    checks.append(
      self._check(
        "P-05",
        "templates",
        "pass" if designer_draft else "warning",
        "设计器草稿",
        (
          f"可使用「{designer_draft.name}」执行 D-01～D-05。"
          if designer_draft
          else "当前没有可管理草稿。"
        ),
        None if designer_draft else "新建空白模板作为结构化设计器验收样本。",
      )
    )
    missing_stats = [
      label
      for label, count in (
        ("本月新增", stats_sample.created_count),
        ("本月完成", stats_sample.completed_count),
        ("本月到期", stats_sample.due_count),
        ("当前未完成", stats_sample.current_open_count),
      )
      if count == 0
    ]
    checks.append(
      self._check(
        "P-06",
        "statistics",
        "pass" if not missing_stats else "warning",
        "S-01 统计样本",
        (
          "本月新增、完成、到期和当前未完成均有样本，可逐项复算。"
          if not missing_stats
          else f"以下统计口径没有样本：{'、'.join(missing_stats)}。"
        ),
        None if not missing_stats else "补充测试任务，避免只验证空状态。",
      )
    )
    checks.append(
      self._check(
        "P-07",
        "manual",
        "manual",
        "人工业务验收",
        "准备检查不代表 UAT 通过；N/R/D 与 S-01 仍须由不同账号实际操作并签字。",
        "按 Memory-Bank 验收清单记录账号、模板、Run ID、结果与备注。",
      )
    )
    return checks

  @staticmethod
  def _is_domain_neutral_candidate(template: WorkflowGraphTemplate) -> bool:
    config = template.config if isinstance(template.config, dict) else {}
    if config.get("run_kind"):
      return False
    return template.base_code not in {TOPIC_MEETING_BATCH_CODE, VIDEO_PRODUCTION_CODE}

  @staticmethod
  def _is_stats_eligible(task: Task) -> bool:
    metadata = task.extra_metadata if isinstance(task.extra_metadata, dict) else {}
    return not metadata.get("admin_archived") and not metadata.get("workflow_graph_root_task")

  @staticmethod
  def _in_period(value: datetime | None, *, start: datetime, end: datetime) -> bool:
    if value is None:
      return False
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return start <= normalized < end

  @staticmethod
  def _template_candidate(
    *,
    kind: Literal["domain_neutral", "video_batch", "video_child", "designer_draft"],
    template: WorkflowGraphTemplate,
  ) -> WorkflowIteration4UatTemplateCandidateRead:
    return WorkflowIteration4UatTemplateCandidateRead(
      kind=kind,
      template_id=template.id,
      code=template.code,
      name=template.name,
      status=template.status,
      scope_mode=template.scope_mode,
      scope_department_ids=[str(item) for item in (template.scope_department_ids or [])],
    )

  @staticmethod
  def _check(
    check_id: str,
    area: Literal["templates", "accounts", "statistics", "manual"],
    status: Literal["pass", "warning", "blocked", "manual"],
    title: str,
    detail: str,
    action: str | None = None,
  ) -> WorkflowIteration4UatCheckRead:
    return WorkflowIteration4UatCheckRead(
      check_id=check_id,
      area=area,
      status=status,
      title=title,
      detail=detail,
      action=action,
    )
