from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import (
  get_current_user,
  get_task_automation_service,
  get_task_template_service,
)
from app.models import TaskTemplate, TaskTemplateInstance, TaskTemplateStep, TaskTemplateStepRun, User
from app.schemas.task_templates import (
  TaskTemplateInstanceRead,
  TaskTemplateInstanceStepRead,
  TaskScheduleCreateRequest,
  TaskScheduleRead,
  TaskScheduleUpdateRequest,
  TaskTemplateCreateRequest,
  TaskTemplateInstantiationRead,
  TaskTemplateInstantiateRequest,
  TaskTemplateRead,
  TaskTemplateStepRunRead,
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


def _is_template_step_completed(step: TaskTemplateStep, step_runs: list[TaskTemplateStepRun]) -> bool:
  if not step_runs:
    return False
  if step.join_mode == "any":
    return any(step_run.status == "completed" for step_run in step_runs)
  return all(step_run.status == "completed" for step_run in step_runs)


def _build_template_step_run_read(step_run: TaskTemplateStepRun) -> TaskTemplateStepRunRead:
  return TaskTemplateStepRunRead.model_validate(step_run).model_copy(
    update={
      "assignee_email": step_run.assignee.email if step_run.assignee is not None else None,
      "task": TaskRead.model_validate(step_run.task) if step_run.task is not None else None,
    }
  )


def _build_template_instance_read(instance: TaskTemplateInstance) -> TaskTemplateInstanceRead:
  if instance.template is None:
    raise ValueError("模板实例缺少模板上下文。")

  ordered_step_runs = sorted(instance.step_runs, key=lambda current_run: current_run.created_at)
  step_runs_by_step_id: dict[UUID, list[TaskTemplateStepRun]] = {}
  for step_run in ordered_step_runs:
    step_runs_by_step_id.setdefault(step_run.template_step_id, []).append(step_run)

  completed_step_ids = {
    step.id
    for step in instance.template.steps
    if _is_template_step_completed(step, step_runs_by_step_id.get(step.id, []))
  }

  step_snapshots: list[TaskTemplateInstanceStepRead] = []
  ordered_steps = sorted(instance.template.steps, key=lambda current_step: (current_step.sort_order, current_step.created_at))
  for step in ordered_steps:
    step_runs = step_runs_by_step_id.get(step.id, [])
    blocked_dependency_keys = [
      dependency.depends_on_step.step_key
      for dependency in step.dependencies
      if dependency.depends_on_step is not None and dependency.depends_on_step_id not in completed_step_ids
    ]
    if step_runs:
      snapshot_status = "completed" if _is_template_step_completed(step, step_runs) else "active"
    elif blocked_dependency_keys:
      snapshot_status = "blocked"
    else:
      snapshot_status = "ready"

    step_snapshots.append(
      TaskTemplateInstanceStepRead(
        step=_build_template_step_read(step),
        status=snapshot_status,
        blocked_dependency_keys=blocked_dependency_keys,
        total_run_count=len(step_runs),
        active_run_count=sum(1 for step_run in step_runs if step_run.status == "active"),
        completed_run_count=sum(1 for step_run in step_runs if step_run.status == "completed"),
        step_runs=[_build_template_step_run_read(step_run) for step_run in step_runs],
      )
    )

  return TaskTemplateInstanceRead.model_validate(instance).model_copy(
    update={
      "initiator_email": instance.initiator.email if instance.initiator is not None else None,
      "department_name": instance.department.name if instance.department is not None else None,
      "step_snapshots": step_snapshots,
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


@router.get("/{template_id}/instances", response_model=list[TaskTemplateInstanceRead])
async def list_task_template_instances(
  template_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  task_template_service: Annotated[TaskTemplateService, Depends(get_task_template_service)],
  limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> list[TaskTemplateInstanceRead]:
  instances = await task_template_service.list_instances(
    actor=actor,
    template_id=template_id,
    limit=limit,
  )
  return [_build_template_instance_read(instance) for instance in instances]


@router.post("", response_model=TaskTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_task_template(
  payload: TaskTemplateCreateRequest,
  actor: Annotated[User, Depends(get_current_user)],
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
  actor: Annotated[User, Depends(get_current_user)],
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


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_template(
  template_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  task_template_service: Annotated[TaskTemplateService, Depends(get_task_template_service)],
) -> Response:
  await task_template_service.delete_template(actor=actor, template_id=template_id)
  return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{template_id}/instantiate", response_model=TaskTemplateInstantiationRead)
async def instantiate_task_template(
  template_id: UUID,
  payload: TaskTemplateInstantiateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  task_template_service: Annotated[TaskTemplateService, Depends(get_task_template_service)],
) -> TaskTemplateInstantiationRead:
  instantiation = await task_template_service.instantiate_template(
    actor=actor,
    template_id=template_id,
    department_id=payload.department_id,
    watcher_user_ids=payload.watcher_user_ids,
    payload=payload.payload,
  )
  template = await task_template_service.get_template(actor=actor, template_id=template_id)
  return TaskTemplateInstantiationRead(
    template=_build_template_read(template),
    instance=_build_template_instance_read(instantiation.instance),
    tasks=[TaskRead.model_validate(task) for task in instantiation.tasks],
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
  actor: Annotated[User, Depends(get_current_user)],
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
  actor: Annotated[User, Depends(get_current_user)],
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
