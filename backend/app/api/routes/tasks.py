from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_object_storage_service, get_task_service
from app.core.database import get_db_session
from app.core.enums import AttachmentStatus, AttachmentTargetType, CommentFormat
from app.models import Attachment, AttachmentLink, User
from app.schemas.attachments import AttachmentRead
from app.schemas.tasks import (
  TaskActivityEntryRead,
  TaskAssignmentDelegateRequest,
  TaskAssignmentRejectRequest,
  TaskBoardColumnRead,
  TaskCommentRead,
  TaskCreateRequest,
  TaskDeliverableReviewRequest,
  TaskDeliverableSubmitRequest,
  TaskGanttEntryRead,
  TaskLogRead,
  TaskRead,
  TaskStatsSummaryRead,
  TaskStatusUpdateRequest,
  TaskUpdateRequest,
  TaskWatcherBatchRequest,
  TaskWatcherRead,
  TaskWorkloadEntryRead,
)
from app.services.object_storage_service import ObjectStorageService
from app.services.task_service import CommentAttachmentInput, TaskActivityEntry, TaskService

router = APIRouter(prefix="/tasks")


async def _build_attachment_read(
  attachment: Attachment,
  object_storage_service: ObjectStorageService,
) -> AttachmentRead:
  from app.api.attachment_serializers import serialize_attachment_read

  return await serialize_attachment_read(attachment, object_storage_service)


async def _list_comment_attachments(
  *,
  session: AsyncSession,
  comment_id: UUID,
  object_storage_service: ObjectStorageService,
) -> list[AttachmentRead]:
  attachments = list(
    await session.scalars(
      select(Attachment)
      .join(Attachment.links)
      .where(
        Attachment.status != AttachmentStatus.DELETED,
        AttachmentLink.target_type == AttachmentTargetType.TASK_COMMENT,
        AttachmentLink.target_id == comment_id,
      )
      .order_by(Attachment.created_at.asc())
    )
  )
  result: list[AttachmentRead] = []
  for attachment in attachments:
    result.append(await _build_attachment_read(attachment, object_storage_service))
  return result


async def _build_task_comment_read(
  *,
  session: AsyncSession,
  comment,
  object_storage_service: ObjectStorageService,
) -> TaskCommentRead:
  attachments = await _list_comment_attachments(
    session=session,
    comment_id=comment.id,
    object_storage_service=object_storage_service,
  )
  return TaskCommentRead.model_validate(comment).model_copy(update={"attachments": attachments})


async def _build_task_activity_read(
  *,
  session: AsyncSession,
  activity_entry: TaskActivityEntry,
  object_storage_service: ObjectStorageService,
) -> TaskActivityEntryRead:
  comment = None
  if activity_entry.comment is not None:
    comment = await _build_task_comment_read(
      session=session,
      comment=activity_entry.comment,
      object_storage_service=object_storage_service,
    )
  log = None
  if activity_entry.log is not None:
    log = TaskLogRead.model_validate(activity_entry.log)
  return TaskActivityEntryRead(
    entry_type=activity_entry.entry_type,
    created_at=activity_entry.created_at,
    comment=comment,
    log=log,
  )


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


