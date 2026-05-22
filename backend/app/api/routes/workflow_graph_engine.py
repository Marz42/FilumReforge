from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import (
  get_current_user,
  get_organization_relation_service,
  get_participant_resolution_service,
  get_workflow_graph_service,
  get_workflow_video_form_service,
  get_workflow_video_instantiation_service,
  get_workflow_video_fork_service,
  get_workflow_video_rework_service,
)
from app.core.exceptions import NotFoundError
from app.core.enums import WorkflowNodeEngineState
from app.models import User, WorkflowGraphInstance, WorkflowNodeInstance
from app.schemas.workflow_video import (
  CreateGraphTemplateRunRequest,
  CreateGraphTemplateRunResponse,
  FinalizeTopicsRequest,
  FinalizeTopicsResponse,
  RejectCapturesRequest,
  RejectCapturesResponse,
  RejectProductionStepRequest,
  ForkProductionRunsResponse,
  RejectProductionStepResponse,
  InstanceSubmissionsResponse,
  ParticipantUserPreview,
  PreviewParticipantsRequest,
  PreviewParticipantsResponse,
  TopicCaptureSubmitRequest,
  TopicCaptureSubmitResponse,
)
from app.schemas.workflow_graph import (
  WorkflowNodeDeepRejectRequest,
  WorkflowGraphInstanceDetailRead,
  WorkflowGraphInstanceRead,
  WorkflowGraphTemplateSummaryRead,
  WorkflowNodeCompleteRequest,
  WorkflowNodeInstanceRead,
  WorkflowNodeTakeoverRequest,
  WorkflowSmartNoticeCandidatesRequest,
  WorkflowSmartNoticeCandidatesResponse,
)
from app.services.organization_relation_service import OrganizationRelationService
from app.services.participant_resolution_service import ParticipantResolutionService
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_video_fork_service import WorkflowVideoForkService
from app.services.workflow_video_form_service import WorkflowVideoFormService

router = APIRouter(prefix="/workflow-graph")

_WORKFLOW_GRAPH_INSTANCE_READ_COLUMNS: frozenset[str] = frozenset(
  name for name in WorkflowGraphInstanceRead.model_fields if name != "node_instances"
)


def _build_node_instance_read(ni: WorkflowNodeInstance) -> WorkflowNodeInstanceRead:
  return WorkflowNodeInstanceRead.model_validate(ni)


def _workflow_graph_instance_read(
  instance: WorkflowGraphInstance,
  node_instances: list[WorkflowNodeInstance],
) -> WorkflowGraphInstanceRead:
  """Build read model without touching ORM relationships (avoids async lazy loads)."""
  payload = {name: getattr(instance, name) for name in _WORKFLOW_GRAPH_INSTANCE_READ_COLUMNS}
  return WorkflowGraphInstanceRead(
    **payload,
    node_instances=[_build_node_instance_read(ni) for ni in node_instances],
  )


def _build_instance_detail(
  instance: WorkflowGraphInstance,
  node_instances: list[WorkflowNodeInstance],
) -> WorkflowGraphInstanceDetailRead:
  total = len(node_instances)
  completed = sum(1 for ni in node_instances if ni.engine_state == WorkflowNodeEngineState.COMPLETED)
  active = sum(1 for ni in node_instances if ni.engine_state == WorkflowNodeEngineState.ACTIVATED)
  pending = sum(1 for ni in node_instances if ni.engine_state == WorkflowNodeEngineState.PENDING)
  progress = int((completed / total) * 100) if total else 0

  base = _workflow_graph_instance_read(instance, node_instances)
  return WorkflowGraphInstanceDetailRead(
    **base.model_dump(),
    total_node_count=total,
    completed_node_count=completed,
    active_node_count=active,
    pending_node_count=pending,
    progress_percent=progress,
  )


def _user_display_name(user: User) -> str | None:
  profile = user.profile
  if profile is not None and profile.real_name:
    return profile.real_name
  return None


