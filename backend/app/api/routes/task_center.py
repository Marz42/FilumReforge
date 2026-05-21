from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_current_user, get_task_center_service, get_task_memo_service
from app.models import TaskMemo, User
from app.schemas.task_center import (
  TaskCenterDepartmentOptionRead,
  TaskCenterHistoryItemRead,
  TaskCenterInboxItemRead,
  TaskCenterPermissionsRead,
  TaskCenterRead,
  TaskCenterTaskReferenceRead,
  TaskCenterTemplateSummaryRead,
  TaskCenterTrackingItemRead,
  TaskCenterUserOptionRead,
  TaskMemoCreateRequest,
  TaskMemoRead,
  TaskMemoUpdateRequest,
)
from app.services.task_center_service import TaskCenterService
from app.services.task_memo_service import TaskMemoService, UNSET

router = APIRouter(prefix="/task-center")


def _build_task_reference(task) -> TaskCenterTaskReferenceRead | None:  # noqa: ANN001
  if task is None:
    return None
  return TaskCenterTaskReferenceRead(
    id=task.id,
    title=task.title,
    status=task.status,
    priority=task.priority,
    due_date=task.due_date,
  )


def _build_task_memo_read(memo: TaskMemo) -> TaskMemoRead:
  return TaskMemoRead(
    id=memo.id,
    owner_user_id=memo.owner_user_id,
    related_task_id=memo.related_task_id,
    title=memo.title,
    content=memo.content,
    is_pinned=memo.is_pinned,
    created_at=memo.created_at,
    updated_at=memo.updated_at,
    related_task=_build_task_reference(memo.related_task),
  )


@router.get("", response_model=TaskCenterRead)
async def read_task_center(
  actor: Annotated[User, Depends(get_current_user)],
  task_center_service: Annotated[TaskCenterService, Depends(get_task_center_service)],
) -> TaskCenterRead:
  snapshot = await task_center_service.get_task_center(actor=actor)
  return TaskCenterRead(
    permissions=TaskCenterPermissionsRead(
      can_manage_templates=snapshot.permissions["can_manage_templates"],
      can_publish_task=snapshot.permissions["can_publish_task"],
    ),
    template_summaries=[
      TaskCenterTemplateSummaryRead(
        id=item.id,
        name=item.name,
        category=item.category,
        is_active=item.is_active,
        step_count=item.step_count,
      )
      for item in snapshot.template_summaries
    ],
    publish_department_options=[
      TaskCenterDepartmentOptionRead(id=item.id, label=item.label)
      for item in snapshot.publish_department_options
    ],
    publish_user_options=[
      TaskCenterUserOptionRead(
        user_id=item.user_id,
        email=item.email,
        real_name=item.real_name,
        department_id=item.department_id,
        department_name=item.department_name,
        label=item.label,
      )
      for item in snapshot.publish_user_options
    ],
    task_inbox=[
      TaskCenterInboxItemRead(
        task_id=item.task_id,
        title=item.title,
        priority=item.priority,
        status=item.status,
        due_date=item.due_date,
        department_name=item.department_name,
        current_stage_label=item.current_stage_label,
        current_handler_label=item.current_handler_label,
      )
      for item in snapshot.task_inbox
    ],
    task_tracking=[
      TaskCenterTrackingItemRead(
        task_id=item.task_id,
        title=item.title,
        priority=item.priority,
        status=item.status,
        due_date=item.due_date,
        department_name=item.department_name,
        relation_types=item.relation_types,
        current_stage_label=item.current_stage_label,
        current_handler_label=item.current_handler_label,
        latest_deliverable_submitted_at=item.latest_deliverable_submitted_at,
        rework_count=item.rework_count,
        review_quality_score=item.review_quality_score,
        is_pending_review=item.is_pending_review,
      )
      for item in snapshot.task_tracking
    ],
    task_history=[
      TaskCenterHistoryItemRead(
        task_id=item.task_id,
        title=item.title,
        priority=item.priority,
        due_date=item.due_date,
        completed_at=item.completed_at,
        department_name=item.department_name,
        relation_types=item.relation_types,
        source_type=item.source_type,
      )
      for item in snapshot.task_history
    ],
    task_memos=[_build_task_memo_read(memo) for memo in snapshot.task_memos],
  )


@router.post("/memos", response_model=TaskMemoRead, status_code=status.HTTP_201_CREATED)
async def create_task_memo(
  payload: TaskMemoCreateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  task_memo_service: Annotated[TaskMemoService, Depends(get_task_memo_service)],
) -> TaskMemoRead:
  memo = await task_memo_service.create_memo(
    actor=actor,
    title=payload.title,
    content=payload.content,
    related_task_id=payload.related_task_id,
    is_pinned=payload.is_pinned,
  )
  return _build_task_memo_read(memo)


@router.patch("/memos/{memo_id}", response_model=TaskMemoRead)
async def update_task_memo(
  memo_id: UUID,
  payload: TaskMemoUpdateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  task_memo_service: Annotated[TaskMemoService, Depends(get_task_memo_service)],
) -> TaskMemoRead:
  memo = await task_memo_service.update_memo(
    actor=actor,
    memo_id=memo_id,
    title=payload.title if "title" in payload.model_fields_set else UNSET,
    content=payload.content,
    related_task_id=payload.related_task_id if "related_task_id" in payload.model_fields_set else UNSET,
    is_pinned=payload.is_pinned,
  )
  return _build_task_memo_read(memo)


@router.delete("/memos/{memo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_memo(
  memo_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  task_memo_service: Annotated[TaskMemoService, Depends(get_task_memo_service)],
) -> Response:
  await task_memo_service.delete_memo(actor=actor, memo_id=memo_id)
  return Response(status_code=status.HTTP_204_NO_CONTENT)
