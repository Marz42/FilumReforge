from __future__ import annotations

from app.api.attachment_content import build_attachment_content_path
from app.core.enums import AttachmentStatus
from app.models import Attachment
from app.schemas.attachments import AttachmentRead
from app.services.object_storage_service import ObjectStorageService


async def serialize_attachment_read(
  attachment: Attachment,
  object_storage_service: ObjectStorageService | None = None,
) -> AttachmentRead:
  del object_storage_service
  download_url = None
  if attachment.status != AttachmentStatus.DELETED:
    download_url = build_attachment_content_path(attachment.id)
  return AttachmentRead.model_validate(attachment).model_copy(update={"download_url": download_url})
