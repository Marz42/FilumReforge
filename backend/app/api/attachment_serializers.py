from __future__ import annotations

from app.models import Attachment
from app.schemas.attachments import AttachmentRead
from app.services.object_storage_service import ObjectStorageService


async def serialize_attachment_read(
  attachment: Attachment,
  object_storage_service: ObjectStorageService,
) -> AttachmentRead:
  download_url = None
  if attachment.status.value != "deleted":
    download_url = await object_storage_service.generate_download_url(
      object_key=attachment.object_key
    )
  return AttachmentRead.model_validate(attachment).model_copy(update={"download_url": download_url})
