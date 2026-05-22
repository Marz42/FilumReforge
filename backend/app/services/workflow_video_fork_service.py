"""Video workflow v1 per-topic production fork (WFK)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import WorkflowGraphTemplateStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.models import User, WorkflowGraphInstance, WorkflowGraphTemplate, WorkflowGraphTemplateNode
from app.schemas.workflow_video import (
  ApprovedTopic,
  ForkProductionRunsResponse,
  validate_run_context,
)
from app.services.access_control import ensure_active_user
from app.services.workflow_orchestration_service import WorkflowOrchestrationService
from app.services.workflow_video_instantiation_service import WorkflowVideoInstantiationService

DEFAULT_CHILD_TEMPLATE_CODE = "video_production_per_topic_v1"
PRODUCTION_START_NODE_KEY = "N3_SCRIPT_WRITE"


@dataclass(slots=True)
class ForkProductionRunsResult:
  batch_instance: WorkflowGraphInstance
  forked_count: int
  skipped_count: int
  child_instance_ids: list[UUID]
  fork_status: str


class WorkflowVideoForkService:
  def __init__(
    self,
    session: AsyncSession,
    *,
    instantiation_service: WorkflowVideoInstantiationService | None = None,
    orchestration_service: WorkflowOrchestrationService | None = None,
  ) -> None:
    self._session = session
    self._instantiation_service = instantiation_service or WorkflowVideoInstantiationService(session)
    self._orchestration_service = orchestration_service or WorkflowOrchestrationService(session)

  @staticmethod
  def _append_run_event(
    *,
    instance: WorkflowGraphInstance,
    event_type: str,
    actor_id: UUID,
    payload: dict[str, Any],
  ) -> None:
    context = dict(instance.context or {})
    events = context.get("run_events")
    if not isinstance(events, list):
      events = []
    events.append(
      {
        "event_type": event_type,
        "at": datetime.now(UTC).isoformat(),
        "actor_user_id": str(actor_id),
        **payload,
      }
    )
    context["run_events"] = events
    instance.context = validate_run_context(context).model_dump(mode="json")
    instance.context_version += 1

  async def _load_batch_instance(self, *, batch_instance_id: UUID) -> WorkflowGraphInstance:
    instance = await self._session.get(WorkflowGraphInstance, batch_instance_id)
    if instance is None:
      raise NotFoundError("批次图实例不存在。")
    context = instance.context if isinstance(instance.context, dict) else {}
    if str(context.get("run_kind") or "") not in {"", "batch"}:
      raise ConflictError("仅批次选题会 Run 可按题 fork 制作子 Run。")
    return instance

  async def _resolve_child_template_code(
    self,
    *,
    batch_instance: WorkflowGraphInstance,
    override_code: str | None,
  ) -> str:
    if override_code:
      return override_code.strip()

    if batch_instance.template_id is not None:
      template = await self._session.get(WorkflowGraphTemplate, batch_instance.template_id)
      if template is not None:
        config = template.config if isinstance(template.config, dict) else {}
        configured = config.get("child_template_code")
        if isinstance(configured, str) and configured.strip():
          return configured.strip()

        nodes = list(
          await self._session.scalars(
            select(WorkflowGraphTemplateNode).where(
              WorkflowGraphTemplateNode.template_id == template.id
            )
          )
        )
        for node in nodes:
          node_config = node.config if isinstance(node.config, dict) else {}
          aggregate = node_config.get("aggregate_schema")
          if isinstance(aggregate, dict):
            on_confirm = aggregate.get("on_confirm")
            if isinstance(on_confirm, dict):
              child_code = on_confirm.get("child_template_code")
              if isinstance(child_code, str) and child_code.strip():
                return child_code.strip()

    return DEFAULT_CHILD_TEMPLATE_CODE

  async def _load_child_template(self, *, template_code: str) -> WorkflowGraphTemplate:
    template = await self._session.scalar(
      select(WorkflowGraphTemplate).where(
        WorkflowGraphTemplate.code == template_code,
        WorkflowGraphTemplate.status == WorkflowGraphTemplateStatus.ACTIVE,
      )
    )
    if template is None:
      raise NotFoundError(f"制作图模板不存在或未发布：{template_code}")
    return template

  async def _find_existing_child(
    self,
    *,
    parent_instance_id: UUID,
    topic_id: UUID,
  ) -> WorkflowGraphInstance | None:
    children = list(
      await self._session.scalars(
        select(WorkflowGraphInstance).where(
          WorkflowGraphInstance.parent_instance_id == parent_instance_id
        )
      )
    )
    topic_key = str(topic_id)
    for child in children:
      context = child.context if isinstance(child.context, dict) else {}
      if str(context.get("topic_id")) == topic_key:
        return child
    return None

  async def fork_production_runs(
    self,
    *,
    actor: User,
    batch_instance_id: UUID,
    approved_topics: list[ApprovedTopic] | None = None,
    child_template_code: str | None = None,
  ) -> ForkProductionRunsResult:
    """Fork one production child Run per approved topic (idempotent by parent + topic_id)."""
    ensure_active_user(actor)
    batch_instance = await self._load_batch_instance(batch_instance_id=batch_instance_id)

    topics = list(approved_topics or [])
    if not topics:
      context = batch_instance.context if isinstance(batch_instance.context, dict) else {}
      raw_topics = context.get("approved_topics")
      if isinstance(raw_topics, list):
        for entry in raw_topics:
          if isinstance(entry, dict):
            topics.append(ApprovedTopic.model_validate(entry))

    if not topics:
      raise ConflictError("没有可 fork 的 approved_topics。")

    resolved_code = await self._resolve_child_template_code(
      batch_instance=batch_instance,
      override_code=child_template_code,
    )
    child_template = await self._load_child_template(template_code=resolved_code)

    batch_context = dict(batch_instance.context or {})
    batch_root_task_id = batch_context.get("root_task_id")
    parent_task_id = UUID(str(batch_root_task_id)) if batch_root_task_id else None

    forked_topics = batch_context.get("forked_topics")
    if not isinstance(forked_topics, dict):
      forked_topics = {}

    child_ids: list[UUID] = list(batch_context.get("forked_child_instance_ids") or [])
    forked_count = 0
    skipped_count = 0

    for topic in topics:
      existing = await self._find_existing_child(
        parent_instance_id=batch_instance.id,
        topic_id=topic.topic_id,
      )
      if existing is not None:
        skipped_count += 1
        forked_topics[str(topic.topic_id)] = str(existing.id)
        if existing.id not in child_ids:
          child_ids.append(existing.id)
        continue

      run_result = await self._instantiation_service.instantiate_production_child_run(
        actor=actor,
        template=child_template,
        parent_instance=batch_instance,
        topic=topic,
        parent_task_id=parent_task_id,
      )
      child_instance = run_result.instance
      forked_count += 1
      forked_topics[str(topic.topic_id)] = str(child_instance.id)
      child_ids.append(child_instance.id)

      self._append_run_event(
        instance=batch_instance,
        event_type="production_run_forked",
        actor_id=actor.id,
        payload={
          "topic_id": str(topic.topic_id),
          "child_instance_id": str(child_instance.id),
          "script_author_id": str(topic.script_author_id),
        },
      )

    total_expected = len(topics)
    if forked_count == 0 and skipped_count == total_expected:
      fork_status = "completed"
    elif skipped_count > 0 and forked_count > 0:
      fork_status = "partial"
    elif forked_count == total_expected:
      fork_status = "completed"
    else:
      fork_status = "partial"

    batch_context["forked_topics"] = forked_topics
    batch_context["forked_child_instance_ids"] = [str(child_id) for child_id in child_ids]
    batch_context["fork_status"] = fork_status
    batch_context.pop("fork_deferred", None)
    batch_instance.context = validate_run_context(batch_context).model_dump(mode="json")
    batch_instance.context_version += 1

    await self._session.commit()
    await self._session.refresh(batch_instance)

    return ForkProductionRunsResult(
      batch_instance=batch_instance,
      forked_count=forked_count,
      skipped_count=skipped_count,
      child_instance_ids=child_ids,
      fork_status=fork_status,
    )

  def to_response(self, result: ForkProductionRunsResult) -> ForkProductionRunsResponse:
    return ForkProductionRunsResponse(
      batch_instance_id=result.batch_instance.id,
      forked_count=result.forked_count,
      skipped_count=result.skipped_count,
      child_instance_ids=result.child_instance_ids,
      fork_status=result.fork_status,
    )
