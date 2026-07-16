"""Video workflow v1 form engine: capture submit, submissions, finalize (WF)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
  TaskStatus,
  UserRole,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models import (
  Task,
  User,
  WorkflowDeliverable,
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateNode,
  WorkflowNodeInstance,
)
from app.schemas.workflow_video import (
  ApprovedTopic,
  CaptureSchema,
  CloseCaptureResponse,
  RejectedCaptureItem,
  FinalizeTopicsResponse,
  DispatchTopicResponse,
  InstanceSubmissionsResponse,
  NodeSubmissionRead,
  TopicCaptureRow,
  TopicCaptureSubmitResponse,
  validate_capture_schema,
  validate_run_context,
)
from app.services.access_control import ensure_active_user
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.human_task_coordinator import HumanTaskCoordinator
from app.services.workflow_definition_snapshot import (
  SNAPSHOT_EXECUTOR_KIND,
  runtime_template,
)
from app.services.workflow_orchestration_service import WorkflowOrchestrationService
from app.services.workflow_video_fork_service import WorkflowVideoForkService
from app.services.workflow_run_event_service import WorkflowRunEventService
from app.services.workflow_video_rework_service import WorkflowVideoReworkService

DEFAULT_AGGREGATE_NODE_KEY = "N2_AGGREGATE"


class WorkflowVideoFormService:
  def __init__(
    self,
    session: AsyncSession,
    *,
    workflow_graph_service: WorkflowGraphService | None = None,
    orchestration_service: WorkflowOrchestrationService | None = None,
    rework_service: WorkflowVideoReworkService | None = None,
    fork_service: WorkflowVideoForkService | None = None,
  ) -> None:
    self._session = session
    self._human_task_coordinator = HumanTaskCoordinator(session)
    self._workflow_graph_service = workflow_graph_service or WorkflowGraphService(session)
    self._orchestration_service = orchestration_service
    if self._orchestration_service is None:
      self._orchestration_service = WorkflowOrchestrationService(
        session,
        workflow_graph_service=self._workflow_graph_service,
      )
    self._rework_service = rework_service
    if self._rework_service is None:
      self._rework_service = WorkflowVideoReworkService(
        session,
        workflow_graph_service=self._workflow_graph_service,
        orchestration_service=self._orchestration_service,
      )
    self._fork_service = fork_service
    if self._fork_service is None:
      self._fork_service = WorkflowVideoForkService(session)

  async def _load_task_projection(
    self,
    *,
    task_id: UUID,
  ) -> tuple[Task, WorkflowGraphInstance, WorkflowNodeInstance]:
    task = await self._session.scalar(
      select(Task)
      .options(selectinload(Task.assignee).selectinload(User.profile))
      .where(Task.id == task_id)
    )
    if task is None:
      raise NotFoundError("任务不存在。")

    metadata = dict(task.extra_metadata or {})
    instance_id = metadata.get("workflow_graph_instance_id")
    node_id = metadata.get("workflow_node_instance_id")
    if instance_id is None or node_id is None:
      raise ConflictError("当前任务未关联图引擎节点，无法提交采集表。")

    instance = await self._session.get(WorkflowGraphInstance, UUID(str(instance_id)))
    node_instance = await self._session.scalar(
      select(WorkflowNodeInstance)
      .options(selectinload(WorkflowNodeInstance.assignee).selectinload(User.profile))
      .options(selectinload(WorkflowNodeInstance.template_node))
      .where(WorkflowNodeInstance.id == UUID(str(node_id)))
    )
    if instance is None or node_instance is None:
      raise NotFoundError("图实例或节点不存在。")
    return task, instance, node_instance

  @staticmethod
  def _resolve_capture_schema(node_instance: WorkflowNodeInstance) -> CaptureSchema:
    config_sources: list[dict[str, Any]] = []
    if isinstance(node_instance.config, dict):
      config_sources.append(node_instance.config)
    template_node = node_instance.template_node
    if template_node is not None and isinstance(template_node.config, dict):
      config_sources.append(template_node.config)

    for config in config_sources:
      raw_schema = config.get("capture_schema")
      if isinstance(raw_schema, dict):
        return validate_capture_schema(raw_schema)

    raise ConflictError("当前节点未配置 capture_schema。")

  @staticmethod
  def _normalize_topics(
    *,
    schema: CaptureSchema,
    raw_topics: list[TopicCaptureRow],
  ) -> list[TopicCaptureRow]:
    if len(raw_topics) < schema.min_rows:
      raise ConflictError(f"至少需要提交 {schema.min_rows} 条记录。")
    if len(raw_topics) > schema.max_rows:
      raise ConflictError(f"最多允许提交 {schema.max_rows} 条记录。")

    required_keys = {column.key for column in schema.columns if column.required}
    normalized: list[TopicCaptureRow] = []
    for row in raw_topics:
      topic_id = row.topic_id or uuid4()
      payload = row.model_dump()
      payload["topic_id"] = topic_id
      for key in required_keys:
        value = payload.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
          raise ConflictError(f"字段 {key} 为必填项。")
      normalized.append(TopicCaptureRow.model_validate(payload))
    return normalized

  @staticmethod
  def _deliverable_signature(*, task_id: UUID, topics: list[TopicCaptureRow]) -> str:
    digest = hashlib.sha256(
      json.dumps(
        [topic.model_dump(mode="json") for topic in topics],
        sort_keys=True,
        ensure_ascii=False,
      ).encode("utf-8")
    ).hexdigest()
    return f"capture:{task_id}:{digest[:32]}"

  async def _upsert_capture_deliverable(
    self,
    *,
    node_instance: WorkflowNodeInstance,
    actor: User,
    topics: list[TopicCaptureRow],
    task_id: UUID,
  ) -> WorkflowDeliverable:
    now = datetime.now(UTC)
    payload_body = {
      "kind": "topic_capture",
      "topics": [topic.model_dump(mode="json") for topic in topics],
    }
    summary = f"提交 {len(topics)} 条采集记录"
    deliverable = await self._session.scalar(
      select(WorkflowDeliverable).where(WorkflowDeliverable.node_instance_id == node_instance.id)
    )
    if deliverable is None:
      deliverable = WorkflowDeliverable(
        node_instance_id=node_instance.id,
        submitted_by_user_id=actor.id,
        submitted_at=now,
        summary=summary,
        payload=payload_body,
        signature=self._deliverable_signature(task_id=task_id, topics=topics),
      )
      self._session.add(deliverable)
    else:
      deliverable.submitted_by_user_id = actor.id
      deliverable.submitted_at = now
      deliverable.summary = summary
      deliverable.payload = payload_body
      deliverable.signature = self._deliverable_signature(task_id=task_id, topics=topics)
    await self._session.flush()
    return deliverable

  @staticmethod
  def _merge_capture_into_context(
    *,
    instance: WorkflowGraphInstance,
    schema: CaptureSchema,
    topics: list[TopicCaptureRow],
  ) -> None:
    if schema.max_rows != 1 or len(topics) != 1:
      return
    row = topics[0].model_dump(mode="json")
    context = dict(instance.context or {})
    for column in schema.columns:
      raw_value = row.get(column.key)
      if raw_value is None or raw_value == "":
        continue
      context[column.key] = raw_value
    instance.context = validate_run_context(context).model_dump(mode="json")
    instance.context_version += 1

  async def _apply_capture_submitted(
    self,
    *,
    task: Task,
    node_instance: WorkflowNodeInstance,
  ) -> None:
    now = datetime.now(UTC)
    await self._human_task_coordinator.coordinate_mutations(
      task=task,
      node_instance=node_instance,
      task_changes={"status": TaskStatus.DONE, "completed_at": now, "updated_at": now},
      task_metadata_patch={
        "latest_capture_state": "submitted",
        "latest_capture_submitted_at": now.isoformat(),
      },
      node_changes={
        "engine_state": WorkflowNodeEngineState.COMPLETED,
        "business_state": WorkflowNodeBusinessState.DONE,
        "completed_at": now,
      },
    )

  async def submit_capture(
    self,
    *,
    actor: User,
    task_id: UUID,
    topics: list[TopicCaptureRow],
  ) -> TopicCaptureSubmitResponse:
    ensure_active_user(actor)
    task, instance, node_instance = await self._load_task_projection(task_id=task_id)
    if actor.role not in {UserRole.ADMIN, UserRole.HR} and actor.id != task.assignee_id:
      raise AuthorizationError("当前账号不能提交该采集表。")
    if node_instance.engine_state == WorkflowNodeEngineState.COMPLETED:
      raise ConflictError("该节点采集已提交。")

    context = instance.context if isinstance(instance.context, dict) else {}
    if context.get("capture_closed"):
      source_node_key = await self._resolve_capture_source_node_key(instance=instance)
      if node_instance.node_key == source_node_key:
        raise ConflictError("采集已结束，无法提交。")

    schema = self._resolve_capture_schema(node_instance)
    normalized_topics = self._normalize_topics(schema=schema, raw_topics=topics)
    if schema.max_rows == 1 and len(normalized_topics) != 1:
      raise ConflictError("当前采集节点每次只能提交 1 条记录。")
    await self._upsert_capture_deliverable(
      node_instance=node_instance,
      actor=actor,
      topics=normalized_topics,
      task_id=task_id,
    )
    self._merge_capture_into_context(
      instance=instance,
      schema=schema,
      topics=normalized_topics,
    )
    await self._apply_capture_submitted(task=task, node_instance=node_instance)
    await self._orchestration_service.after_capture_submitted(
      actor=actor,
      task=task,
      instance=instance,
      node_instance=node_instance,
    )
    await WorkflowRunEventService(self._session).append(
      instance_id=instance.id,
      event_type="capture_submitted",
      actor_user_id=actor.id,
      payload={
        "task_id": str(task.id),
        "node_instance_id": str(node_instance.id),
        "node_key": node_instance.node_key,
        "instance_key": node_instance.instance_key,
        "topic_count": len(normalized_topics),
      },
    )
    await self._session.commit()
    await self._session.refresh(task)
    await self._session.refresh(node_instance)
    await self._session.refresh(instance)

    return TopicCaptureSubmitResponse(
      task_id=task.id,
      node_instance_id=node_instance.id,
      topic_count=len(normalized_topics),
      topics=normalized_topics,
    )

  async def list_instance_submissions(
    self,
    *,
    instance_id: UUID,
    node_key: str,
  ) -> InstanceSubmissionsResponse:
    node_instances = list(
      await self._session.scalars(
        select(WorkflowNodeInstance)
        .options(selectinload(WorkflowNodeInstance.assignee).selectinload(User.profile))
        .where(
          WorkflowNodeInstance.instance_id == instance_id,
          WorkflowNodeInstance.node_key == node_key,
        )
        .order_by(WorkflowNodeInstance.created_at.asc())
      )
    )
    if not node_instances:
      raise NotFoundError("未找到匹配的节点实例。")

    submissions: list[NodeSubmissionRead] = []
    for node_instance in node_instances:
      deliverable = await self._session.scalar(
        select(WorkflowDeliverable).where(WorkflowDeliverable.node_instance_id == node_instance.id)
      )
      topics: list[TopicCaptureRow] = []
      if deliverable is not None and isinstance(deliverable.payload, dict):
        raw_topics = deliverable.payload.get("topics")
        if isinstance(raw_topics, list):
          for item in raw_topics:
            if isinstance(item, dict):
              topics.append(TopicCaptureRow.model_validate(item))

      assignee = node_instance.assignee
      submissions.append(
        NodeSubmissionRead(
          node_instance_id=node_instance.id,
          node_key=node_instance.node_key,
          instance_key=node_instance.instance_key,
          assignee_user_id=node_instance.assignee_user_id,
          assignee_email=assignee.email if assignee is not None else None,
          assignee_display_name=(
            assignee.profile.real_name
            if assignee is not None and assignee.profile is not None
            else None
          ),
          submitted_at=deliverable.submitted_at if deliverable is not None else None,
          topics=topics,
        )
      )

    return InstanceSubmissionsResponse(
      instance_id=instance_id,
      node_key=node_key,
      submissions=submissions,
    )

  async def _ensure_finalize_actor(
    self,
    *,
    actor: User,
    instance: WorkflowGraphInstance,
  ) -> None:
    if actor.role in {UserRole.ADMIN, UserRole.HR}:
      return
    if actor.id == instance.initiator_user_id:
      return

    context = instance.context if isinstance(instance.context, dict) else {}
    manager_id = context.get("manager_user_id")
    if manager_id is not None and str(manager_id) == str(actor.id):
      return

    aggregate_nodes = list(
      await self._session.scalars(
        select(WorkflowNodeInstance)
        .where(
          WorkflowNodeInstance.instance_id == instance.id,
          WorkflowNodeInstance.node_key == DEFAULT_AGGREGATE_NODE_KEY,
        )
        .order_by(WorkflowNodeInstance.iteration.desc())
      )
    )
    aggregate_node = aggregate_nodes[0] if aggregate_nodes else None
    if aggregate_node is not None and aggregate_node.assignee_user_id == actor.id:
      return

    raise AuthorizationError("当前账号不能确认选题清单。")

  async def finalize_topics(
    self,
    *,
    actor: User,
    instance_id: UUID,
    approved_topics: list[ApprovedTopic],
    rejected_topics: list[RejectedCaptureItem] | list[dict[str, object]] | None = None,
  ) -> FinalizeTopicsResponse:
    ensure_active_user(actor)
    instance = await self._session.get(WorkflowGraphInstance, instance_id)
    if instance is None:
      raise NotFoundError("图实例不存在。")
    await self._ensure_finalize_actor(actor=actor, instance=instance)

    normalized_rejections: list[RejectedCaptureItem] = []
    for entry in rejected_topics or []:
      if isinstance(entry, RejectedCaptureItem):
        normalized_rejections.append(entry)
      elif isinstance(entry, dict):
        normalized_rejections.append(RejectedCaptureItem.model_validate(entry))

    if normalized_rejections:
      await self._rework_service.apply_capture_rejections(
        actor=actor,
        instance_id=instance_id,
        rejections=normalized_rejections,
      )

    if not approved_topics:
      await self._session.commit()
      await self._session.refresh(instance)
      return FinalizeTopicsResponse(
        instance_id=instance_id,
        approved_count=0,
        fork_status="pending",
        fork_deferred=True,
        message="已打回采集，待相关编辑补交。",
      )

    context_before_fork = dict(instance.context or {})
    forked_topics_map = context_before_fork.get("forked_topics")
    already_forked: set[str] = set()
    if isinstance(forked_topics_map, dict):
      already_forked = {str(key) for key in forked_topics_map}

    topics_to_fork = [
      topic for topic in approved_topics if str(topic.topic_id) not in already_forked
    ]
    skipped_forked = len(approved_topics) - len(topics_to_fork)

    context = dict(instance.context or {})
    context["approved_topics"] = [topic.model_dump(mode="json") for topic in approved_topics]
    context["rejected_topics"] = [item.model_dump(mode="json") for item in normalized_rejections]
    if not topics_to_fork:
      context["fork_status"] = str(context_before_fork.get("fork_status") or "completed")
    else:
      context["fork_status"] = "pending"
    instance.context = validate_run_context(context).model_dump(mode="json")
    instance.context_version += 1
    await self._session.flush()

    skip_note = f"，跳过 {skipped_forked} 条已派发" if skipped_forked else ""
    if not topics_to_fork:
      await self._session.commit()
      await self._session.refresh(instance)
      return FinalizeTopicsResponse(
        instance_id=instance_id,
        approved_count=len(approved_topics),
        fork_status=str(context_before_fork.get("fork_status") or "completed"),
        fork_deferred=False,
        child_instance_ids=[],
        message=f"所选 {len(approved_topics)} 条选题均已派发，无需重复 fork{skip_note}。",
      )

    template_config: dict[str, object] = {}
    if instance.executor_kind == SNAPSHOT_EXECUTOR_KIND:
      snapshot_template = runtime_template(instance.definition_snapshot)
      if snapshot_template is not None:
        template_config = snapshot_template.config
    elif instance.template_id is not None:
      template = await self._session.get(WorkflowGraphTemplate, instance.template_id)
      if template is not None and isinstance(template.config, dict):
        template_config = template.config
    aggregate_key = str(
      template_config.get("aggregate_node_key")
      or (instance.context or {}).get("aggregate_node_key")
      or DEFAULT_AGGREGATE_NODE_KEY
    )

    await self._orchestration_service.after_aggregate_confirmed(
      actor=actor,
      instance=instance,
      aggregate_node_key=aggregate_key,
    )
    await WorkflowRunEventService(self._session).append(
      instance_id=instance.id,
      event_type="aggregate_confirmed",
      actor_user_id=actor.id,
      payload={
        "approved_count": len(approved_topics),
        "rejected_count": len(normalized_rejections),
        "aggregate_node_key": aggregate_key,
      },
    )

    fork_result = await self._fork_service.fork_production_runs(
      actor=actor,
      batch_instance_id=instance_id,
      approved_topics=topics_to_fork,
    )

    return FinalizeTopicsResponse(
      instance_id=instance_id,
      approved_count=len(approved_topics),
      fork_status=fork_result.fork_status,
      fork_deferred=False,
      child_instance_ids=fork_result.child_instance_ids,
      message=(
        f"已派发 {fork_result.forked_count} 条制作子 Run"
        f"（跳过 {fork_result.skipped_count + skipped_forked} 条重复）{skip_note}。"
      ),
    )

  async def _resolve_capture_source_node_key(
    self,
    *,
    instance: WorkflowGraphInstance,
  ) -> str:
    if instance.executor_kind == SNAPSHOT_EXECUTOR_KIND:
      snapshot_template = runtime_template(instance.definition_snapshot)
      if snapshot_template is not None:
        configured = snapshot_template.config.get("capture_node_key")
        if isinstance(configured, str) and configured.strip():
          return configured.strip()
    elif instance.template_id is not None:
      template = await self._session.get(WorkflowGraphTemplate, instance.template_id)
      if template is not None and isinstance(template.config, dict):
        configured = template.config.get("capture_node_key")
        if isinstance(configured, str) and configured.strip():
          return configured.strip()
    context = instance.context if isinstance(instance.context, dict) else {}
    configured = context.get("capture_node_key")
    if isinstance(configured, str) and configured.strip():
      return configured.strip()
    return "N1_PROPOSE"

  async def close_capture(
    self,
    *,
    actor: User,
    instance_id: UUID,
  ) -> CloseCaptureResponse:
    ensure_active_user(actor)
    instance = await self._session.get(WorkflowGraphInstance, instance_id)
    if instance is None:
      raise NotFoundError("图实例不存在。")

    context = dict(instance.context or {})
    if context.get("run_kind") != "batch":
      raise ConflictError("仅批次 Run 支持结束采集。")
    if context.get("capture_closed"):
      raise ConflictError("采集已结束。")

    await self._ensure_finalize_actor(actor=actor, instance=instance)

    source_node_key = await self._resolve_capture_source_node_key(instance=instance)
    pending_nodes = list(
      await self._session.scalars(
        select(WorkflowNodeInstance).where(
          WorkflowNodeInstance.instance_id == instance_id,
          WorkflowNodeInstance.node_key == source_node_key,
          WorkflowNodeInstance.engine_state.in_(
            {
              WorkflowNodeEngineState.PENDING,
              WorkflowNodeEngineState.ACTIVATED,
              WorkflowNodeEngineState.ACKNOWLEDGED,
            }
          ),
        )
      )
    )

    now = datetime.now(UTC)
    for node in pending_nodes:
      await self._human_task_coordinator.coordinate_mutations(
        node_instance=node,
        node_changes={
          "engine_state": WorkflowNodeEngineState.TERMINATED,
          "business_state": WorkflowNodeBusinessState.CANCELLED,
          "terminated_at": now,
          "node_instance_version": node.node_instance_version + 1,
        },
      )

    # Sync Task projections for terminated capture nodes — mark as DONE
    # so users don't get stuck with "doing" tasks after capture is closed.
    for node in pending_nodes:
      config = node.config if isinstance(node.config, dict) else {}
      raw_task_id = config.get("task_id")
      if isinstance(raw_task_id, str) and raw_task_id.strip():
        try:
          task_id = UUID(raw_task_id.strip())
          pending_task = await self._session.get(Task, task_id)
          if pending_task is not None and pending_task.status != TaskStatus.DONE:
            await self._human_task_coordinator.coordinate_mutations(
              task=pending_task,
              task_changes={"status": TaskStatus.DONE, "completed_at": now},
              task_metadata_patch={
                "latest_capture_state": "closed_by_manager",
                "capture_closed_at": now.isoformat(),
              },
            )
        except ValueError:
          continue

    context["capture_closed"] = True
    context["capture_closed_at"] = now.isoformat()
    instance.context = validate_run_context(context).model_dump(mode="json")

    await WorkflowRunEventService(self._session).append(
      instance_id=instance.id,
      event_type="capture_closed",
      actor_user_id=actor.id,
      payload={
        "skipped_capture_count": len(pending_nodes),
        "source_node_key": source_node_key,
      },
    )
    await self._session.commit()
    await self._session.refresh(instance)

    return CloseCaptureResponse(
      instance_id=instance_id,
      capture_closed=True,
      capture_closed_at=now,
      skipped_capture_count=len(pending_nodes),
      message=f"采集已结束，关闭 {len(pending_nodes)} 个未提交入口。",
    )

  async def dispatch_topic(
    self,
    *,
    actor: User,
    instance_id: UUID,
    topic_id: UUID,
    title: str,
    script_writer_user_id: UUID,
    source_node_instance_id: UUID | None = None,
  ) -> DispatchTopicResponse:
    """Incrementally fork one production child Run without completing N2 aggregate."""
    ensure_active_user(actor)
    instance = await self._session.get(WorkflowGraphInstance, instance_id)
    if instance is None:
      raise NotFoundError("图实例不存在。")
    await self._ensure_finalize_actor(actor=actor, instance=instance)

    context = dict(instance.context or {})
    forked_topics = context.get("forked_topics")
    if isinstance(forked_topics, dict) and str(topic_id) in forked_topics:
      raise ConflictError("该选题已派发制作，不可重复。")

    source_node_key = await self._resolve_capture_source_node_key(instance=instance)
    submissions_response = await self.list_instance_submissions(
      instance_id=instance_id,
      node_key=source_node_key,
    )

    matched_submission: NodeSubmissionRead | None = None
    matched_topic: TopicCaptureRow | None = None
    for submission in submissions_response.submissions:
      if source_node_instance_id is not None and submission.node_instance_id != source_node_instance_id:
        continue
      if submission.submitted_at is None or not submission.topics:
        continue
      for topic_row in submission.topics:
        row_topic_id = topic_row.topic_id
        if row_topic_id is not None and row_topic_id == topic_id:
          matched_submission = submission
          matched_topic = topic_row
          break
      if matched_topic is not None:
        break

    if matched_submission is None or matched_topic is None:
      raise NotFoundError("未找到已提交的选题，无法派发。")

    approved = ApprovedTopic(
      topic_id=topic_id,
      title=title.strip() or matched_topic.title,
      content=matched_topic.content,
      reason=matched_topic.reason,
      source_submitter_id=matched_submission.assignee_user_id,
      source_node_instance_id=matched_submission.node_instance_id,
      script_author_id=script_writer_user_id,
    )

    fork_result = await self._fork_service.fork_production_runs(
      actor=actor,
      batch_instance_id=instance_id,
      approved_topics=[approved],
    )

    if fork_result.forked_count == 0:
      raise ConflictError("该选题已派发制作，不可重复。")

    child_instance_id = fork_result.child_instance_ids[-1]
    await WorkflowRunEventService(self._session).append(
      instance_id=instance_id,
      event_type="topic_dispatched",
      actor_user_id=actor.id,
      payload={
        "topic_id": str(topic_id),
        "child_instance_id": str(child_instance_id),
        "script_author_id": str(script_writer_user_id),
      },
    )

    return DispatchTopicResponse(
      instance_id=instance_id,
      child_instance_id=child_instance_id,
      fork_status=fork_result.fork_status,
      message="已指派并启动制作子 Run。",
    )
