from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import AttachmentStatus, AttachmentVisibility


class AttachmentRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  original_filename: str
  mime_type: str
  size_bytes: int
  checksum_sha256: str
  uploader_id: UUID
  visibility: AttachmentVisibility
  status: AttachmentStatus
  deleted_at: datetime | None
  created_at: datetime
  download_url: str | None = None
