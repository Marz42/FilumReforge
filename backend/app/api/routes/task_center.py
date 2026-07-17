from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_current_user, get_task_center_service, get_task_memo_service
from app.models import TaskMemo, User
from app.schemas.task_center import (
  TaskActionOptionRead,
  TaskCenterDepartmentOptionRead,
  TaskCenterHistoryItemRead,
  TaskCenterHistoryPageRead,
  TaskCenterInboxItemRead,
  TaskCenterInboxPageRead,
  TaskCenterPaginationRead,
  TaskCenterPermissionsRead,
  TaskCenterRead,
  TaskCenterTaskReferenceRead,
  TaskCenterTemplateSummaryRead,
  TaskCenterTrackingItemRead,
  TaskCenterTrackingPageRead,
  TaskCenterUserOptionRead,
  TaskMemoCreateRequest,
  TaskMemoRead,
  TaskMemoUpdateRequest,
)
from app.services.task_center_service import TaskCenterService
from app.services.task_memo_service import TaskMemoService, UNSET
from app.services.task_service import TaskHistoryEntry, TaskInboxEntry, TaskTrackingEntry

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


def _build_action_options(item) -> list[TaskActionOptionRead]:  # noqa: ANN001
  return [
    TaskActionOptionRead(action=option.action, label=option.label, button_type=option.button_type)
    for option in getattr(item, "available_actions", []) or []
  ]


def _build_inbox_item_read(item: TaskInboxEntry) -> TaskCenterInboxItemRead:
  return TaskCenterInboxItemRead(
    task_id=item.task_id,
    title=item.title,
    priority=item.priority,
    status=item.status,
    due_date=item.due_date,
    department_name=item.department_name,
    current_stage_label=item.current_stage_label,
    current_handler_label=item.current_handler_label,
    run_label=item.run_label,
    user_facing_state=item.user_facing_state,
    execution_mode=item.execution_mode,
    assignment_mode=item.assignment_mode,
    current_action_owner_id=item.current_action_owner_id,
    requires_action=item.requires_action,
    action_type=item.action_type,
    available_actions=_build_action_options(item),
  )


def _build_tracking_item_read(item: TaskTrackingEntry) -> TaskCenterTrackingItemRead:
  return TaskCenterTrackingItemRead(
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
    run_label=item.run_label,
    user_facing_state=item.user_facing_state,
    execution_mode=item.execution_mode,
    assignment_mode=item.assignment_mode,
    current_action_owner_id=item.current_action_owner_id,
    requires_action=item.requires_action,
    action_type=item.action_type,
    available_actions=_build_action_options(item),
  )


def _build_history_item_read(item: TaskHistoryEntry) -> TaskCenterHistoryItemRead:
  return TaskCenterHistoryItemRead(
    task_id=item.task_id,
    title=item.title,
    priority=item.priority,
    due_date=item.due_date,
    completed_at=item.completed_at,
    department_name=item.department_name,
    relation_types=item.relation_types,
    source_type=item.source_type,
    run_label=item.run_label,
    user_facing_state=item.user_facing_state,
  )


def _build_pagination_read(*, next_cursor: UUID | None, has_more: bool) -> TaskCenterPaginationRead:
  return TaskCenterPaginationRead(next_cursor=next_cursor, has_more=has_more)


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
    task_inbox=[_build_inbox_item_read(item) for item in snapshot.task_inbox],
    task_tracking=[_build_tracking_item_read(item) for item in snapshot.task_tracking],
    task_history=[_build_history_item_read(item) for item in snapshot.task_history],
    task_memos=[_build_task_memo_read(memo) for memo in snapshot.task_memos],
    inbox_pagination=_build_pagination_read(
      next_cursor=snapshot.inbox_next_cursor,
      has_more=snapshot.inbox_has_more,
    ),
    tracking_pagination=_build_pagination_read(
      next_cursor=snapshot.tracking_next_cursor,
      has_more=snapshot.tracking_has_more,
    ),
    history_pagination=_build_pagination_read(
      next_cursor=snapshot.history_next_cursor,
      has_more=snapshot.history_has_more,
    ),
  )


@router.get("/inbox", response_model=TaskCenterInboxPageRead)
async def read_task_center_inbox_page(
  actor: Annotated[User, Depends(get_current_user)],
  task_center_service: Annotated[TaskCenterService, Depends(get_task_center_service)],
  limit: Annotated[int, Query(ge=1, le=100)] = 50,
  cursor: UUID | None = None,
) -> TaskCenterInboxPageRead:
  page = await task_center_service.list_task_inbox_page(actor=actor, limit=limit, cursor=cursor)
  return TaskCenterInboxPageRead(
    items=[_build_inbox_item_read(item) for item in page.items],
    pagination=_build_pagination_read(next_cursor=page.next_cursor, has_more=page.has_more),
  )


@router.get("/tracking", response_model=TaskCenterTrackingPageRead)
async def read_task_center_tracking_page(
  actor: Annotated[User, Depends(get_current_user)],
  task_center_service: Annotated[TaskCenterService, Depends(get_task_center_service)],
  limit: Annotated[int, Query(ge=1, le=100)] = 50,
  cursor: UUID | None = None,
) -> TaskCenterTrackingPageRead:
  page = await task_center_service.list_task_tracking_page(actor=actor, limit=limit, cursor=cursor)
  return TaskCenterTrackingPageRead(
    items=[_build_tracking_item_read(item) for item in page.items],
    pagination=_build_pagination_read(next_cursor=page.next_cursor, has_more=page.has_more),
  )


@router.get("/history", response_model=TaskCenterHistoryPageRead)
async def read_task_center_history_page(
  actor: Annotated[User, Depends(get_current_user)],
  task_center_service: Annotated[TaskCenterService, Depends(get_task_center_service)],
  limit: Annotated[int, Query(ge=1, le=100)] = 50,
  cursor: UUID | None = None,
) -> TaskCenterHistoryPageRead:
  page = await task_center_service.list_task_history_page(actor=actor, limit=limit, cursor=cursor)
  return TaskCenterHistoryPageRead(
    items=[_build_history_item_read(item) for item in page.items],
    pagination=_build_pagination_read(next_cursor=page.next_cursor, has_more=page.has_more),
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
