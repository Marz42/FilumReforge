from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Response

from app.api.dependencies import (
  get_current_user,
  get_db_session,
  get_organization_relation_service,
  get_participant_resolution_service,
  get_workflow_graph_service,
  get_workflow_video_form_service,
  get_workflow_video_instantiation_service,
  get_workflow_video_fork_service,
  get_workflow_video_rework_service,
  get_workflow_graph_template_admin_service,
  get_workflow_graph_template_schedule_service,
  get_workflow_run_event_service,
  get_settings,
)
from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.enums import WorkflowNodeEngineState
from app.models import User, WorkflowGraphInstance, WorkflowGraphTemplateNode, WorkflowNodeInstance
from app.services.access_control import ensure_department_stats_access, can_manage_task_templates, get_effective_managed_department_ids
from app.services.workflow_access_policy import WorkflowAccessPolicy
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.workflow_video import (
  CloseCaptureResponse,
  CreateGraphTemplateRunRequest,
  CreateGraphTemplateRunResponse,
  FinalizeTopicsRequest,
  FinalizeTopicsResponse,
  DispatchTopicRequest,
  DispatchTopicResponse,
  DepartmentRunSummaryRead,
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
  WorkflowRunEventListResponse,
)
from app.schemas.workflow_graph import (
  WorkflowNodeDeepRejectRequest,
  WorkflowGraphInstanceDetailRead,
  WorkflowGraphInstanceRead,
  WorkflowGraphTemplateCreateRequest,
  WorkflowGraphTemplateDeleteResponse,
  WorkflowGraphTemplateDesignerRead,
  WorkflowGraphTemplateDetailRead,
  WorkflowGraphTemplateDraftSaveRequest,
  WorkflowGraphTemplateDryRunRequest,
  WorkflowGraphTemplateDryRunResponse,
  WorkflowGraphTemplateExportBundle,
  WorkflowGraphTemplateImportRequest,
  WorkflowGraphTemplateStatusUpdateRequest,
  WorkflowGraphTemplateStatsRead,
  WorkflowGraphTemplateSummaryRead,
  WorkflowGraphTemplateUpdateRequest,
  WorkflowGraphTemplateValidateResponse,
  WorkflowNodeCompleteRequest,
  WorkflowNodeInstanceRead,
  WorkflowNodeTakeoverRequest,
  WorkflowSmartNoticeCandidatesRequest,
  WorkflowSmartNoticeCandidatesResponse,
)
from app.schemas.workflow_graph_schedule import (
  GraphTemplateScheduleCreateRequest,
  GraphTemplateScheduleRead,
  GraphTemplateScheduleRunNowResponse,
  GraphTemplateScheduleUpdateRequest,
)
from app.services.organization_relation_service import OrganizationRelationService
from app.services.participant_resolution_service import ParticipantResolutionService
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_graph_template_admin_service import WorkflowGraphTemplateAdminService
from app.services.workflow_graph_template_schedule_service import (
  WorkflowGraphTemplateScheduleService,
  template_is_schedulable,
)
from app.services.workflow_run_event_service import WorkflowRunEventService
from app.services.workflow_command_executor import WorkflowCommandExecutor
from app.services.workflow_video_fork_service import WorkflowVideoForkService
from app.services.workflow_video_form_service import WorkflowVideoFormService

router = APIRouter(prefix="/workflow-graph")


def _resolve_command_id(raw_command_id: str | None, response: Response) -> str:
  command_id = (raw_command_id or "").strip() or str(uuid4())
  response.headers["X-Command-ID"] = command_id
  return command_id

_WORKFLOW_GRAPH_INSTANCE_READ_COLUMNS: frozenset[str] = frozenset(
  name for name in WorkflowGraphInstanceRead.model_fields if name != "node_instances"
)


