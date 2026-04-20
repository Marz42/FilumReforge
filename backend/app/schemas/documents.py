from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import DocumentCategory, DocumentStatus
from app.schemas.attachments import AttachmentRead


class DocumentSummaryRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  title: str
  slug: str
  category: DocumentCategory
  status: DocumentStatus
  author_id: UUID
  version: int
  published_at: datetime | None
  created_at: datetime
  updated_at: datetime
  author_email: str | None = None


class DocumentRead(DocumentSummaryRead):
  content_md: str
  attachments: list[AttachmentRead] = Field(default_factory=list)


class DocumentCreateRequest(BaseModel):
  title: str = Field(min_length=1, max_length=255)
  slug: str | None = Field(default=None, max_length=255)
  category: DocumentCategory
  content_md: str = Field(min_length=1)
  status: DocumentStatus = DocumentStatus.DRAFT


class DocumentUpdateRequest(BaseModel):
  title: str | None = Field(default=None, min_length=1, max_length=255)
  slug: str | None = Field(default=None, max_length=255)
  category: DocumentCategory | None = None
  content_md: str | None = Field(default=None, min_length=1)


class DocumentSearchHitRead(BaseModel):
  document_id: UUID
  title: str
  slug: str
  category: DocumentCategory
  status: DocumentStatus
  score: float
  chunk_index: int
  excerpt: str


class DocumentSearchResponse(BaseModel):
  query: str
  items: list[DocumentSearchHitRead] = Field(default_factory=list)


class DocumentEmbeddingStatusRead(BaseModel):
  document_id: UUID
  enqueued_job: str
  job_arguments: list[Any]
