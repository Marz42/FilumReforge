from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user, get_task_service
from app.models import User
from app.schemas.tasks import TaskCreateRequest, TaskRead, TaskUpdateRequest
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks")


@router.get("", response_model=list[TaskRead])
async def list_tasks(
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
) -> list[TaskRead]:
  tasks = await task_service.list_tasks(actor=actor)
  return [TaskRead.model_validate(task) for task in tasks]


@router.get("/{task_id}", response_model=TaskRead)
async def read_task(
  task_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskRead:
  task = await task_service.get_task(actor=actor, task_id=task_id)
  return TaskRead.model_validate(task)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
  payload: TaskCreateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskRead:
  task = await task_service.create_task(
    actor=actor,
    title=payload.title,
    assignee_id=payload.assignee_id,
    description=payload.description,
    department_id=payload.department_id,
    due_date=payload.due_date,
    priority=payload.priority,
    dependency_ids=payload.dependency_ids or None,
  )
  return TaskRead.model_validate(task)


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
  task_id: UUID,
  payload: TaskUpdateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskRead:
  task = await task_service.update_task(
    actor=actor,
    task_id=task_id,
    title=payload.title,
    description=payload.description,
    assignee_id=payload.assignee_id,
    department_id=payload.department_id,
    due_date=payload.due_date,
    priority=payload.priority,
  )
  return TaskRead.model_validate(task)