def _build_node_instance_read(ni: WorkflowNodeInstance) -> WorkflowNodeInstanceRead:
  config = ni.config if isinstance(ni.config, dict) else {}
  task_id_raw = config.get("task_id")
  task_id: UUID | None = None
  if isinstance(task_id_raw, str) and task_id_raw.strip():
    try:
      task_id = UUID(task_id_raw.strip())
    except ValueError:
      task_id = None
  return WorkflowNodeInstanceRead.model_validate(ni).model_copy(update={"task_id": task_id})


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
  completed = sum(
    1
    for ni in node_instances
    if ni.engine_state
    in {
      WorkflowNodeEngineState.COMPLETED,
      WorkflowNodeEngineState.SKIPPED,
      WorkflowNodeEngineState.TERMINATED,
    }
  )
  active = sum(
    1
    for ni in node_instances
    if ni.engine_state
    in {WorkflowNodeEngineState.ACTIVATED, WorkflowNodeEngineState.ACKNOWLEDGED}
  )
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
  "/feature-flags",
  tags=["workflow-graph"],
)
async def get_workflow_feature_flags(
  actor: Annotated[User, Depends(get_current_user)],
  settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, bool]:
  _ = actor
  from app.core.workflow_video_policy import workflow_feature_flags

  return workflow_feature_flags(settings)


@router.get(
  "/managed-department-member-options",
  response_model=list[ParticipantUserPreview],
  tags=["workflow-graph"],
)
async def list_managed_department_member_options(
  actor: Annotated[User, Depends(get_current_user)],
  participant_service: Annotated[ParticipantResolutionService, Depends(get_participant_resolution_service)],
) -> list[ParticipantUserPreview]:
  users = await participant_service.list_managed_department_member_options(actor=actor)
  return [
    ParticipantUserPreview(
      id=user.id,
      email=user.email,
      display_name=_user_display_name(user),
    )
    for user in users
  ]


@router.get(
  "/templates/{template_id}/department-pool-member-options",
  response_model=list[ParticipantUserPreview],
  tags=["workflow-graph"],
)
async def list_department_pool_member_options(
  template_id: UUID,
  pool_key: Annotated[str, Query(min_length=1, max_length=64)],
  actor: Annotated[User, Depends(get_current_user)],
  participant_service: Annotated[ParticipantResolutionService, Depends(get_participant_resolution_service)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
  instance_id: Annotated[UUID | None, Query()] = None,
) -> list[ParticipantUserPreview]:
  template = await participant_service.get_template_or_raise(template_id)
  instance: WorkflowGraphInstance | None = None
  if instance_id is not None:
    instance = await workflow_graph_service.get_instance(instance_id=instance_id)
  users = await participant_service.list_department_pool_member_options(
    actor=actor,
    template=template,
    pool_key=pool_key,
    instance=instance,
  )
  return [
    ParticipantUserPreview(
      id=user.id,
      email=user.email,
      display_name=_user_display_name(user),
    )
    for user in users
  ]


@router.get(
  "/templates",
  response_model=list[WorkflowGraphTemplateSummaryRead],
  tags=["workflow-graph"],
)
async def list_graph_templates(
  actor: Annotated[User, Depends(get_current_user)],
  session: Annotated[AsyncSession, Depends(get_db_session)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
  admin_service: Annotated[WorkflowGraphTemplateAdminService, Depends(get_workflow_graph_template_admin_service)],
  scope: Annotated[str | None, Query()] = None,
  schedulable: Annotated[bool | None, Query()] = None,
) -> list[WorkflowGraphTemplateSummaryRead]:
  if scope == "manage" and await can_manage_task_templates(session, actor):
    templates = await admin_service.list_manageable_templates()
    stats_map = await admin_service.load_template_stats_map(template_ids=[template.id for template in templates])
  else:
    templates = await workflow_graph_service.list_active_templates()
    managed_department_ids = await get_effective_managed_department_ids(session, actor.id)
    if managed_department_ids:
      managed_set = {str(did) for did in managed_department_ids}
      templates = [
        template
        for template in templates
        if not template.scope_department_ids
        or any(
          str(did) in managed_set
          for did in (template.scope_department_ids or [])
        )
      ]
    stats_map = {}

  if schedulable:
    filtered = []
    for template in templates:
      nodes = list(
        await session.scalars(
          select(WorkflowGraphTemplateNode).where(WorkflowGraphTemplateNode.template_id == template.id)
        )
      )
      if template_is_schedulable(template=template, nodes=nodes):
        filtered.append(template)
    templates = filtered

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
      scope_mode=template.scope_mode,
      scope_department_ids=[str(did) for did in (template.scope_department_ids or [])],
      run_count_total=stats_map[template.id].run_count_total if template.id in stats_map else None,
      run_count_30d=stats_map[template.id].run_count_30d if template.id in stats_map else None,
      active_run_count=stats_map[template.id].active_run_count if template.id in stats_map else None,
    )
    for template in templates
  ]


