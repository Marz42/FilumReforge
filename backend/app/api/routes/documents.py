from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
  get_current_user,
  get_document_service,
  get_job_queue_publisher,
  get_knowledge_retrieval_service,
  get_management_user,
  get_object_storage_service,
)
from app.core.enums import AttachmentStatus, DocumentCategory, DocumentStatus
from app.integrations.notifications.queue import JobQueuePublisher
from app.models import Attachment, User
from app.schemas.attachments import AttachmentRead
from app.schemas.documents import (
  DocumentCreateRequest,
  DocumentRead,
  DocumentSearchHitRead,
  DocumentSearchResponse,
  DocumentSummaryRead,
  DocumentUpdateRequest,
)
from app.services.document_service import DocumentService
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.object_storage_service import ObjectStorageService
from app.workers.arq_worker import REBUILD_DOCUMENT_EMBEDDINGS_JOB

router = APIRouter(prefix="/documents")


async def _build_attachment_read(
  attachment: Attachment,
  object_storage_service: ObjectStorageService,
) -> AttachmentRead:
  from app.api.attachment_serializers import serialize_attachment_read

  return await serialize_attachment_read(attachment, object_storage_service)


def _build_document_summary(document) -> DocumentSummaryRead:  # noqa: ANN001
  return DocumentSummaryRead.model_validate(document).model_copy(
    update={"author_email": document.author.email if document.author is not None else None}
  )


async def _build_document_read(
  *,
  actor: User,
  document,
  document_service: DocumentService,
  object_storage_service: ObjectStorageService,
) -> DocumentRead:  # noqa: ANN001
  attachments = [
    await _build_attachment_read(attachment, object_storage_service)
    for attachment in await document_service.list_document_attachments(
      actor=actor,
      document_id=document.id,
    )
  ]
  return DocumentRead.model_validate(document).model_copy(
    update={
      "author_email": document.author.email if document.author is not None else None,
      "attachments": attachments,
    }
  )


async def _enqueue_embedding_rebuild(
  *,
  job_queue_publisher: JobQueuePublisher,
  document_id: UUID,
) -> None:
  await job_queue_publisher.enqueue(REBUILD_DOCUMENT_EMBEDDINGS_JOB, str(document_id))


@router.get("", response_model=list[DocumentSummaryRead])
async def list_documents(
  actor: Annotated[User, Depends(get_current_user)],
  document_service: Annotated[DocumentService, Depends(get_document_service)],
  category: DocumentCategory | None = None,
  status: DocumentStatus | None = None,
  query: str | None = None,
) -> list[DocumentSummaryRead]:
  documents = await document_service.list_documents(
    actor=actor,
    category=category,
    status=status,
    query=query,
  )
  return [_build_document_summary(document) for document in documents]


@router.get("/search", response_model=DocumentSearchResponse)
async def search_documents(
  actor: Annotated[User, Depends(get_current_user)],
  retrieval_service: Annotated[
    KnowledgeRetrievalService,
    Depends(get_knowledge_retrieval_service),
  ],
  query: str = Query(min_length=1, max_length=500),
  category: DocumentCategory | None = None,
  limit: int = Query(default=5, ge=1, le=10),
) -> DocumentSearchResponse:
  hits = await retrieval_service.search_documents(
    actor=actor,
    query=query,
    category=category,
    limit=limit,
  )
  return DocumentSearchResponse(
    query=query,
    items=[
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


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def create_document(
  payload: DocumentCreateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  document_service: Annotated[DocumentService, Depends(get_document_service)],
  object_storage_service: Annotated[ObjectStorageService, Depends(get_object_storage_service)],
  job_queue_publisher: Annotated[JobQueuePublisher, Depends(get_job_queue_publisher)],
) -> DocumentRead:
  document = await document_service.create_document(
    actor=actor,
    title=payload.title,
    slug=payload.slug,
    category=payload.category,
    content_md=payload.content_md,
    status=payload.status,
  )
  await _enqueue_embedding_rebuild(
    job_queue_publisher=job_queue_publisher,
    document_id=document.id,
  )
  return await _build_document_read(
    actor=actor,
    document=document,
    document_service=document_service,
    object_storage_service=object_storage_service,
  )


@router.get("/{document_id}", response_model=DocumentRead)
async def read_document(
  document_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  document_service: Annotated[DocumentService, Depends(get_document_service)],
  object_storage_service: Annotated[ObjectStorageService, Depends(get_object_storage_service)],
) -> DocumentRead:
  document = await document_service.get_document(actor=actor, document_id=document_id)
  return await _build_document_read(
    actor=actor,
    document=document,
    document_service=document_service,
    object_storage_service=object_storage_service,
  )


@router.patch("/{document_id}", response_model=DocumentRead)
async def update_document(
  document_id: UUID,
  payload: DocumentUpdateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  document_service: Annotated[DocumentService, Depends(get_document_service)],
  object_storage_service: Annotated[ObjectStorageService, Depends(get_object_storage_service)],
  job_queue_publisher: Annotated[JobQueuePublisher, Depends(get_job_queue_publisher)],
) -> DocumentRead:
  document = await document_service.update_document(
    actor=actor,
    document_id=document_id,
    title=payload.title,
    slug=payload.slug,
    category=payload.category,
    content_md=payload.content_md,
  )
  await _enqueue_embedding_rebuild(
    job_queue_publisher=job_queue_publisher,
    document_id=document.id,
  )
  return await _build_document_read(
    actor=actor,
    document=document,
    document_service=document_service,
    object_storage_service=object_storage_service,
  )


@router.post("/{document_id}/publish", response_model=DocumentRead)
async def publish_document(
  document_id: UUID,
  actor: Annotated[User, Depends(get_management_user)],
  document_service: Annotated[DocumentService, Depends(get_document_service)],
  object_storage_service: Annotated[ObjectStorageService, Depends(get_object_storage_service)],
  job_queue_publisher: Annotated[JobQueuePublisher, Depends(get_job_queue_publisher)],
) -> DocumentRead:
  document = await document_service.publish_document(actor=actor, document_id=document_id)
  await _enqueue_embedding_rebuild(
    job_queue_publisher=job_queue_publisher,
    document_id=document.id,
  )
  return await _build_document_read(
    actor=actor,
    document=document,
    document_service=document_service,
    object_storage_service=object_storage_service,
  )


@router.post("/{document_id}/archive", response_model=DocumentRead)
async def archive_document(
  document_id: UUID,
  actor: Annotated[User, Depends(get_management_user)],
  document_service: Annotated[DocumentService, Depends(get_document_service)],
  object_storage_service: Annotated[ObjectStorageService, Depends(get_object_storage_service)],
) -> DocumentRead:
  document = await document_service.archive_document(actor=actor, document_id=document_id)
  return await _build_document_read(
    actor=actor,
    document=document,
    document_service=document_service,
    object_storage_service=object_storage_service,
  )


@router.get("/{document_id}/attachments", response_model=list[AttachmentRead])
async def list_document_attachments(
  document_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  document_service: Annotated[DocumentService, Depends(get_document_service)],
  object_storage_service: Annotated[ObjectStorageService, Depends(get_object_storage_service)],
) -> list[AttachmentRead]:
  attachments = await document_service.list_document_attachments(
    actor=actor,
    document_id=document_id,
  )
  return [
    await _build_attachment_read(attachment, object_storage_service)
    for attachment in attachments
  ]