@router.get(
  "/templates",
  response_model=list[WorkflowGraphTemplateSummaryRead],
  tags=["workflow-graph"],
)
async def list_graph_templates(
  actor: Annotated[User, Depends(get_current_user)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
) -> list[WorkflowGraphTemplateSummaryRead]:
  _ = actor
  templates = await workflow_graph_service.list_active_templates()
  return [
    WorkflowGraphTemplateSummaryRead(
      id=template.id,
      code=template.code,
      name=template.name,
      description=template.description,
      status=template.status,
      version=template.version,
      run_kind=str((template.config or {}).get("run_kind") or "") or None,
      config=dict(template.config or {}),
    )
    for template in templates
  ]


@router.post(
  "/templates/{template_id}/runs",
  response_model=CreateGraphTemplateRunResponse,
  tags=["workflow-graph"],
)
async def create_graph_template_run(
  template_id: UUID,
  payload: CreateGraphTemplateRunRequest,
  actor: Annotated[User, Depends(get_current_user)],
  instantiation_service: WorkflowVideoInstantiationService = Depends(
    get_workflow_video_instantiation_service
  ),
) -> CreateGraphTemplateRunResponse:
  result = await instantiation_service.instantiate_graph_template(
    actor=actor,
    template_id=template_id,
    inputs=payload.inputs,
    participants_snapshot=payload.participants_snapshot,
    department_id=payload.department_id,
    run_label=payload.run_label,
  )
  return instantiation_service.to_response(result)


@router.post(
  "/templates/{template_id}/preview-participants",
  response_model=PreviewParticipantsResponse,
  tags=["workflow-graph"],
)
async def preview_template_participants(
  template_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  participant_service: Annotated[ParticipantResolutionService, Depends(get_participant_resolution_service)],
  policy: Annotated[str, Query(min_length=1, max_length=64)],
  payload: PreviewParticipantsRequest | None = None,
) -> PreviewParticipantsResponse:
  template = await participant_service.get_template_or_raise(template_id)

  body = payload or PreviewParticipantsRequest()
  snapshot, users = await participant_service.preview_for_template(
    actor=actor,
    template=template,
    policy_ref=policy,
    department_id=body.department_id,
    mode=body.mode,
    selected_user_ids=body.user_ids or None,
  )
  return PreviewParticipantsResponse(
    policy_ref=policy,
    mode=snapshot.mode,
    user_ids=snapshot.user_ids,
    users=[
      ParticipantUserPreview(
        id=user.id,
        email=user.email,
        display_name=_user_display_name(user),
      )
      for user in users
    ],
    snapshot=snapshot,
  )


@router.get(
  "/templates/{template_id}/instances",
  response_model=list[WorkflowGraphInstanceRead],
  tags=["workflow-graph"],
)
async def list_graph_instances_for_template(
  template_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
  limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[WorkflowGraphInstanceRead]:
  instances = await workflow_graph_service.list_instances_for_template(
    template_id=template_id,
    limit=limit,
  )
  results: list[WorkflowGraphInstanceRead] = []
  for instance in instances:
    node_instances = await workflow_graph_service.list_node_instances_for_graph(
      instance_id=instance.id,
    )
    results.append(_workflow_graph_instance_read(instance, node_instances))
  return results


@router.post(
  "/tasks/{task_id}/submit-capture",
  response_model=TopicCaptureSubmitResponse,
  tags=["workflow-graph"],
)
async def submit_task_capture(
  task_id: UUID,
  payload: TopicCaptureSubmitRequest,
  actor: Annotated[User, Depends(get_current_user)],
  form_service: Annotated[WorkflowVideoFormService, Depends(get_workflow_video_form_service)],
) -> TopicCaptureSubmitResponse:
  return await form_service.submit_capture(
    actor=actor,
    task_id=task_id,
    topics=payload.topics,
  )


@router.get(
  "/instances/{instance_id}/submissions",
  response_model=InstanceSubmissionsResponse,
  tags=["workflow-graph"],
)
async def list_instance_submissions(
  instance_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  form_service: Annotated[WorkflowVideoFormService, Depends(get_workflow_video_form_service)],
  node_key: Annotated[str, Query(min_length=1, max_length=64)],
) -> InstanceSubmissionsResponse:
  _ = actor
  return await form_service.list_instance_submissions(
    instance_id=instance_id,
    node_key=node_key,
  )


@router.post(
  "/instances/{instance_id}/fork-production",
  response_model=ForkProductionRunsResponse,
  tags=["workflow-graph"],
)
async def fork_production_runs(
  instance_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  fork_service: WorkflowVideoForkService = Depends(get_workflow_video_fork_service),
) -> ForkProductionRunsResponse:
  result = await fork_service.fork_production_runs(
    actor=actor,
    batch_instance_id=instance_id,
  )
  return fork_service.to_response(result)


@router.post(
  "/instances/{instance_id}/reject-captures",
  response_model=RejectCapturesResponse,
  tags=["workflow-graph"],
)
async def reject_instance_captures(
  instance_id: UUID,
  payload: RejectCapturesRequest,
  actor: Annotated[User, Depends(get_current_user)],
  rework_service: WorkflowVideoReworkService = Depends(get_workflow_video_rework_service),
) -> RejectCapturesResponse:
  return await rework_service.apply_capture_rejections(
    actor=actor,
    instance_id=instance_id,
    rejections=payload.rejections,
    source_node_key=payload.source_node_key,
  )


@router.post(
  "/tasks/{task_id}/reject-production",
  response_model=RejectProductionStepResponse,
  tags=["workflow-graph"],
)
async def reject_production_task_step(
  task_id: UUID,
  payload: RejectProductionStepRequest,
  actor: Annotated[User, Depends(get_current_user)],
  rework_service: WorkflowVideoReworkService = Depends(get_workflow_video_rework_service),
) -> RejectProductionStepResponse:
  return await rework_service.reject_production_step(
    actor=actor,
    task_id=task_id,
    reason=payload.reason,
    target_node_key=payload.target_node_key,
  )


@router.post(
  "/instances/{instance_id}/finalize-topics",
  response_model=FinalizeTopicsResponse,
  tags=["workflow-graph"],
)
async def finalize_instance_topics(
  instance_id: UUID,
  payload: FinalizeTopicsRequest,
  actor: Annotated[User, Depends(get_current_user)],
  form_service: Annotated[WorkflowVideoFormService, Depends(get_workflow_video_form_service)],
) -> FinalizeTopicsResponse:
  return await form_service.finalize_topics(
    actor=actor,
    instance_id=instance_id,
    approved_topics=payload.approved_topics,
    rejected_topics=payload.rejected_topics,
  )


@router.get(
  "/instances/{instance_id}/children",
  response_model=list[WorkflowGraphInstanceRead],
  tags=["workflow-graph"],
)
async def list_graph_instance_children(
  instance_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
  limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[WorkflowGraphInstanceRead]:
  _ = actor
  children = await workflow_graph_service.list_child_instances(
    parent_instance_id=instance_id,
    limit=limit,
  )
  results: list[WorkflowGraphInstanceRead] = []
  for child in children:
    node_instances = await workflow_graph_service.list_node_instances_for_graph(instance_id=child.id)
    results.append(_workflow_graph_instance_read(child, node_instances))
  return results


@router.get(
  "/instances/{instance_id}",
  response_model=WorkflowGraphInstanceDetailRead,
  tags=["workflow-graph"],
)
async def get_graph_instance(
  instance_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
) -> WorkflowGraphInstanceDetailRead:
  instance = await workflow_graph_service.get_instance(instance_id=instance_id)
  node_instances = await workflow_graph_service.list_node_instances_for_graph(instance_id=instance_id)
  return _build_instance_detail(instance, node_instances)


@router.post(
  "/node-instances/{node_instance_id}/complete",
  response_model=WorkflowGraphInstanceDetailRead,
  tags=["workflow-graph"],
)
async def complete_node_instance(
  node_instance_id: UUID,
  payload: WorkflowNodeCompleteRequest,
  actor: Annotated[User, Depends(get_current_user)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
) -> WorkflowGraphInstanceDetailRead:
  await workflow_graph_service.complete_node_instance(
    node_instance_id=node_instance_id,
    actor_id=actor.id,
    context_updates=payload.context_updates,
  )
  # 重新查询实例以返回最新快照
  node_instance: WorkflowNodeInstance | None = await workflow_graph_service._session.get(
    WorkflowNodeInstance, node_instance_id
  )
  if node_instance is None:
    from app.core.exceptions import NotFoundError
    raise NotFoundError("节点实例不存在。")
  instance = await workflow_graph_service.get_instance(instance_id=node_instance.instance_id)
  node_instances = await workflow_graph_service.list_node_instances_for_graph(
    instance_id=node_instance.instance_id
  )
  return _build_instance_detail(instance, node_instances)


@router.post(
  "/node-instances/{node_instance_id}/deep-reject",
  response_model=WorkflowGraphInstanceDetailRead,
  tags=["workflow-graph"],
)
async def deep_reject_node_instance(
  node_instance_id: UUID,
  payload: WorkflowNodeDeepRejectRequest,
  actor: Annotated[User, Depends(get_current_user)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
) -> WorkflowGraphInstanceDetailRead:
  instance_id = await workflow_graph_service.deep_reject_to_upstream(
    node_instance_id=node_instance_id,
    actor_id=actor.id,
    target_node_key=payload.target_node_key,
    reason=payload.reason,
  )
  instance = await workflow_graph_service.get_instance(instance_id=instance_id)
  node_instances = await workflow_graph_service.list_node_instances_for_graph(
    instance_id=instance_id,
  )
  return _build_instance_detail(instance, node_instances)


@router.post(
  "/node-instances/{node_instance_id}/takeover",
  response_model=WorkflowGraphInstanceDetailRead,
  tags=["workflow-graph"],
)
async def takeover_node_instance(
  node_instance_id: UUID,
  payload: WorkflowNodeTakeoverRequest,
  actor: Annotated[User, Depends(get_current_user)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
) -> WorkflowGraphInstanceDetailRead:
  instance_id = await workflow_graph_service.takeover_node_instance(
    node_instance_id=node_instance_id,
    actor_id=actor.id,
    actor_role=actor.role,
    assignee_id=payload.assignee_user_id,
    reason=payload.reason,
  )
  instance = await workflow_graph_service.get_instance(instance_id=instance_id)
  node_instances = await workflow_graph_service.list_node_instances_for_graph(
    instance_id=instance_id,
  )
  return _build_instance_detail(instance, node_instances)


@router.post(
  "/smart-notice-candidates",
  response_model=WorkflowSmartNoticeCandidatesResponse,
  tags=["workflow-graph"],
)
async def compute_smart_notice_candidates(
  payload: WorkflowSmartNoticeCandidatesRequest,
  actor: Annotated[User, Depends(get_current_user)],
  organization_relation_service: Annotated[
    OrganizationRelationService,
    Depends(get_organization_relation_service),
  ],
) -> WorkflowSmartNoticeCandidatesResponse:
  candidate_user_ids, reached_initiator = await organization_relation_service.suggest_notice_recipients(
    initiator_user_id=payload.initiator_user_id,
    target_user_id=payload.target_user_id,
    include_user_ids=payload.include_user_ids,
    exclude_user_ids=payload.exclude_user_ids,
  )
  return WorkflowSmartNoticeCandidatesResponse(
    candidate_user_ids=candidate_user_ids,
    reached_initiator=reached_initiator,
  )