@router.post(
  "/templates",
  response_model=WorkflowGraphTemplateDesignerRead,
  tags=["workflow-graph"],
)
async def create_graph_template(
  payload: WorkflowGraphTemplateCreateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  admin_service: Annotated[WorkflowGraphTemplateAdminService, Depends(get_workflow_graph_template_admin_service)],
) -> WorkflowGraphTemplateDesignerRead:
  return await admin_service.create_template(actor=actor, payload=payload)


@router.get(
  "/templates/{template_id}/designer",
  response_model=WorkflowGraphTemplateDesignerRead,
  tags=["workflow-graph"],
)
async def get_graph_template_designer(
  template_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  session: Annotated[AsyncSession, Depends(get_db_session)],
  admin_service: Annotated[WorkflowGraphTemplateAdminService, Depends(get_workflow_graph_template_admin_service)],
) -> WorkflowGraphTemplateDesignerRead:
  await WorkflowAccessPolicy(session).ensure_can_manage_templates(
    actor=actor,
    template_id=template_id,
  )
  return await admin_service.get_designer_detail(template_id=template_id)


@router.put(
  "/templates/{template_id}/draft",
  response_model=WorkflowGraphTemplateDesignerRead,
  tags=["workflow-graph"],
)
async def save_graph_template_draft(
  template_id: UUID,
  payload: WorkflowGraphTemplateDraftSaveRequest,
  actor: Annotated[User, Depends(get_current_user)],
  admin_service: Annotated[WorkflowGraphTemplateAdminService, Depends(get_workflow_graph_template_admin_service)],
) -> WorkflowGraphTemplateDesignerRead:
  return await admin_service.save_draft(actor=actor, template_id=template_id, payload=payload)


@router.post(
  "/templates/{template_id}/versions",
  response_model=WorkflowGraphTemplateDesignerRead,
  tags=["workflow-graph"],
)
async def fork_graph_template_version(
  template_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  admin_service: Annotated[WorkflowGraphTemplateAdminService, Depends(get_workflow_graph_template_admin_service)],
) -> WorkflowGraphTemplateDesignerRead:
  return await admin_service.fork_template_version(actor=actor, template_id=template_id)


@router.patch(
  "/templates/{template_id}/status",
  response_model=WorkflowGraphTemplateDesignerRead,
  tags=["workflow-graph"],
)
async def update_graph_template_status(
  template_id: UUID,
  payload: WorkflowGraphTemplateStatusUpdateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  admin_service: Annotated[WorkflowGraphTemplateAdminService, Depends(get_workflow_graph_template_admin_service)],
) -> WorkflowGraphTemplateDesignerRead:
  return await admin_service.update_status(actor=actor, template_id=template_id, payload=payload)


@router.get(
  "/templates/{template_id}/validate",
  response_model=WorkflowGraphTemplateValidateResponse,
  tags=["workflow-graph"],
)
async def validate_graph_template(
  template_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  admin_service: Annotated[WorkflowGraphTemplateAdminService, Depends(get_workflow_graph_template_admin_service)],
) -> WorkflowGraphTemplateValidateResponse:
  _ = actor
  return await admin_service.validate_template(template_id=template_id)


@router.get(
  "/templates/{template_id}/export",
  response_model=WorkflowGraphTemplateExportBundle,
  tags=["workflow-graph"],
)
async def export_graph_template(
  template_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  admin_service: Annotated[WorkflowGraphTemplateAdminService, Depends(get_workflow_graph_template_admin_service)],
) -> WorkflowGraphTemplateExportBundle:
  return await admin_service.export_template(actor=actor, template_id=template_id)


@router.post(
  "/templates/import",
  response_model=WorkflowGraphTemplateDesignerRead,
  tags=["workflow-graph"],
)
async def import_graph_template_new(
  payload: WorkflowGraphTemplateImportRequest,
  actor: Annotated[User, Depends(get_current_user)],
  admin_service: Annotated[WorkflowGraphTemplateAdminService, Depends(get_workflow_graph_template_admin_service)],
  name: Annotated[str | None, Query(max_length=120)] = None,
) -> WorkflowGraphTemplateDesignerRead:
  return await admin_service.import_template_new(actor=actor, payload=payload, name=name)


