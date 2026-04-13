from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import AttachmentStatus, AttachmentTargetType, AttachmentVisibility, UserRole
from app.core.exceptions import NotFoundError
from app.models import Attachment, AttachmentLink, User
from app.services.access_control import ensure_active_user
from app.services.object_storage_service import ObjectStorageService


class AttachmentService:
  def __init__(self, session: AsyncSession, object_storage_service: ObjectStorageService) -> None:
    self._session = session
    self._object_storage_service = object_storage_service

  async def upload_attachment(
    self,
    *,
    actor: User,
    filename: str,
    content_type: str,
    content: bytes,
    visibility: AttachmentVisibility = AttachmentVisibility.PRIVATE,
    target_type: AttachmentTargetType | None = None,
    target_id: UUID | None = None,
    relation: str = "primary",
  ) -> Attachment:
    ensure_active_user(actor)

    safe_name = Path(filename).name.replace(" ", "_")
    object_key = f"{uuid4().hex}/{safe_name}"
    descriptor = await self._object_storage_service.upload(
      object_key=object_key,
      content=content,
      content_type=content_type,
    )

    attachment = Attachment(
      storage_provider=descriptor.storage_provider,
      bucket=descriptor.bucket,
      object_key=descriptor.object_key,
      original_filename=safe_name,
      mime_type=content_type,
      size_bytes=len(content),
      checksum_sha256=sha256(content).hexdigest(),
      uploader_id=actor.id,
      visibility=visibility,
    )
    self._session.add(attachment)
    await self._session.flush()

    if target_type is not None and target_id is not None:
      self._session.add(
        AttachmentLink(
          attachment_id=attachment.id,
          target_type=target_type,
          target_id=target_id,
          relation=relation,
          created_by=actor.id,
        )
      )

    await self._session.commit()
    await self._session.refresh(attachment)
    return attachment

  async def list_attachments(
    self,
    *,
    actor: User,
    target_type: AttachmentTargetType | None = None,
    target_id: UUID | None = None,
  ) -> list[Attachment]:
    ensure_active_user(actor)
    statement = (
      select(Attachment)
      .options(selectinload(Attachment.links))
      .where(Attachment.status != AttachmentStatus.DELETED)
      .order_by(Attachment.created_at.desc())
    )
    if target_type is not None and target_id is not None:
      statement = (
        statement.join(Attachment.links)
        .where(
          AttachmentLink.target_type == target_type,
          AttachmentLink.target_id == target_id,
        )
      )
    if actor.role not in {UserRole.ADMIN, UserRole.HR}:
      statement = statement.where(Attachment.uploader_id == actor.id)

    result = await self._session.scalars(statement)
    return list(result)

  async def delete_attachment(self, *, actor: User, attachment_id: UUID) -> Attachment:
    ensure_active_user(actor)

    attachment = await self._session.get(Attachment, attachment_id)
    if attachment is None:
      raise NotFoundError("附件不存在。")
    if actor.role not in {UserRole.ADMIN, UserRole.HR} and attachment.uploader_id != actor.id:
      raise NotFoundError("附件不存在。")

    await self._object_storage_service.delete(object_key=attachment.object_key)
    attachment.status = AttachmentStatus.DELETED
    attachment.deleted_at = datetime.now(UTC)
    await self._session.commit()
    await self._session.refresh(attachment)
    return attachment
