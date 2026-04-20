from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.documents import DocumentSearchHitRead


class AIRouterRequest(BaseModel):
  text: str = Field(min_length=1, max_length=2000)


class AIRouterResponse(BaseModel):
  mode: str
  prompt: str
  reply_text: str
  command_name: str | None = None
  tool_results: list[dict[str, Any]] = Field(default_factory=list)
  knowledge_hits: list[DocumentSearchHitRead] = Field(default_factory=list)