@router.post(
  "/templates/{template_id}/import",
  response_model=WorkflowGraphTemplateDesignerRead,
  tags=["workflow-graph"],
)
async def import_graph_template_draft(
  template_id: UUID,
  payload: WorkflowGraphTemplateImportRequest,
  actor: Annotated[User, Depends(get_current_user)],
  admin_service: Annotated[WorkflowGraphTemplateAdminService, Depends(get_workflow_graph_template_admin_service)],
) -> WorkflowGraphTemplateDesignerRead:
  return await admin_service.import_template_draft(actor=actor, template_id=template_id, payload=payload)


@router.post(
  "/templates/{template_id}/dry-run",
  response_model=WorkflowGraphTemplateDryRunResponse,
  tags=["workflow-graph"],
)
async def dry_run_graph_template(
  template_id: UUID,
  payload: WorkflowGraphTemplateDryRunRequest,
  actor: Annotated[User, Depends(get_current_user)],
  admin_service: Annotated[WorkflowGraphTemplateAdminService, Depends(get_workflow_graph_template_admin_service)],
) -> WorkflowGraphTemplateDryRunResponse:
  return await admin_service.dry_run_template(actor=actor, template_id=template_id, payload=payload)


@router.get(
  "/templates/{template_id}/stats",
  response_model=WorkflowGraphTemplateStatsRead,
  tags=["workflow-graph"],
)
async def get_graph_template_stats(
  template_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  session: Annotated[AsyncSession, Depends(get_db_session)],
  admin_service: Annotated[WorkflowGraphTemplateAdminService, Depends(get_workflow_graph_template_admin_service)],
) -> WorkflowGraphTemplateStatsRead:
  await WorkflowAccessPolicy(session).ensure_can_manage_templates(
    actor=actor,
    template_id=template_id,
  )
  return await admin_service.get_template_stats(template_id=template_id)


@router.get(
  "/templates/{template_id}",
  response_model=WorkflowGraphTemplateDetailRead,
  tags=["workflow-graph"],
)
async def get_graph_template(
  template_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  admin_service: Annotated[WorkflowGraphTemplateAdminService, Depends(get_workflow_graph_template_admin_service)],
) -> WorkflowGraphTemplateDetailRead:
  _ = actor
  return await admin_service.get_template_detail(template_id=template_id)


@router.patch(
  "/templates/{template_id}",
  response_model=WorkflowGraphTemplateDetailRead,
  tags=["workflow-graph"],
)
async def update_graph_template(
  template_id: UUID,
  payload: WorkflowGraphTemplateUpdateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  admin_service: Annotated[WorkflowGraphTemplateAdminService, Depends(get_workflow_graph_template_admin_service)],
) -> WorkflowGraphTemplateDetailRead:
  return await admin_service.update_template(actor=actor, template_id=template_id, payload=payload)


@router.delete(
  "/templates/{template_id}",
  response_model=WorkflowGraphTemplateDeleteResponse,
  tags=["workflow-graph"],
)
async def delete_graph_template(
  template_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  admin_service: Annotated[WorkflowGraphTemplateAdminService, Depends(get_workflow_graph_template_admin_service)],
) -> WorkflowGraphTemplateDeleteResponse:
  await admin_service.delete_template(actor=actor, template_id=template_id)
  return WorkflowGraphTemplateDeleteResponse(deleted=True, template_id=str(template_id))


