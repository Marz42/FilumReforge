from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.enums import DocumentCategory
from app.schemas.documents import DocumentSearchHitRead


class KnowledgeQueryRequest(BaseModel):
  query: str = Field(min_length=1, max_length=500)
  category: DocumentCategory | None = None
  limit: int = Field(default=4, ge=1, le=10)


class KnowledgeQueryResponse(BaseModel):
  query: str
  context: str
  hits: list[DocumentSearchHitRead] = Field(default_factory=list)
