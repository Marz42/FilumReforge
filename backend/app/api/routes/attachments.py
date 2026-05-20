from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.attachment_access import assert_can_download_attachment
from app.api.attachment_content import build_content_disposition
from app.api.dependencies import (
  get_attachment_service,
  get_current_user,
  get_db_session,
  get_document_service,
  get_message_center_service,
  get_object_storage_service,
  get_profile_service,
  get_report_service,
  get_task_service,
)
from app.core.enums import AttachmentTargetType, AttachmentVisibility
from app.api.attachment_serializers import serialize_attachment_read
from app.models import Attachment, TaskComment, User
from app.schemas.attachments import AttachmentRead
from app.services.attachment_service import AttachmentService
from app.services.document_service import DocumentService
from app.services.message_center_service import MessageCenterService
from app.services.object_storage_service import ObjectStorageService
from app.services.profile_service import ProfileService
from app.services.report_service import ReportService
from app.services.task_service import TaskService

router = APIRouter(prefix="/attachments")


def _validate_attachment_target(
  *,
  target_type: AttachmentTargetType | None,
  target_id: UUID | None,
) -> None:
  if (target_type is None) != (target_id is None):
    raise HTTPException(
      status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
      detail="target_type 和 target_id 必须同时提供。",
    )


async def _resolve_bypass_uploader_filter(
  *,
  session: AsyncSession,
  actor: User,
  target_type: AttachmentTargetType | None,
  target_id: UUID | None,
  task_service: TaskService,
  report_service: ReportService,
) -> bool:
  if target_type is None or target_id is None:
    return False
  if target_type == AttachmentTargetType.TASK:
    await task_service.get_task(actor=actor, task_id=target_id)
    return True
  if target_type == AttachmentTargetType.TASK_COMMENT:
    comment = await session.get(TaskComment, target_id)
    if comment is None:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评论不存在。")
    await task_service.get_task(actor=actor, task_id=comment.task_id)
    return True
  if target_type == AttachmentTargetType.REPORT:
    await report_service.get_report(actor=actor, report_id=target_id)
    return True
  return False


@router.get("", response_model=list[AttachmentRead])
async def list_attachments(
  session: Annotated[AsyncSession, Depends(get_db_session)],
  actor: Annotated[User, Depends(get_current_user)],
  attachment_service: Annotated[AttachmentService, Depends(get_attachment_service)],
  object_storage_service: Annotated[ObjectStorageService, Depends(get_object_storage_service)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
  report_service: Annotated[ReportService, Depends(get_report_service)],
  target_type: AttachmentTargetType | None = None,
  target_id: UUID | None = None,
) -> list[AttachmentRead]:
  _validate_attachment_target(target_type=target_type, target_id=target_id)
  bypass = await _resolve_bypass_uploader_filter(
    session=session,
    actor=actor,
    target_type=target_type,
    target_id=target_id,
    task_service=task_service,
    report_service=report_service,
  )
  attachments = await attachment_service.list_attachments(
    actor=actor,
    target_type=target_type,
    target_id=target_id,
    bypass_uploader_filter=bypass,
  )
  result: list[AttachmentRead] = []
  for attachment in attachments:
    result.append(await serialize_attachment_read(attachment, object_storage_service))
  return result


@router.post("", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
  actor: Annotated[User, Depends(get_current_user)],
  attachment_service: Annotated[AttachmentService, Depends(get_attachment_service)],
  object_storage_service: Annotated[ObjectStorageService, Depends(get_object_storage_service)],
  file: Annotated[UploadFile, File(...)],
  visibility: Annotated[AttachmentVisibility, Form()] = AttachmentVisibility.PRIVATE,
  target_type: Annotated[AttachmentTargetType | None, Form()] = None,
  target_id: Annotated[UUID | None, Form()] = None,
  relation: Annotated[str, Form()] = "primary",
) -> AttachmentRead:
  _validate_attachment_target(target_type=target_type, target_id=target_id)

  content = await file.read()
  attachment = await attachment_service.upload_attachment(
    actor=actor,
    filename=file.filename or "upload.bin",
    content_type=file.content_type or "application/octet-stream",
    content=content,
    visibility=visibility,
    target_type=target_type,
    target_id=target_id,
    relation=relation,
  )
  return await serialize_attachment_read(attachment, object_storage_service)


@router.get("/{attachment_id}/content")
async def download_attachment_content(
  attachment_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  session: Annotated[AsyncSession, Depends(get_db_session)],
  attachment_service: Annotated[AttachmentService, Depends(get_attachment_service)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
  report_service: Annotated[ReportService, Depends(get_report_service)],
  document_service: Annotated[DocumentService, Depends(get_document_service)],
  message_center_service: Annotated[MessageCenterService, Depends(get_message_center_service)],
  profile_service: Annotated[ProfileService, Depends(get_profile_service)],
  disposition: Annotated[Literal["inline", "attachment"], Query()] = "attachment",
) -> Response:
  attachment = await attachment_service.get_attachment_with_links(attachment_id=attachment_id)
  await assert_can_download_attachment(
    session=session,
    actor=actor,
    attachment=attachment,
    task_service=task_service,
    report_service=report_service,
    document_service=document_service,
    message_center_service=message_center_service,
    profile_service=profile_service,
  )
  content = await attachment_service.read_attachment_bytes(attachment=attachment)
  header_disposition = "inline" if disposition == "inline" else "attachment"
  return Response(
    content=content,
    media_type=attachment.mime_type,
    headers={
      "Content-Disposition": build_content_disposition(
        disposition=header_disposition,
        filename=attachment.original_filename,
      ),
      "Cache-Control": "private, no-store",
    },
  )


@router.delete("/{attachment_id}", response_model=AttachmentRead)
async def delete_attachment(
  attachment_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  attachment_service: Annotated[AttachmentService, Depends(get_attachment_service)],
  object_storage_service: Annotated[ObjectStorageService, Depends(get_object_storage_service)],
) -> AttachmentRead:
  attachment = await attachment_service.delete_attachment(
    actor=actor,
    attachment_id=attachment_id,
  )
  return await serialize_attachment_read(attachment, object_storage_service)
