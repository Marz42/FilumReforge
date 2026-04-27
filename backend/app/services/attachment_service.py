from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import filetype
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import AttachmentStatus, AttachmentTargetType, AttachmentVisibility, UserRole
from app.core.exceptions import AppValidationError, NotFoundError
from app.models import Attachment, AttachmentLink, User
from app.services.access_control import ensure_active_user
from app.services.object_storage_service import ObjectStorageService

ALLOWED_ATTACHMENT_MIME_TYPES = frozenset(
  {
    "text/plain",
    "text/markdown",
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
  }
)
TEXT_ATTACHMENT_MIME_TYPES = frozenset({"text/plain", "text/markdown"})


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
    validated_content_type = self._validate_attachment_content(
      filename=filename,
      content_type=content_type,
      content=content,
    )

    safe_name = Path(filename).name.replace(" ", "_")
    object_key = f"{uuid4().hex}/{safe_name}"
    descriptor = await self._object_storage_service.upload(
      object_key=object_key,
      content=content,
      content_type=validated_content_type,
    )

    attachment = Attachment(
      storage_provider=descriptor.storage_provider,
      bucket=descriptor.bucket,
      object_key=descriptor.object_key,
      original_filename=safe_name,
      mime_type=validated_content_type,
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

  @staticmethod
  def _validate_attachment_content(*, filename: str, content_type: str, content: bytes) -> str:
    normalized_content_type = content_type.split(";", 1)[0].strip().lower()
    if not normalized_content_type:
      raise AppValidationError("附件必须声明 MIME 类型。")
    if normalized_content_type not in ALLOWED_ATTACHMENT_MIME_TYPES:
      raise AppValidationError(f"不支持的附件类型：{normalized_content_type}。")
    if not content:
      raise AppValidationError("附件内容不能为空。")

    if normalized_content_type in TEXT_ATTACHMENT_MIME_TYPES:
      if b"\x00" in content:
        raise AppValidationError("文本附件包含无效的二进制内容。")
      try:
        content.decode("utf-8")
      except UnicodeDecodeError as exc:
        raise AppValidationError("文本附件必须使用 UTF-8 编码。") from exc
      return normalized_content_type

    kind = filetype.guess(content)
    if kind is None or kind.mime != normalized_content_type:
      raise AppValidationError(
        f"附件内容与声明类型不匹配：filename={Path(filename).suffix or '<none>'} content_type={normalized_content_type}。"
      )
    return normalized_content_type

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
