from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.dependencies import (
  get_attachment_service,
  get_current_user,
  get_object_storage_service,
)
from app.core.enums import AttachmentTargetType, AttachmentVisibility
from app.models import Attachment, User
from app.schemas.attachments import AttachmentRead
from app.services.attachment_service import AttachmentService
from app.services.object_storage_service import ObjectStorageService

router = APIRouter(prefix="/attachments")


async def _build_attachment_read(
  attachment: Attachment,
  object_storage_service: ObjectStorageService,
) -> AttachmentRead:
  download_url = None
  if attachment.status.value != "deleted":
    download_url = await object_storage_service.generate_download_url(
      object_key=attachment.object_key
    )
  return AttachmentRead.model_validate(attachment).model_copy(update={"download_url": download_url})


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


@router.get("", response_model=list[AttachmentRead])
async def list_attachments(
  actor: Annotated[User, Depends(get_current_user)],
  attachment_service: Annotated[AttachmentService, Depends(get_attachment_service)],
  object_storage_service: Annotated[ObjectStorageService, Depends(get_object_storage_service)],
  target_type: AttachmentTargetType | None = None,
  target_id: UUID | None = None,
) -> list[AttachmentRead]:
  _validate_attachment_target(target_type=target_type, target_id=target_id)
  attachments = await attachment_service.list_attachments(
    actor=actor,
    target_type=target_type,
    target_id=target_id,
  )
  result: list[AttachmentRead] = []
  for attachment in attachments:
    result.append(await _build_attachment_read(attachment, object_storage_service))
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
  return await _build_attachment_read(attachment, object_storage_service)


@router.delete("/{attachment_id}", response_model=AttachmentRead)
async def delete_attachment(
  attachment_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  attachment_service: Annotated[AttachmentService, Depends(get_attachment_service)],
) -> AttachmentRead:
  attachment = await attachment_service.delete_attachment(
    actor=actor,
    attachment_id=attachment_id,
  )
  return AttachmentRead.model_validate(attachment)