@router.post(
  "/templates/{template_id}/runs",
  response_model=CreateGraphTemplateRunResponse,
  tags=["workflow-graph"],
)
async def create_graph_template_run(
  template_id: UUID,
  payload: CreateGraphTemplateRunRequest,
  response: Response,
  actor: Annotated[User, Depends(get_current_user)],
  session: Annotated[AsyncSession, Depends(get_db_session)],
  instantiation_service: WorkflowVideoInstantiationService = Depends(
    get_workflow_video_instantiation_service
  ),
  command_id_header: Annotated[str | None, Header(alias="X-Command-ID", max_length=128)] = None,
) -> CreateGraphTemplateRunResponse:
  command_id = _resolve_command_id(command_id_header, response)

  async def operation() -> dict[str, object]:
    result = await instantiation_service.instantiate_graph_template(
      actor=actor,
      template_id=template_id,
      inputs=payload.inputs,
      participants_snapshot=payload.participants_snapshot,
      department_id=payload.department_id,
      run_label=payload.run_label,
      commit=False,
    )
    return instantiation_service.to_response(result).model_dump(mode="json")

  result_payload = await WorkflowCommandExecutor(session).execute(
    command_id=command_id,
    command_type="create_run",
    payload={"template_id": str(template_id), **payload.model_dump(mode="json")},
    operation=operation,
    actor_user_id=actor.id,
    aggregate_type="workflow_run",
  )
  return CreateGraphTemplateRunResponse.model_validate(result_payload)


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
  session: Annotated[AsyncSession, Depends(get_db_session)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
  limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[WorkflowGraphInstanceRead]:
  await WorkflowAccessPolicy(session).ensure_can_manage_templates(
    actor=actor,
    template_id=template_id,
  )
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
  session: Annotated[AsyncSession, Depends(get_db_session)],
  form_service: Annotated[WorkflowVideoFormService, Depends(get_workflow_video_form_service)],
  node_key: Annotated[str, Query(min_length=1, max_length=64)],
) -> InstanceSubmissionsResponse:
  await WorkflowAccessPolicy(session).ensure_can_read_instance(actor=actor, instance_id=instance_id)
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
  "/instances/{instance_id}/close-capture",
  response_model=CloseCaptureResponse,
  tags=["workflow-graph"],
)
async def close_instance_capture(
  instance_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  form_service: Annotated[WorkflowVideoFormService, Depends(get_workflow_video_form_service)],
) -> CloseCaptureResponse:
  return await form_service.close_capture(actor=actor, instance_id=instance_id)


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


@router.post(
  "/instances/{instance_id}/dispatch-topic",
  response_model=DispatchTopicResponse,
  tags=["workflow-graph"],
)
async def dispatch_instance_topic(
  instance_id: UUID,
  payload: DispatchTopicRequest,
  actor: Annotated[User, Depends(get_current_user)],
  form_service: Annotated[WorkflowVideoFormService, Depends(get_workflow_video_form_service)],
) -> DispatchTopicResponse:
  return await form_service.dispatch_topic(
    actor=actor,
    instance_id=instance_id,
    topic_id=payload.topic_id,
    title=payload.title,
    script_writer_user_id=payload.script_writer_user_id,
    source_node_instance_id=payload.source_node_instance_id,
  )


