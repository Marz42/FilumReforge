from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_llm_router_service
from app.models import User
from app.schemas.ai_router import AIRouterRequest, AIRouterResponse
from app.schemas.documents import DocumentSearchHitRead
from app.services.llm_router_service import LLMRouterService

router = APIRouter(prefix="/ai")


@router.post("/router", response_model=AIRouterResponse)
async def route_ai_command(
  payload: AIRouterRequest,
  actor: Annotated[User, Depends(get_current_user)],
  llm_router_service: Annotated[LLMRouterService, Depends(get_llm_router_service)],
) -> AIRouterResponse:
  result = await llm_router_service.route_text(actor=actor, text=payload.text)
  return AIRouterResponse(
    mode=result.mode,
    prompt=result.prompt,
    reply_text=result.reply_text,
    command_name=result.command_name,
    tool_results=result.tool_results,
    knowledge_hits=[
      DocumentSearchHitRead(
        document_id=hit.document.id,
        title=hit.document.title,
        slug=hit.document.slug,
        category=hit.document.category,
        status=hit.document.status,
        score=round(hit.score, 4),
        chunk_index=hit.chunk_index,
        excerpt=hit.chunk_text[:240],
      )
      for hit in (result.knowledge_hits or [])
    ],
  )
