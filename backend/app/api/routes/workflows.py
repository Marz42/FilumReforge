from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user, get_management_user, get_workflow_engine_service
from app.models import User, WorkflowDefinition, WorkflowInstance, WorkflowStepRun
from app.schemas.workflows import (
  WorkflowActionRequest,
  WorkflowDefinitionCreateRequest,
  WorkflowDefinitionRead,
  WorkflowDefinitionUpdateRequest,
  WorkflowInstanceRead,
  WorkflowStartRequest,
  WorkflowStepRead,
  WorkflowStepRunRead,
)
from app.services.workflow_engine_service import WorkflowEngineService

router = APIRouter(prefix="/workflows")


def _build_definition_read(definition: WorkflowDefinition) -> WorkflowDefinitionRead:
  return WorkflowDefinitionRead.model_validate(definition).model_copy(
    update={"steps": [WorkflowStepRead.model_validate(step) for step in definition.steps]}
  )


def _build_step_run_read(step_run: WorkflowStepRun) -> WorkflowStepRunRead:
  return WorkflowStepRunRead.model_validate(step_run).model_copy(
    update={"step": WorkflowStepRead.model_validate(step_run.step) if step_run.step is not None else None}
  )


def _build_instance_read(instance: WorkflowInstance) -> WorkflowInstanceRead:
  return WorkflowInstanceRead.model_validate(instance).model_copy(
    update={
      "definition": _build_definition_read(instance.definition) if instance.definition is not None else None,
      "step_runs": [_build_step_run_read(step_run) for step_run in instance.step_runs],
    }
  )


@router.get("/definitions", response_model=list[WorkflowDefinitionRead])
async def list_workflow_definitions(
  actor: Annotated[User, Depends(get_current_user)],
  workflow_engine_service: Annotated[WorkflowEngineService, Depends(get_workflow_engine_service)],
) -> list[WorkflowDefinitionRead]:
  definitions = await workflow_engine_service.list_definitions(actor=actor)
  return [_build_definition_read(definition) for definition in definitions]


@router.get("/definitions/{definition_id}", response_model=WorkflowDefinitionRead)
async def read_workflow_definition(
  definition_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  workflow_engine_service: Annotated[WorkflowEngineService, Depends(get_workflow_engine_service)],
) -> WorkflowDefinitionRead:
  definition = await workflow_engine_service.get_definition(actor=actor, definition_id=definition_id)
  return _build_definition_read(definition)


@router.post("/definitions", response_model=WorkflowDefinitionRead, status_code=status.HTTP_201_CREATED)
async def create_workflow_definition(
  payload: WorkflowDefinitionCreateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  workflow_engine_service: Annotated[WorkflowEngineService, Depends(get_workflow_engine_service)],
) -> WorkflowDefinitionRead:
  definition = await workflow_engine_service.create_definition(
    actor=actor,
    code=payload.code,
    name=payload.name,
    scope_type=payload.scope_type,
    status=payload.status,
    version=payload.version,
    config=payload.config,
    steps=[step.model_dump(mode="json") for step in payload.steps],
  )
  return _build_definition_read(definition)


@router.patch("/definitions/{definition_id}", response_model=WorkflowDefinitionRead)
async def update_workflow_definition(
  definition_id: UUID,
  payload: WorkflowDefinitionUpdateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  workflow_engine_service: Annotated[WorkflowEngineService, Depends(get_workflow_engine_service)],
) -> WorkflowDefinitionRead:
  definition = await workflow_engine_service.update_definition(
    actor=actor,
    definition_id=definition_id,
    code=payload.code,
    name=payload.name,
    scope_type=payload.scope_type,
    status=payload.status,
    version=payload.version,
    config=payload.config,
    steps=[step.model_dump(mode="json") for step in payload.steps] if payload.steps is not None else None,
  )
  return _build_definition_read(definition)


@router.get("/instances", response_model=list[WorkflowInstanceRead])
async def list_workflow_instances(
  actor: Annotated[User, Depends(get_current_user)],
  workflow_engine_service: Annotated[WorkflowEngineService, Depends(get_workflow_engine_service)],
) -> list[WorkflowInstanceRead]:
  instances = await workflow_engine_service.list_instances(actor=actor)
  return [_build_instance_read(instance) for instance in instances]


@router.get("/instances/{instance_id}", response_model=WorkflowInstanceRead)
async def read_workflow_instance(
  instance_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  workflow_engine_service: Annotated[WorkflowEngineService, Depends(get_workflow_engine_service)],
) -> WorkflowInstanceRead:
  instance = await workflow_engine_service.get_instance(actor=actor, instance_id=instance_id)
  return _build_instance_read(instance)


@router.post("/instances/start", response_model=WorkflowInstanceRead, status_code=status.HTTP_201_CREATED)
async def start_workflow(
  payload: WorkflowStartRequest,
  actor: Annotated[User, Depends(get_current_user)],
  workflow_engine_service: Annotated[WorkflowEngineService, Depends(get_workflow_engine_service)],
) -> WorkflowInstanceRead:
  instance = await workflow_engine_service.start_workflow(
    actor=actor,
    definition_id=payload.definition_id,
    source_type=payload.source_type,
    source_id=payload.source_id,
    payload=payload.payload,
  )
  return _build_instance_read(instance)


@router.get("/step-runs/pending", response_model=list[WorkflowStepRunRead])
async def list_pending_workflow_step_runs(
  actor: Annotated[User, Depends(get_current_user)],
  workflow_engine_service: Annotated[WorkflowEngineService, Depends(get_workflow_engine_service)],
) -> list[WorkflowStepRunRead]:
  step_runs = await workflow_engine_service.list_pending_step_runs(actor=actor)
  return [_build_step_run_read(step_run) for step_run in step_runs]


@router.post("/step-runs/{step_run_id}/actions", response_model=WorkflowInstanceRead)
async def act_workflow_step_run(
  step_run_id: UUID,
  payload: WorkflowActionRequest,
  actor: Annotated[User, Depends(get_current_user)],
  workflow_engine_service: Annotated[WorkflowEngineService, Depends(get_workflow_engine_service)],
) -> WorkflowInstanceRead:
  instance = await workflow_engine_service.act_step_run(
    actor=actor,
    step_run_id=step_run_id,
    action=payload.action,
    comment=payload.comment,
  )
  return _build_instance_read(instance)
