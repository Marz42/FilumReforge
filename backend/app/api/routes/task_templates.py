from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
  get_current_user,
  get_management_user,
  get_task_automation_service,
  get_task_template_service,
)
from app.models import TaskTemplate, TaskTemplateStep, User
from app.schemas.task_templates import (
  TaskScheduleCreateRequest,
  TaskScheduleRead,
  TaskScheduleUpdateRequest,
  TaskTemplateCreateRequest,
  TaskTemplateInstantiationRead,
  TaskTemplateInstantiateRequest,
  TaskTemplateRead,
  TaskTemplateStepRead,
  TaskTemplateUpdateRequest,
)
from app.schemas.tasks import TaskRead
from app.services.task_automation_service import TaskAutomationService
from app.services.task_template_service import TaskTemplateService

router = APIRouter(prefix="/task-templates")


def _build_template_step_read(step: TaskTemplateStep) -> TaskTemplateStepRead:
  return TaskTemplateStepRead.model_validate(step).model_copy(
    update={
      "depends_on_step_keys": [
        dependency.depends_on_step.step_key
        for dependency in step.dependencies
      ],
    }
  )


def _build_template_read(template: TaskTemplate) -> TaskTemplateRead:
  return TaskTemplateRead.model_validate(template).model_copy(
    update={
      "steps": [_build_template_step_read(step) for step in template.steps],
      "schedules": [TaskScheduleRead.model_validate(schedule) for schedule in template.schedules],
    }
  )


@router.get("", response_model=list[TaskTemplateRead])
async def list_task_templates(
  actor: Annotated[User, Depends(get_current_user)],
  task_template_service: Annotated[TaskTemplateService, Depends(get_task_template_service)],
) -> list[TaskTemplateRead]:
  templates = await task_template_service.list_templates(actor=actor)
  return [_build_template_read(template) for template in templates]


@router.get("/{template_id}", response_model=TaskTemplateRead)
async def read_task_template(
  template_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  task_template_service: Annotated[TaskTemplateService, Depends(get_task_template_service)],
) -> TaskTemplateRead:
  template = await task_template_service.get_template(actor=actor, template_id=template_id)
  return _build_template_read(template)


@router.post("", response_model=TaskTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_task_template(
  payload: TaskTemplateCreateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  task_template_service: Annotated[TaskTemplateService, Depends(get_task_template_service)],
) -> TaskTemplateRead:
  template = await task_template_service.create_template(
    actor=actor,
    code=payload.code,
    name=payload.name,
    category=payload.category,
    description=payload.description,
    trigger_type=payload.trigger_type,
    config=payload.config,
    is_active=payload.is_active,
    steps=[step.model_dump() for step in payload.steps],
  )
  return _build_template_read(template)


@router.patch("/{template_id}", response_model=TaskTemplateRead)
async def update_task_template(
  template_id: UUID,
  payload: TaskTemplateUpdateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  task_template_service: Annotated[TaskTemplateService, Depends(get_task_template_service)],
) -> TaskTemplateRead:
  template = await task_template_service.update_template(
    actor=actor,
    template_id=template_id,
    code=payload.code,
    name=payload.name,
    category=payload.category,
    description=payload.description,
    trigger_type=payload.trigger_type,
    config=payload.config,
    is_active=payload.is_active,
    steps=[step.model_dump() for step in payload.steps] if payload.steps is not None else None,
  )
  return _build_template_read(template)


@router.post("/{template_id}/instantiate", response_model=TaskTemplateInstantiationRead)
async def instantiate_task_template(
  template_id: UUID,
  payload: TaskTemplateInstantiateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  task_template_service: Annotated[TaskTemplateService, Depends(get_task_template_service)],
) -> TaskTemplateInstantiationRead:
  tasks = await task_template_service.instantiate_template(
    actor=actor,
    template_id=template_id,
    department_id=payload.department_id,
    watcher_user_ids=payload.watcher_user_ids,
    payload=payload.payload,
  )
  template = await task_template_service.get_template(actor=actor, template_id=template_id)
  return TaskTemplateInstantiationRead(
    template=_build_template_read(template),
    tasks=[TaskRead.model_validate(task) for task in tasks],
  )


@router.get("/schedules/list", response_model=list[TaskScheduleRead])
async def list_task_schedules(
  actor: Annotated[User, Depends(get_current_user)],
  task_automation_service: Annotated[TaskAutomationService, Depends(get_task_automation_service)],
) -> list[TaskScheduleRead]:
  schedules = await task_automation_service.list_schedules(actor=actor)
  return [TaskScheduleRead.model_validate(schedule) for schedule in schedules]


@router.post("/schedules", response_model=TaskScheduleRead, status_code=status.HTTP_201_CREATED)
async def create_task_schedule(
  payload: TaskScheduleCreateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  task_automation_service: Annotated[TaskAutomationService, Depends(get_task_automation_service)],
) -> TaskScheduleRead:
  schedule = await task_automation_service.create_schedule(
    actor=actor,
    template_id=payload.template_id,
    cron_expr=payload.cron_expr,
    timezone=payload.timezone,
    payload=payload.payload,
    is_active=payload.is_active,
  )
  return TaskScheduleRead.model_validate(schedule)


@router.patch("/schedules/{schedule_id}", response_model=TaskScheduleRead)
async def update_task_schedule(
  schedule_id: UUID,
  payload: TaskScheduleUpdateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  task_automation_service: Annotated[TaskAutomationService, Depends(get_task_automation_service)],
) -> TaskScheduleRead:
  schedule = await task_automation_service.update_schedule(
    actor=actor,
    schedule_id=schedule_id,
    cron_expr=payload.cron_expr,
    timezone=payload.timezone,
    payload=payload.payload,
    is_active=payload.is_active,
  )
  return TaskScheduleRead.model_validate(schedule)
