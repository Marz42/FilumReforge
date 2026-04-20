from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.enums import DocumentCategory, DocumentStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.integrations.llm.openai_client import OpenAIClient
from app.models import Document, DocumentEmbedding, User
from app.services.access_control import MANAGEMENT_ROLES, ensure_active_user

DEFAULT_CHUNK_SIZE = 900
DEFAULT_CHUNK_OVERLAP = 120


@dataclass(slots=True)
class KnowledgeSearchHit:
  document: Document
  chunk_index: int
  chunk_text: str
  score: float


class KnowledgeRetrievalService:
  def __init__(
    self,
    session: AsyncSession,
    settings: Settings,
    openai_client: OpenAIClient | Any,
  ) -> None:
    self._session = session
    self._settings = settings
    self._openai_client = openai_client

  @staticmethod
  def chunk_markdown(
    content_md: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
  ) -> list[str]:
    normalized = content_md.strip()
    if not normalized:
      return []

    paragraphs = [paragraph.strip() for paragraph in normalized.split("\n\n") if paragraph.strip()]
    chunks: list[str] = []
    current_chunk = ""

    def flush_current_chunk() -> None:
      nonlocal current_chunk
      if current_chunk:
        chunks.append(current_chunk)
        current_chunk = ""

    for paragraph in paragraphs:
      candidate = f"{current_chunk}\n\n{paragraph}" if current_chunk else paragraph
      if len(candidate) <= chunk_size:
        current_chunk = candidate
        continue

      flush_current_chunk()
      if len(paragraph) <= chunk_size:
        current_chunk = paragraph
        continue

      step = max(chunk_size - overlap, 1)
      for start in range(0, len(paragraph), step):
        piece = paragraph[start : start + chunk_size].strip()
        if piece:
          chunks.append(piece)

    flush_current_chunk()
    return chunks or [normalized]

  async def rebuild_document_embeddings(self, *, document_id: UUID) -> list[DocumentEmbedding]:
    document = await self._session.scalar(
      select(Document).options(selectinload(Document.author)).where(Document.id == document_id)
    )
    if document is None:
      raise NotFoundError("文档不存在。")

    chunks = self.chunk_markdown(document.content_md) or [document.title]
    embeddings = await self._openai_client.create_embeddings(inputs=chunks)
    if len(embeddings) != len(chunks):
      raise ConflictError("embedding 返回数量与切块数量不一致。")

    await self._session.execute(
      delete(DocumentEmbedding).where(DocumentEmbedding.document_id == document.id)
    )

    stored_embeddings: list[DocumentEmbedding] = []
    for index, (chunk_text, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
      stored_embeddings.append(
        DocumentEmbedding(
          document_id=document.id,
          chunk_index=index,
          chunk_text=chunk_text,
          token_count=len(chunk_text.split()),
          embedding_model=self._settings.openai_embedding_model,
          embedding=list(embedding),
        )
      )
    self._session.add_all(stored_embeddings)
    await self._session.commit()
    return list(
      await self._session.scalars(
        select(DocumentEmbedding)
        .where(DocumentEmbedding.document_id == document.id)
        .order_by(DocumentEmbedding.chunk_index.asc())
      )
    )

  async def search_documents(
    self,
    *,
    actor: User,
    query: str,
    category: DocumentCategory | None = None,
    limit: int = 5,
  ) -> list[KnowledgeSearchHit]:
    ensure_active_user(actor)

    normalized_query = query.strip()
    if not normalized_query:
      raise ConflictError("检索内容不能为空。")

    query_embedding = (await self._openai_client.create_embeddings(inputs=[normalized_query]))[0]
    dialect_name = self._session.bind.dialect.name if self._session.bind is not None else ""
    if dialect_name == "postgresql":
      hits = await self._search_documents_postgresql(
        actor=actor,
        query_embedding=query_embedding,
        category=category,
        limit=limit,
      )
    else:
      hits = await self._search_documents_python(
        actor=actor,
        query_embedding=query_embedding,
        category=category,
      )

    return hits[:limit]

  async def build_rag_context(
    self,
    *,
    actor: User,
    query: str,
    category: DocumentCategory | None = None,
    limit: int = 4,
  ) -> tuple[str, list[KnowledgeSearchHit]]:
    hits = await self.search_documents(actor=actor, query=query, category=category, limit=limit)
    context = "\n\n".join(
      [
        f"[{hit.document.title}] slug={hit.document.slug}\n{hit.chunk_text}"
        for hit in hits
      ]
    )
    return context, hits

  async def _search_documents_postgresql(
    self,
    *,
    actor: User,
    query_embedding: list[float],
    category: DocumentCategory | None,
    limit: int,
  ) -> list[KnowledgeSearchHit]:
    distance = DocumentEmbedding.embedding.cosine_distance(query_embedding).label("distance")
    statement = (
      select(DocumentEmbedding, distance)
      .join(DocumentEmbedding.document)
      .options(selectinload(DocumentEmbedding.document).selectinload(Document.author))
    )
    if category is not None:
      statement = statement.where(Document.category == category)
    if actor.role not in MANAGEMENT_ROLES:
      statement = statement.where(Document.status == DocumentStatus.PUBLISHED)
    statement = statement.order_by(distance.asc()).limit(max(limit * 4, limit))

    grouped_hits: dict[UUID, KnowledgeSearchHit] = {}
    result = await self._session.execute(statement)
    for embedding, distance_value in result.all():
      score = 1 - float(distance_value)
      existing_hit = grouped_hits.get(embedding.document_id)
      if existing_hit is None or score > existing_hit.score:
        grouped_hits[embedding.document_id] = KnowledgeSearchHit(
          document=embedding.document,
          chunk_index=embedding.chunk_index,
          chunk_text=embedding.chunk_text,
          score=score,
        )

    return sorted(grouped_hits.values(), key=lambda hit: hit.score, reverse=True)

  async def _search_documents_python(
    self,
    *,
    actor: User,
    query_embedding: list[float],
    category: DocumentCategory | None,
  ) -> list[KnowledgeSearchHit]:
    statement = (
      select(DocumentEmbedding)
      .join(DocumentEmbedding.document)
      .options(selectinload(DocumentEmbedding.document).selectinload(Document.author))
    )
    if category is not None:
      statement = statement.where(Document.category == category)
    if actor.role not in MANAGEMENT_ROLES:
      statement = statement.where(Document.status == DocumentStatus.PUBLISHED)

    grouped_hits: dict[UUID, KnowledgeSearchHit] = {}
    embeddings = list(await self._session.scalars(statement))
    for embedding in embeddings:
      score = self._cosine_similarity(query_embedding, embedding.embedding)
      existing_hit = grouped_hits.get(embedding.document_id)
      if existing_hit is None or score > existing_hit.score:
        grouped_hits[embedding.document_id] = KnowledgeSearchHit(
          document=embedding.document,
          chunk_index=embedding.chunk_index,
          chunk_text=embedding.chunk_text,
          score=score,
        )

    return sorted(grouped_hits.values(), key=lambda hit: hit.score, reverse=True)

  @staticmethod
  def _cosine_similarity(left: list[float], right: Any) -> float:
    right_values = list(right)
    if not left or not right_values or len(left) != len(right_values):
      return 0.0

    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right_values, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right_values))
    if left_norm == 0 or right_norm == 0:
      return 0.0
    return dot_product / (left_norm * right_norm)
