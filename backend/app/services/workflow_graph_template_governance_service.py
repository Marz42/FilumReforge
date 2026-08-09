"""Read-only governance audit for template availability scopes and dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import WorkflowGraphTemplateStatus
from app.models import Department, User, WorkflowGraphTemplate, WorkflowGraphTemplateNode
from app.schemas.workflow_graph import (
  WorkflowGraphTemplateGovernanceAuditRead,
  WorkflowGraphTemplateGovernanceIssueRead,
)
from app.services.workflow_access_policy import WorkflowAccessPolicy


@dataclass(frozen=True, slots=True)
class _DependencyReference:
  kind: Literal["exact_code", "base_code"]
  code: str


class WorkflowGraphTemplateGovernanceService:
  """Inventory risks without mutating published definitions or business scope."""

  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def audit_manageable_templates(
    self,
    *,
    actor: User,
  ) -> WorkflowGraphTemplateGovernanceAuditRead:
    policy = WorkflowAccessPolicy(self._session)
    await policy.ensure_can_manage_templates(actor=actor)

    all_templates = list(
      await self._session.scalars(
        select(WorkflowGraphTemplate).order_by(
          WorkflowGraphTemplate.base_code.asc(),
          WorkflowGraphTemplate.version.desc(),
        )
      )
    )
    operational_templates = [
      template
      for template in all_templates
      if template.status in {
        WorkflowGraphTemplateStatus.DRAFT,
        WorkflowGraphTemplateStatus.ACTIVE,
      }
    ]
    manageable_templates = await policy.filter_manageable_templates(
      actor=actor,
      templates=operational_templates,
    )
    manageable_ids = {template.id for template in manageable_templates}
    nodes = (
      list(
        await self._session.scalars(
          select(WorkflowGraphTemplateNode).where(
            WorkflowGraphTemplateNode.template_id.in_(manageable_ids)
          )
        )
      )
      if manageable_ids
      else []
    )
    nodes_by_template: dict[UUID, list[WorkflowGraphTemplateNode]] = {}
    for node in nodes:
      nodes_by_template.setdefault(node.template_id, []).append(node)

    departments = list(await self._session.scalars(select(Department)))
    department_by_id = {str(department.id): department for department in departments}
    active_by_code = {
      template.code: template
      for template in all_templates
      if template.status == WorkflowGraphTemplateStatus.ACTIVE
    }
    active_by_base = {
      template.base_code: template
      for template in sorted(all_templates, key=lambda item: item.version)
      if template.status == WorkflowGraphTemplateStatus.ACTIVE
    }
    any_by_code = {template.code: template for template in all_templates}

    issues: list[WorkflowGraphTemplateGovernanceIssueRead] = []
    for template in manageable_templates:
      issues.extend(
        self._audit_scope(
          template=template,
          department_by_id=department_by_id,
        )
      )
      for reference in self._dependency_references(
        template=template,
        nodes=nodes_by_template.get(template.id, []),
      ):
        target = (
          active_by_code.get(reference.code)
          if reference.kind == "exact_code"
          else active_by_base.get(reference.code)
        )
        if target is None:
          missing_issue = self._missing_dependency_issue(
            template=template,
            reference=reference,
            any_by_code=any_by_code,
            active_by_base=active_by_base,
          )
          issues.append(missing_issue)
          target = (
            active_by_code.get(missing_issue.suggested_template_code)
            if missing_issue.suggested_template_code
            else None
          )
          if target is None:
            continue
        compatibility_issue = self._scope_compatibility_issue(
          template=template,
          target=target,
          referenced_code=reference.code,
        )
        if compatibility_issue is not None:
          issues.append(compatibility_issue)

    severity_order = {"error": 0, "warning": 1, "review": 2}
    issues.sort(
      key=lambda issue: (
        severity_order[issue.severity],
        issue.template_name.lower(),
        issue.issue_code,
      )
    )
    return WorkflowGraphTemplateGovernanceAuditRead(
      generated_at=datetime.now(UTC),
      template_count=len(manageable_templates),
      error_count=sum(issue.severity == "error" for issue in issues),
      warning_count=sum(issue.severity == "warning" for issue in issues),
      review_count=sum(issue.severity == "review" for issue in issues),
      issues=issues,
    )

  def _audit_scope(
    self,
    *,
    template: WorkflowGraphTemplate,
    department_by_id: dict[str, Department],
  ) -> list[WorkflowGraphTemplateGovernanceIssueRead]:
    scope_ids = self._scope_ids(template)
    issues: list[WorkflowGraphTemplateGovernanceIssueRead] = []
    if template.scope_mode == "global":
      if scope_ids:
        issues.append(
          self._issue(
            template=template,
            issue_code="global_scope_has_department_ids",
            severity="warning",
            category="availability_scope",
            message="全公司可用模板仍保存了部门编号；这些编号不会生效，容易误导后续维护。",
            recommendation=self._scope_repair_recommendation(template),
            affected_department_ids=scope_ids,
          )
        )
      if template.status == WorkflowGraphTemplateStatus.ACTIVE:
        issues.append(
          self._issue(
            template=template,
            issue_code="global_scope_review_required",
            severity="review",
            category="availability_scope",
            message="该已发布模板对全公司可用，请确认这是明确授权而不是历史数据漂移。",
            recommendation="确认无误即可保留；如需缩小范围，请新建版本并在发布前选择可用部门。",
          )
        )
      return issues

    if template.scope_mode != "departments":
      issues.append(
        self._issue(
          template=template,
          issue_code="invalid_scope_mode",
          severity="error",
          category="availability_scope",
          message=f"模板保存了无法识别的可用范围模式：{template.scope_mode}。",
          recommendation=self._scope_repair_recommendation(template),
        )
      )
      return issues

    if not scope_ids:
      issues.append(
        self._issue(
          template=template,
          issue_code="department_scope_empty",
          severity="error",
          category="availability_scope",
          message="模板设置为指定部门可用，但没有任何有效部门。",
          recommendation=self._scope_repair_recommendation(template),
        )
      )
      return issues

    missing_ids = sorted(scope_id for scope_id in scope_ids if scope_id not in department_by_id)
    inactive_ids = sorted(
      scope_id
      for scope_id in scope_ids
      if scope_id in department_by_id and not department_by_id[scope_id].is_active
    )
    if missing_ids:
      issues.append(
        self._issue(
          template=template,
          issue_code="scope_department_missing",
          severity="error",
          category="availability_scope",
          message=f"可用范围包含 {len(missing_ids)} 个已不存在的部门。",
          recommendation=self._scope_repair_recommendation(template),
          affected_department_ids=missing_ids,
        )
      )
    if inactive_ids:
      labels = "、".join(department_by_id[department_id].name for department_id in inactive_ids)
      issues.append(
        self._issue(
          template=template,
          issue_code="scope_department_inactive",
          severity="error",
          category="availability_scope",
          message=f"可用范围包含已停用部门：{labels}。",
          recommendation=self._scope_repair_recommendation(template),
          affected_department_ids=inactive_ids,
        )
      )
    return issues

  def _missing_dependency_issue(
    self,
    *,
    template: WorkflowGraphTemplate,
    reference: _DependencyReference,
    any_by_code: dict[str, WorkflowGraphTemplate],
    active_by_base: dict[str, WorkflowGraphTemplate],
  ) -> WorkflowGraphTemplateGovernanceIssueRead:
    suggested_code: str | None = None
    if reference.kind == "exact_code":
      previous = any_by_code.get(reference.code)
      if previous is not None:
        replacement = active_by_base.get(previous.base_code)
        if replacement is not None:
          suggested_code = replacement.code
    if suggested_code:
      message = f"子流程仍指向非当前发布版本「{reference.code}」。"
      recommendation = (
        f"将引用改为当前已发布版本「{suggested_code}」。"
        f"{self._definition_repair_suffix(template)}"
      )
      issue_code = "stale_child_template_reference"
    else:
      label = "子流程" if reference.kind == "exact_code" else "后续模板链"
      message = f"{label}引用「{reference.code}」不存在或尚未发布。"
      recommendation = (
        f"先发布目标模板，或改为正确的模板编码。"
        f"{self._definition_repair_suffix(template)}"
      )
      issue_code = "missing_template_dependency"
    return self._issue(
      template=template,
      issue_code=issue_code,
      severity="error",
      category="template_dependency",
      message=message,
      recommendation=recommendation,
      referenced_template_code=reference.code,
      suggested_template_code=suggested_code,
    )

  def _scope_compatibility_issue(
    self,
    *,
    template: WorkflowGraphTemplate,
    target: WorkflowGraphTemplate,
    referenced_code: str,
  ) -> WorkflowGraphTemplateGovernanceIssueRead | None:
    if target.scope_mode != "departments":
      return None
    target_ids = set(self._scope_ids(target))
    source_ids = set(self._scope_ids(template))
    affected_ids: list[str]
    if template.scope_mode == "global":
      affected_ids = []
      message = "父模板对全公司可用，但子模板只对部分部门可用；部分运行会在进入子流程时失败。"
    elif template.scope_mode == "departments":
      affected_ids = sorted(source_ids - target_ids)
      if not affected_ids:
        return None
      message = f"子模板缺少父模板范围内的 {len(affected_ids)} 个部门；这些部门的运行无法进入子流程。"
    else:
      return None
    return self._issue(
      template=template,
      issue_code="dependency_scope_mismatch",
      severity="error",
      category="template_dependency",
      message=message,
      recommendation=(
        f"扩大目标模板「{target.name}」的可用部门，或缩小父模板范围。"
        f"{self._definition_repair_suffix(template)}"
      ),
      referenced_template_code=referenced_code,
      suggested_template_code=target.code,
      affected_department_ids=affected_ids,
    )

  def _dependency_references(
    self,
    *,
    template: WorkflowGraphTemplate,
    nodes: list[WorkflowGraphTemplateNode],
  ) -> list[_DependencyReference]:
    references: set[tuple[str, str]] = set()
    config = template.config if isinstance(template.config, dict) else {}
    self._add_reference(references, "exact_code", config.get("child_template_code"))
    on_complete = config.get("on_complete")
    if isinstance(on_complete, dict):
      self._add_reference(references, "base_code", on_complete.get("next_template_code"))
    for node in nodes:
      node_config = node.config if isinstance(node.config, dict) else {}
      aggregate = node_config.get("aggregate_schema")
      if not isinstance(aggregate, dict):
        continue
      on_confirm = aggregate.get("on_confirm")
      if isinstance(on_confirm, dict):
        self._add_reference(references, "exact_code", on_confirm.get("child_template_code"))
    return [
      _DependencyReference(kind=kind, code=code)
      for kind, code in sorted(references)
    ]

  @staticmethod
  def _add_reference(
    references: set[tuple[str, str]],
    kind: Literal["exact_code", "base_code"],
    raw_code: object,
  ) -> None:
    if isinstance(raw_code, str) and raw_code.strip():
      references.add((kind, raw_code.strip()))

  @staticmethod
  def _scope_ids(template: WorkflowGraphTemplate) -> list[str]:
    return sorted(
      {
        str(value).strip()
        for value in (template.scope_department_ids or [])
        if str(value).strip()
      }
    )

  def _issue(
    self,
    *,
    template: WorkflowGraphTemplate,
    issue_code: str,
    severity: Literal["error", "warning", "review"],
    category: Literal["availability_scope", "template_dependency"],
    message: str,
    recommendation: str,
    referenced_template_code: str | None = None,
    suggested_template_code: str | None = None,
    affected_department_ids: list[str] | None = None,
  ) -> WorkflowGraphTemplateGovernanceIssueRead:
    return WorkflowGraphTemplateGovernanceIssueRead(
      issue_code=issue_code,
      severity=severity,
      category=category,
      template_id=template.id,
      template_code=template.code,
      template_name=template.name,
      template_status=template.status,
      message=message,
      recommendation=recommendation,
      repair_action=(
        "review_configuration" if severity == "review" else self._repair_action(template)
      ),
      referenced_template_code=referenced_template_code,
      suggested_template_code=suggested_template_code,
      affected_department_ids=affected_department_ids or [],
    )

  @staticmethod
  def _repair_action(
    template: WorkflowGraphTemplate,
  ) -> Literal["edit_draft", "create_new_version", "review_configuration"]:
    if template.status == WorkflowGraphTemplateStatus.DRAFT:
      return "edit_draft"
    if template.status == WorkflowGraphTemplateStatus.ACTIVE:
      return "create_new_version"
    return "review_configuration"

  def _scope_repair_recommendation(self, template: WorkflowGraphTemplate) -> str:
    if template.status == WorkflowGraphTemplateStatus.DRAFT:
      return "在设计器中重新选择可用部门后再发布。"
    if template.status == WorkflowGraphTemplateStatus.ACTIVE:
      return "新建模板版本，在草稿中修正可用范围后发布；不要原地缩小已发布范围。"
    return "从仍需使用的版本派生新草稿，并在发布前修正可用范围。"

  def _definition_repair_suffix(self, template: WorkflowGraphTemplate) -> str:
    if template.status == WorkflowGraphTemplateStatus.DRAFT:
      return "可直接在当前草稿中修改。"
    if template.status == WorkflowGraphTemplateStatus.ACTIVE:
      return "父模板已发布，请通过新版本修正引用。"
    return "如需恢复使用，请先派生新草稿。"
