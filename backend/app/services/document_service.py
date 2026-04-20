from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import AttachmentStatus, AttachmentTargetType, DocumentCategory, DocumentStatus
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models import Attachment, AttachmentLink, Document, User
from app.services.access_control import MANAGEMENT_ROLES, ensure_active_user


class DocumentService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  @staticmethod
  def _normalize_slug(raw_value: str) -> str:
    normalized = unicodedata.normalize("NFKC", raw_value).strip().lower()
    normalized = re.sub(r"[^\w-]+", "-", normalized)
    normalized = re.sub(r"[-_]{2,}", "-", normalized).strip("-_")
    return normalized

  def _statement(self, *, include_embeddings: bool = False):
    options = [selectinload(Document.author)]
    if include_embeddings:
      options.append(selectinload(Document.embeddings))
    return select(Document).options(*options)

  async def _get_document_for_management(self, *, document_id: UUID) -> Document:
    document = await self._session.scalar(
      self._statement(include_embeddings=True).where(Document.id == document_id)
    )
    if document is None:
      raise NotFoundError("文档不存在。")
    return document

  async def _get_document_or_raise(self, *, actor: User, document_id: UUID) -> Document:
    statement = self._statement(include_embeddings=True).where(Document.id == document_id)
    if actor.role not in MANAGEMENT_ROLES:
      statement = statement.where(Document.status == DocumentStatus.PUBLISHED)
    document = await self._session.scalar(statement)
    if document is None:
      raise NotFoundError("文档不存在。")
    return document

  async def list_documents(
    self,
    *,
    actor: User,
    category: DocumentCategory | None = None,
    status: DocumentStatus | None = None,
    query: str | None = None,
  ) -> list[Document]:
    ensure_active_user(actor)
    statement = self._statement().order_by(Document.updated_at.desc())

    if category is not None:
      statement = statement.where(Document.category == category)

    if actor.role not in MANAGEMENT_ROLES:
      if status is not None and status != DocumentStatus.PUBLISHED:
        raise AuthorizationError("当前账号不能查看未发布文档。")
      statement = statement.where(Document.status == DocumentStatus.PUBLISHED)
    elif status is not None:
      statement = statement.where(Document.status == status)

    if query:
      term = f"%{query.strip()}%"
      statement = statement.where(
        or_(
          Document.title.ilike(term),
          Document.slug.ilike(term),
          Document.content_md.ilike(term),
        )
      )

    return list(await self._session.scalars(statement))

  async def get_document(self, *, actor: User, document_id: UUID) -> Document:
    ensure_active_user(actor)
    return await self._get_document_or_raise(actor=actor, document_id=document_id)

  async def get_document_by_slug(self, *, actor: User, slug: str) -> Document:
    ensure_active_user(actor)
    normalized_slug = self._normalize_slug(slug)
    statement = self._statement(include_embeddings=True).where(Document.slug == normalized_slug)
    if actor.role not in MANAGEMENT_ROLES:
      statement = statement.where(Document.status == DocumentStatus.PUBLISHED)
    document = await self._session.scalar(statement)
    if document is None:
      raise NotFoundError("文档不存在。")
    return document

  async def create_document(
    self,
    *,
    actor: User,
    title: str,
    slug: str | None,
    category: DocumentCategory,
    content_md: str,
    status: DocumentStatus = DocumentStatus.DRAFT,
  ) -> Document:
    ensure_active_user(actor)
    if actor.role not in MANAGEMENT_ROLES:
      raise AuthorizationError("当前账号不能创建知识库文档。")

    normalized_title = title.strip()
    normalized_content = content_md.strip()
    normalized_slug = self._normalize_slug(slug or normalized_title)

    if not normalized_title:
      raise ConflictError("文档标题不能为空。")
    if not normalized_content:
      raise ConflictError("文档内容不能为空。")
    if not normalized_slug:
      raise ConflictError("文档 slug 不能为空。")
    if await self._session.scalar(select(Document.id).where(Document.slug == normalized_slug)) is not None:
      raise ConflictError("文档 slug 已存在。")

    document = Document(
      title=normalized_title,
      slug=normalized_slug,
      category=category,
      status=status,
      content_md=normalized_content,
      author_id=actor.id,
      version=1,
      published_at=datetime.now(UTC) if status == DocumentStatus.PUBLISHED else None,
    )
    self._session.add(document)
    await self._session.commit()
    return await self.get_document(actor=actor, document_id=document.id)

  async def update_document(
    self,
    *,
    actor: User,
    document_id: UUID,
    title: str | None = None,
    slug: str | None = None,
    category: DocumentCategory | None = None,
    content_md: str | None = None,
  ) -> Document:
    ensure_active_user(actor)
    if actor.role not in MANAGEMENT_ROLES:
      raise AuthorizationError("当前账号不能更新知识库文档。")

    document = await self._get_document_for_management(document_id=document_id)
    changed = False

    if title is not None:
      normalized_title = title.strip()
      if not normalized_title:
        raise ConflictError("文档标题不能为空。")
      if normalized_title != document.title:
        document.title = normalized_title
        changed = True

    if slug is not None:
      normalized_slug = self._normalize_slug(slug)
      if not normalized_slug:
        raise ConflictError("文档 slug 不能为空。")
      if normalized_slug != document.slug:
        existing_document_id = await self._session.scalar(
          select(Document.id).where(Document.slug == normalized_slug)
        )
        if existing_document_id is not None and existing_document_id != document.id:
          raise ConflictError("文档 slug 已存在。")
        document.slug = normalized_slug
        changed = True

    if category is not None and category != document.category:
      document.category = category
      changed = True

    if content_md is not None:
      normalized_content = content_md.strip()
      if not normalized_content:
        raise ConflictError("文档内容不能为空。")
      if normalized_content != document.content_md:
        document.content_md = normalized_content
        changed = True

    if changed:
      document.version += 1
      document.updated_at = datetime.now(UTC)

    await self._session.commit()
    return await self.get_document(actor=actor, document_id=document.id)

  async def publish_document(self, *, actor: User, document_id: UUID) -> Document:
    ensure_active_user(actor)
    if actor.role not in MANAGEMENT_ROLES:
      raise AuthorizationError("当前账号不能发布知识库文档。")

    document = await self._get_document_for_management(document_id=document_id)
    document.status = DocumentStatus.PUBLISHED
    document.published_at = datetime.now(UTC)
    await self._session.commit()
    return await self.get_document(actor=actor, document_id=document.id)

  async def archive_document(self, *, actor: User, document_id: UUID) -> Document:
    ensure_active_user(actor)
    if actor.role not in MANAGEMENT_ROLES:
      raise AuthorizationError("当前账号不能归档知识库文档。")

    document = await self._get_document_for_management(document_id=document_id)
    document.status = DocumentStatus.ARCHIVED
    await self._session.commit()
    return await self.get_document(actor=actor, document_id=document.id)

  async def list_document_attachments(
    self,
    *,
    actor: User,
    document_id: UUID,
  ) -> list[Attachment]:
    ensure_active_user(actor)
    await self._get_document_or_raise(actor=actor, document_id=document_id)
    return list(
      await self._session.scalars(
        select(Attachment)
        .join(Attachment.links)
        .where(
          Attachment.status != AttachmentStatus.DELETED,
          AttachmentLink.target_type == AttachmentTargetType.DOCUMENT,
          AttachmentLink.target_id == document_id,
        )
        .order_by(Attachment.created_at.asc())
      )
    )