@router.get("/stats/summary", response_model=TaskStatsSummaryRead)
async def read_task_stats_summary(
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskStatsSummaryRead:
  summary = await task_service.get_task_stats_summary(actor=actor)
  return TaskStatsSummaryRead(
    total_tasks=summary.total_tasks,
    completed_tasks=summary.completed_tasks,
    completion_rate=summary.completion_rate,
    overdue_tasks=summary.overdue_tasks,
    overdue_rate=summary.overdue_rate,
    tasks_by_status={status.value: count for status, count in summary.tasks_by_status.items()},
  )


@router.get("/stats/workload", response_model=list[TaskWorkloadEntryRead])
async def read_task_workload(
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
) -> list[TaskWorkloadEntryRead]:
  workload = await task_service.get_task_workload(actor=actor)
  return [TaskWorkloadEntryRead.model_validate(row) for row in workload]


@router.get("/views/board", response_model=list[TaskBoardColumnRead])
async def read_task_board(
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
) -> list[TaskBoardColumnRead]:
  board = await task_service.get_task_board(actor=actor)
  return [
    TaskBoardColumnRead(
      status=column.status,
      tasks=[TaskRead.model_validate(task) for task in column.tasks],
    )
    for column in board
  ]


@router.get("/views/gantt", response_model=list[TaskGanttEntryRead])
async def read_task_gantt(
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
) -> list[TaskGanttEntryRead]:
  gantt_entries = await task_service.get_task_gantt(actor=actor)
  return [
    TaskGanttEntryRead(
      task=TaskRead.model_validate(entry.task),
      dependency_ids=entry.dependency_ids,
    )
    for entry in gantt_entries
  ]


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


@router.get("/{task_id}/watchers", response_model=list[TaskWatcherRead])
async def list_task_watchers(
  task_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
) -> list[TaskWatcherRead]:
  watchers = await task_service.list_task_watchers(actor=actor, task_id=task_id)
  return [TaskWatcherRead.model_validate(watcher) for watcher in watchers]


@router.post("/{task_id}/watchers", response_model=list[TaskWatcherRead])
async def add_task_watchers(
  task_id: UUID,
  payload: TaskWatcherBatchRequest,
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
) -> list[TaskWatcherRead]:
  watchers = await task_service.add_task_watchers(
    actor=actor,
    task_id=task_id,
    watcher_user_ids=payload.user_ids,
  )
  return [TaskWatcherRead.model_validate(watcher) for watcher in watchers]


@router.delete("/{task_id}/watchers/{watcher_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_watcher(
  task_id: UUID,
  watcher_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
) -> Response:
  await task_service.remove_task_watcher(
    actor=actor,
    task_id=task_id,
    watcher_id=watcher_id,
  )
  return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{task_id}/status", response_model=TaskRead)
async def update_task_status(
  task_id: UUID,
  payload: TaskStatusUpdateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskRead:
  task = await task_service.transition_task_status(
    actor=actor,
    task_id=task_id,
    target_status=payload.status,
  )
  return TaskRead.model_validate(task)


@router.post("/{task_id}/accept", response_model=TaskRead)
async def accept_task_assignment(
  task_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskRead:
  task = await task_service.accept_task_assignment(
    actor=actor,
    task_id=task_id,
  )
  return TaskRead.model_validate(task)


@router.post("/{task_id}/reject", response_model=TaskRead)
async def reject_task_assignment(
  task_id: UUID,
  payload: TaskAssignmentRejectRequest,
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskRead:
  task = await task_service.reject_task_assignment(
    actor=actor,
    task_id=task_id,
    reason=payload.reason or "",
  )
  return TaskRead.model_validate(task)


@router.post("/{task_id}/delegate", response_model=TaskRead)
async def delegate_task_assignment(
  task_id: UUID,
  payload: TaskAssignmentDelegateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskRead:
  task = await task_service.delegate_task_assignment(
    actor=actor,
    task_id=task_id,
    assignee_id=payload.assignee_id,
    reason=payload.reason or "",
  )
  return TaskRead.model_validate(task)


@router.post("/{task_id}/deliverable", response_model=TaskRead)
async def submit_task_deliverable(
  task_id: UUID,
  payload: TaskDeliverableSubmitRequest,
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskRead:
  task = await task_service.submit_task_deliverable(
    actor=actor,
    task_id=task_id,
    summary=payload.summary,
    attachment_ids=payload.attachment_ids,
  )
  return TaskRead.model_validate(task)


@router.post("/{task_id}/review", response_model=TaskRead)
async def review_task_deliverable(
  task_id: UUID,
  payload: TaskDeliverableReviewRequest,
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskRead:
  task = await task_service.review_task_deliverable(
    actor=actor,
    task_id=task_id,
    approve=payload.action == "approve",
    comment=payload.comment,
    quality_score=payload.quality_score,
  )
  return TaskRead.model_validate(task)


@router.get("/{task_id}/comments", response_model=list[TaskCommentRead])
async def list_task_comments(
  task_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
  session: Annotated[AsyncSession, Depends(get_db_session)],
  object_storage_service: Annotated[ObjectStorageService, Depends(get_object_storage_service)],
) -> list[TaskCommentRead]:
  comments = await task_service.list_task_comments(actor=actor, task_id=task_id)
  result: list[TaskCommentRead] = []
  for comment in comments:
    result.append(
      await _build_task_comment_read(
        session=session,
        comment=comment,
        object_storage_service=object_storage_service,
      )
    )
  return result


@router.post("/{task_id}/comments", response_model=TaskCommentRead, status_code=status.HTTP_201_CREATED)
async def create_task_comment(
  task_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
  session: Annotated[AsyncSession, Depends(get_db_session)],
  object_storage_service: Annotated[ObjectStorageService, Depends(get_object_storage_service)],
  content: Annotated[str, Form(...)],
  content_format: Annotated[CommentFormat, Form()] = CommentFormat.MARKDOWN,
  is_internal: Annotated[bool, Form()] = False,
  files: Annotated[list[UploadFile] | None, File()] = None,
) -> TaskCommentRead:
  attachments = [
    CommentAttachmentInput(
      filename=file.filename or "upload.bin",
      content_type=file.content_type or "application/octet-stream",
      content=await file.read(),
    )
    for file in files or []
  ]
  comment = await task_service.create_task_comment(
    actor=actor,
    task_id=task_id,
    content=content,
    content_format=content_format,
    is_internal=is_internal,
    attachments=attachments or None,
  )
  return await _build_task_comment_read(
    session=session,
    comment=comment,
    object_storage_service=object_storage_service,
  )


@router.get("/{task_id}/activity", response_model=list[TaskActivityEntryRead])
async def list_task_activity(
  task_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
  session: Annotated[AsyncSession, Depends(get_db_session)],
  object_storage_service: Annotated[ObjectStorageService, Depends(get_object_storage_service)],
) -> list[TaskActivityEntryRead]:
  activity = await task_service.list_task_activity(actor=actor, task_id=task_id)
  result: list[TaskActivityEntryRead] = []
  for activity_entry in activity:
    result.append(
      await _build_task_activity_read(
        session=session,
        activity_entry=activity_entry,
        object_storage_service=object_storage_service,
      )
    )
  return result
