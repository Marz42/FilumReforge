from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_knowledge_retrieval_service
from app.models import User
from app.schemas.documents import DocumentSearchHitRead
from app.schemas.knowledge import KnowledgeQueryRequest, KnowledgeQueryResponse
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService

router = APIRouter(prefix="/knowledge")


@router.post("/query", response_model=KnowledgeQueryResponse)
async def query_knowledge(
  payload: KnowledgeQueryRequest,
  actor: Annotated[User, Depends(get_current_user)],
  retrieval_service: Annotated[
    KnowledgeRetrievalService,
    Depends(get_knowledge_retrieval_service),
  ],
) -> KnowledgeQueryResponse:
  context, hits = await retrieval_service.build_rag_context(
    actor=actor,
    query=payload.query,
    category=payload.category,
    limit=payload.limit,
  )
  return KnowledgeQueryResponse(
    query=payload.query,
    context=context,
    hits=[
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
      for hit in hits
    ],
  )
