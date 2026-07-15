from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import TaskSourceType
from app.core.exceptions import ConflictError, NotFoundError
from app.models import (
  Task,
  WorkflowGraphInstance,
  WorkflowHumanTaskLink,
  WorkflowNodeInstance,
)


logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class HumanTaskResolution:
  instance: WorkflowGraphInstance | None
  node_instance: WorkflowNodeInstance | None
  link: WorkflowHumanTaskLink | None
  source: str


@dataclass(slots=True, frozen=True)
class HumanTaskBackfillIssue:
  task_id: UUID
  code: str
  detail: str


@dataclass(slots=True)
class HumanTaskBackfillReport:
  scanned: int = 0
  eligible: int = 0
  created: int = 0
  existing: int = 0
  issues: list[HumanTaskBackfillIssue] = field(default_factory=list)


class HumanTaskCoordinator:
  """Application-layer boundary between Work Items and runtime node execution.

  I3-A limits this coordinator to durable relationship management. Runtime
  activation and capability-result commands move here in the next cutover.
  """

  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def ensure_link(
    self,
    *,
    task_id: UUID,
    node_instance_id: UUID,
    link_role: str = "primary",
    source: str = "runtime",
    link_metadata: dict[str, object] | None = None,
  ) -> WorkflowHumanTaskLink:
    task = await self._session.get(Task, task_id)
    if task is None:
      raise NotFoundError("HumanTask Link 对应的 Work Item 不存在。")
    node_instance = await self._session.get(WorkflowNodeInstance, node_instance_id)
    if node_instance is None:
      raise NotFoundError("HumanTask Link 对应的 NodeInstance 不存在。")

    existing = await self._session.scalar(
      select(WorkflowHumanTaskLink).where(WorkflowHumanTaskLink.task_id == task_id)
    )
    if existing is not None:
      if existing.node_instance_id != node_instance_id:
        raise ConflictError("同一个 Work Item 不能关联多个 NodeInstance。")
      return existing

    if link_role == "primary":
      active_primary = await self._session.scalar(
        select(WorkflowHumanTaskLink).where(
          WorkflowHumanTaskLink.node_instance_id == node_instance_id,
          WorkflowHumanTaskLink.link_role == "primary",
          WorkflowHumanTaskLink.lifecycle == "active",
        )
      )
      if active_primary is not None:
        raise ConflictError("当前 NodeInstance 已有关联的 active primary Work Item。")

    link = WorkflowHumanTaskLink(
      instance_id=node_instance.instance_id,
      node_instance_id=node_instance.id,
      task_id=task.id,
      link_role=link_role,
      lifecycle="active",
      source=source,
      link_metadata=dict(link_metadata or {}),
    )
    try:
      async with self._session.begin_nested():
        self._session.add(link)
        await self._session.flush()
    except IntegrityError:
      existing = await self._session.scalar(
        select(WorkflowHumanTaskLink).where(WorkflowHumanTaskLink.task_id == task_id)
      )
      if existing is not None:
        if existing.node_instance_id != node_instance_id:
          raise ConflictError("同一个 Work Item 不能关联多个 NodeInstance。")
        return existing
      if link_role == "primary":
        active_primary = await self._session.scalar(
          select(WorkflowHumanTaskLink).where(
            WorkflowHumanTaskLink.node_instance_id == node_instance_id,
            WorkflowHumanTaskLink.link_role == "primary",
            WorkflowHumanTaskLink.lifecycle == "active",
          )
        )
        if active_primary is not None:
          raise ConflictError("当前 NodeInstance 已有关联的 active primary Work Item。")
      raise
    return link

  async def resolve_for_task(
    self,
    *,
    task: Task,
    allow_json_fallback: bool = True,
  ) -> HumanTaskResolution:
    link = await self._session.scalar(
      select(WorkflowHumanTaskLink)
      .options(
        selectinload(WorkflowHumanTaskLink.instance),
        selectinload(WorkflowHumanTaskLink.node_instance),
      )
      .where(WorkflowHumanTaskLink.task_id == task.id)
    )
    if link is not None:
      return HumanTaskResolution(
        instance=link.instance,
        node_instance=link.node_instance,
        link=link,
        source="link",
      )

    if not allow_json_fallback:
      return HumanTaskResolution(None, None, None, "none")

    metadata = task.extra_metadata if isinstance(task.extra_metadata, dict) else {}
    try:
      instance_id = UUID(str(metadata["workflow_graph_instance_id"]))
      node_instance_id = UUID(str(metadata["workflow_node_instance_id"]))
    except (KeyError, TypeError, ValueError):
      return HumanTaskResolution(None, None, None, "none")

    node_instance = await self._session.get(WorkflowNodeInstance, node_instance_id)
    if node_instance is None or node_instance.instance_id != instance_id:
      return HumanTaskResolution(None, None, None, "none")
    instance = await self._session.get(WorkflowGraphInstance, instance_id)
    if instance is None:
      return HumanTaskResolution(None, None, None, "none")

    logger.warning(
      "workflow_human_task_link_fallback task_id=%s instance_id=%s node_instance_id=%s",
      task.id,
      instance.id,
      node_instance.id,
    )
    return HumanTaskResolution(instance, node_instance, None, "json_fallback")

  async def backfill_existing_links(self, *, dry_run: bool = True) -> HumanTaskBackfillReport:
    """Cross-check all legacy JSON anchors and optionally materialize safe links."""
    report = HumanTaskBackfillReport()
    tasks = list(await self._session.scalars(select(Task).order_by(Task.created_at.asc())))
    for task in tasks:
      metadata = task.extra_metadata if isinstance(task.extra_metadata, dict) else {}
      if not metadata.get("workflow_node_instance_id") and not metadata.get("workflow_graph_instance_id"):
        continue
      report.scanned += 1

      try:
        node_id = UUID(str(metadata["workflow_node_instance_id"]))
        instance_id = UUID(str(metadata["workflow_graph_instance_id"]))
      except (KeyError, TypeError, ValueError):
        report.issues.append(
          HumanTaskBackfillIssue(task.id, "invalid_json_anchor", "Task metadata 中的 Run/Node UUID 无效。")
        )
        continue

      node_instance = await self._session.get(WorkflowNodeInstance, node_id)
      if node_instance is None:
        report.issues.append(
          HumanTaskBackfillIssue(task.id, "node_missing", "Task metadata 指向的 NodeInstance 不存在。")
        )
        continue
      if node_instance.instance_id != instance_id:
        report.issues.append(
          HumanTaskBackfillIssue(task.id, "instance_mismatch", "Task metadata 的 Run 与 Node 所属 Run 不一致。")
        )
        continue

      node_config = node_instance.config if isinstance(node_instance.config, dict) else {}
      if str(node_config.get("task_id") or "") != str(task.id):
        report.issues.append(
          HumanTaskBackfillIssue(task.id, "node_task_mismatch", "Node config.task_id 未与 Task 互相指向。")
        )
        continue

      instance = await self._session.get(WorkflowGraphInstance, instance_id)
      if instance is None:
        report.issues.append(
          HumanTaskBackfillIssue(task.id, "instance_missing", "Task metadata 指向的 Run 不存在。")
        )
        continue
      if task.source_type == TaskSourceType.MANUAL and instance.source_id != task.id:
        report.issues.append(
          HumanTaskBackfillIssue(task.id, "source_mismatch", "手动图任务未与 Run source_id 互相指向。")
        )
        continue

      report.eligible += 1
      existing = await self._session.scalar(
        select(WorkflowHumanTaskLink).where(WorkflowHumanTaskLink.task_id == task.id)
      )
      if existing is not None:
        if existing.node_instance_id != node_instance.id:
          report.issues.append(
            HumanTaskBackfillIssue(task.id, "link_mismatch", "既有 Link 与 JSON 锚点指向不同 Node。")
          )
        else:
          report.existing += 1
        continue

      if not dry_run:
        await self.ensure_link(
          task_id=task.id,
          node_instance_id=node_instance.id,
          source="backfill",
          link_metadata={"backfilled_from": "legacy_json_anchors"},
        )
        report.created += 1

    return report