@router.get(
  "/runs",
  response_model=list[DepartmentRunSummaryRead],
  tags=["workflow-graph"],
)
async def list_department_runs(
  department_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  session: Annotated[AsyncSession, Depends(get_db_session)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
  limit: Annotated[int, Query(ge=1, le=100)] = 50,
  include_completed: Annotated[bool, Query()] = True,
) -> list[DepartmentRunSummaryRead]:
  await ensure_department_stats_access(session, actor, department_id)
  runs = await workflow_graph_service.list_department_runs(
    department_id=department_id,
    limit=limit,
    include_completed=include_completed,
  )
  return [
    DepartmentRunSummaryRead(
      instance_id=run.instance_id,
      run_label=run.run_label,
      status=run.status.value,
      created_at=run.created_at,
      event_count=run.event_count,
      department_id=run.department_id,
    )
    for run in runs
  ]


@router.get(
  "/instances/{instance_id}/events",
  response_model=WorkflowRunEventListResponse,
  tags=["workflow-graph"],
)
async def list_graph_instance_events(
  instance_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  session: Annotated[AsyncSession, Depends(get_db_session)],
  event_service: Annotated[WorkflowRunEventService, Depends(get_workflow_run_event_service)],
  limit: Annotated[int, Query(ge=1, le=100)] = 20,
  offset: Annotated[int, Query(ge=0)] = 0,
) -> WorkflowRunEventListResponse:
  await WorkflowAccessPolicy(session).ensure_can_read_instance(actor=actor, instance_id=instance_id)
  return await event_service.list_for_instance(
    instance_id=instance_id,
    limit=limit,
    offset=offset,
  )


@router.get(
  "/instances/{instance_id}/children",
  response_model=list[WorkflowGraphInstanceRead],
  tags=["workflow-graph"],
)
async def list_graph_instance_children(
  instance_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  session: Annotated[AsyncSession, Depends(get_db_session)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
  limit: Annotated[int, Query(ge=1, le=100)] = 50,
  include_completed: Annotated[bool, Query()] = False,
) -> list[WorkflowGraphInstanceRead]:
  await WorkflowAccessPolicy(session).ensure_can_read_instance(actor=actor, instance_id=instance_id)
  children = await workflow_graph_service.list_child_instances(
    parent_instance_id=instance_id,
    limit=limit,
    include_completed=include_completed,
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
  session: Annotated[AsyncSession, Depends(get_db_session)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
) -> WorkflowGraphInstanceDetailRead:
  instance = await WorkflowAccessPolicy(session).ensure_can_read_instance(
    actor=actor,
    instance_id=instance_id,
  )
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
  response: Response,
  actor: Annotated[User, Depends(get_current_user)],
  session: Annotated[AsyncSession, Depends(get_db_session)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
  command_id_header: Annotated[str | None, Header(alias="X-Command-ID", max_length=128)] = None,
) -> WorkflowGraphInstanceDetailRead:
  command_id = _resolve_command_id(command_id_header, response)

  async def operation() -> dict[str, object]:
    await workflow_graph_service.complete_node_instance(
      node_instance_id=node_instance_id,
      actor_id=actor.id,
      context_updates=payload.context_updates,
      expected_context_version=payload.expected_context_version,
      commit=False,
    )
    node_instance = await session.get(WorkflowNodeInstance, node_instance_id)
    if node_instance is None:
      raise NotFoundError("节点实例不存在。")
    instance = await workflow_graph_service.get_instance(instance_id=node_instance.instance_id)
    node_instances = await workflow_graph_service.list_node_instances_for_graph(
      instance_id=node_instance.instance_id
    )
    return _build_instance_detail(instance, node_instances).model_dump(mode="json")

  result_payload = await WorkflowCommandExecutor(session).execute(
    command_id=command_id,
    command_type="complete_node",
    payload={"node_instance_id": str(node_instance_id), **payload.model_dump(mode="json")},
    operation=operation,
    actor_user_id=actor.id,
    aggregate_type="workflow_node",
    aggregate_id=node_instance_id,
  )
  return WorkflowGraphInstanceDetailRead.model_validate(result_payload)


@router.post(
  "/node-instances/{node_instance_id}/deep-reject",
  response_model=WorkflowGraphInstanceDetailRead,
  tags=["workflow-graph"],
)
async def deep_reject_node_instance(
  node_instance_id: UUID,
  payload: WorkflowNodeDeepRejectRequest,
  response: Response,
  actor: Annotated[User, Depends(get_current_user)],
  session: Annotated[AsyncSession, Depends(get_db_session)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
  command_id_header: Annotated[str | None, Header(alias="X-Command-ID", max_length=128)] = None,
) -> WorkflowGraphInstanceDetailRead:
  command_id = _resolve_command_id(command_id_header, response)

  async def operation() -> dict[str, object]:
    instance_id = await workflow_graph_service.deep_reject_to_upstream(
      node_instance_id=node_instance_id,
      actor_id=actor.id,
      target_node_key=payload.target_node_key,
      reason=payload.reason,
      commit=False,
    )
    instance = await workflow_graph_service.get_instance(instance_id=instance_id)
    node_instances = await workflow_graph_service.list_node_instances_for_graph(instance_id=instance_id)
    return _build_instance_detail(instance, node_instances).model_dump(mode="json")

  result_payload = await WorkflowCommandExecutor(session).execute(
    command_id=command_id,
    command_type="deep_reject",
    payload={"node_instance_id": str(node_instance_id), **payload.model_dump(mode="json")},
    operation=operation,
    actor_user_id=actor.id,
    aggregate_type="workflow_node",
    aggregate_id=node_instance_id,
  )
  return WorkflowGraphInstanceDetailRead.model_validate(result_payload)


@router.post(
  "/node-instances/{node_instance_id}/takeover",
  response_model=WorkflowGraphInstanceDetailRead,
  tags=["workflow-graph"],
)
async def takeover_node_instance(
  node_instance_id: UUID,
  payload: WorkflowNodeTakeoverRequest,
  response: Response,
  actor: Annotated[User, Depends(get_current_user)],
  session: Annotated[AsyncSession, Depends(get_db_session)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
  command_id_header: Annotated[str | None, Header(alias="X-Command-ID", max_length=128)] = None,
) -> WorkflowGraphInstanceDetailRead:
  command_id = _resolve_command_id(command_id_header, response)

  async def operation() -> dict[str, object]:
    instance_id = await workflow_graph_service.takeover_node_instance(
      node_instance_id=node_instance_id,
      actor_id=actor.id,
      actor_role=actor.role,
      assignee_id=payload.assignee_user_id,
      reason=payload.reason,
      commit=False,
    )
    instance = await workflow_graph_service.get_instance(instance_id=instance_id)
    node_instances = await workflow_graph_service.list_node_instances_for_graph(instance_id=instance_id)
    return _build_instance_detail(instance, node_instances).model_dump(mode="json")

  result_payload = await WorkflowCommandExecutor(session).execute(
    command_id=command_id,
    command_type="takeover",
    payload={"node_instance_id": str(node_instance_id), **payload.model_dump(mode="json")},
    operation=operation,
    actor_user_id=actor.id,
    aggregate_type="workflow_node",
    aggregate_id=node_instance_id,
  )
  return WorkflowGraphInstanceDetailRead.model_validate(result_payload)


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


@router.get(
  "/schedules",
  response_model=list[GraphTemplateScheduleRead],
  tags=["workflow-graph"],
)
async def list_graph_template_schedules(
  actor: Annotated[User, Depends(get_current_user)],
  schedule_service: Annotated[
    WorkflowGraphTemplateScheduleService,
    Depends(get_workflow_graph_template_schedule_service),
  ],
) -> list[GraphTemplateScheduleRead]:
  return await schedule_service.list_schedules(actor=actor)


@router.post(
  "/schedules",
  response_model=GraphTemplateScheduleRead,
  tags=["workflow-graph"],
)
async def create_graph_template_schedule(
  payload: GraphTemplateScheduleCreateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  schedule_service: Annotated[
    WorkflowGraphTemplateScheduleService,
    Depends(get_workflow_graph_template_schedule_service),
  ],
) -> GraphTemplateScheduleRead:
  return await schedule_service.create_schedule(actor=actor, payload=payload)


@router.patch(
  "/schedules/{schedule_id}",
  response_model=GraphTemplateScheduleRead,
  tags=["workflow-graph"],
)
async def update_graph_template_schedule(
  schedule_id: UUID,
  payload: GraphTemplateScheduleUpdateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  schedule_service: Annotated[
    WorkflowGraphTemplateScheduleService,
    Depends(get_workflow_graph_template_schedule_service),
  ],
) -> GraphTemplateScheduleRead:
  return await schedule_service.update_schedule(actor=actor, schedule_id=schedule_id, payload=payload)


@router.post(
  "/schedules/{schedule_id}/run-now",
  response_model=GraphTemplateScheduleRunNowResponse,
  tags=["workflow-graph"],
)
async def run_graph_template_schedule_now(
  schedule_id: UUID,
  response: Response,
  actor: Annotated[User, Depends(get_current_user)],
  session: Annotated[AsyncSession, Depends(get_db_session)],
  schedule_service: Annotated[
    WorkflowGraphTemplateScheduleService,
    Depends(get_workflow_graph_template_schedule_service),
  ],
  command_id_header: Annotated[str | None, Header(alias="X-Command-ID", max_length=128)] = None,
) -> GraphTemplateScheduleRunNowResponse:
  command_id = _resolve_command_id(command_id_header, response)

  async def operation() -> dict[str, object]:
    result = await schedule_service.run_schedule_now(
      actor=actor,
      schedule_id=schedule_id,
      commit=False,
    )
    return result.model_dump(mode="json")

  result_payload = await WorkflowCommandExecutor(session).execute(
    command_id=command_id,
    command_type="schedule_run_now",
    payload={"schedule_id": str(schedule_id)},
    operation=operation,
    actor_user_id=actor.id,
    aggregate_type="workflow_schedule",
    aggregate_id=schedule_id,
  )
  return GraphTemplateScheduleRunNowResponse.model_validate(result_payload)
