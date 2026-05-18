from __future__ import annotations

import io
import zipfile
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

# MIME 白名单（归一化后存储；audio/x-wav 会映射为 audio/wav）
MIME_ALIAS: dict[str, str] = {
  "audio/x-wav": "audio/wav",
}

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

ALLOWED_ATTACHMENT_MIME_TYPES = frozenset(
  {
    "text/plain",
    "text/markdown",
    "application/pdf",
    DOCX_MIME,
    XLSX_MIME,
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "audio/mpeg",
    "audio/wav",
  }
)

TEXT_PLAIN_MARKDOWN_MIMES = frozenset({"text/plain", "text/markdown"})

# 文本类（含 docx）：10MB；音频：50MB；PDF / XLSX / 图片：25MB（与产品约定一致）
TEXT_CLASS_MAX_BYTES = 10 * 1024 * 1024
AUDIO_MAX_BYTES = 50 * 1024 * 1024
OTHER_BINARY_MAX_BYTES = 25 * 1024 * 1024


def _max_bytes_for_mime(mime: str) -> int:
  if mime in TEXT_PLAIN_MARKDOWN_MIMES or mime == DOCX_MIME:
    return TEXT_CLASS_MAX_BYTES
  if mime in {"audio/mpeg", "audio/wav"}:
    return AUDIO_MAX_BYTES
  return OTHER_BINARY_MAX_BYTES


def _normalize_declared_mime(content_type: str) -> str:
  raw = content_type.split(";", 1)[0].strip().lower()
  return MIME_ALIAS.get(raw, raw)


def _is_valid_ooxml_zip(content: bytes, *, require_word: bool) -> bool:
  if not content or len(content) < 4 or content[:2] != b"PK":
    return False
  try:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
      names = set(zf.namelist())
  except zipfile.BadZipFile:
    return False
  if require_word:
    return "word/document.xml" in names
  return "xl/workbook.xml" in names


def _is_valid_wav(content: bytes) -> bool:
  return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WAVE"


def _is_valid_mp3(content: bytes) -> bool:
  if len(content) < 3:
    return False
  if content[:3] == b"ID3":
    return True
  return content[0] == 0xFF and (content[1] & 0xE0) == 0xE0


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
    normalized_content_type = _normalize_declared_mime(content_type)
    if not normalized_content_type:
      raise AppValidationError("附件必须声明 MIME 类型。")
    if normalized_content_type not in ALLOWED_ATTACHMENT_MIME_TYPES:
      raise AppValidationError(
        f"不支持的附件类型：{normalized_content_type}。"
        " 仅支持图片、PDF、Excel（.xlsx）、纯文本（.txt/.md）、Word（.docx）与音频（.mp3/.wav）。"
      )
    if not content:
      raise AppValidationError("附件内容不能为空。")

    max_bytes = _max_bytes_for_mime(normalized_content_type)
    if len(content) > max_bytes:
      label = "10MB" if max_bytes == TEXT_CLASS_MAX_BYTES else "50MB" if max_bytes == AUDIO_MAX_BYTES else "25MB"
      raise AppValidationError(f"附件超过允许大小（本类型上限 {label}），当前约 {len(content) // (1024 * 1024)}MB。")

    if normalized_content_type in TEXT_PLAIN_MARKDOWN_MIMES:
      if b"\x00" in content:
        raise AppValidationError("文本附件包含无效的二进制内容。")
      try:
        content.decode("utf-8")
      except UnicodeDecodeError as exc:
        raise AppValidationError("文本附件必须使用 UTF-8 编码。") from exc
      return normalized_content_type

    if normalized_content_type == DOCX_MIME:
      if not _is_valid_ooxml_zip(content, require_word=True):
        raise AppValidationError("Word 附件内容与类型不匹配（需为有效的 .docx / OOXML）。")
      return normalized_content_type

    if normalized_content_type == XLSX_MIME:
      if not _is_valid_ooxml_zip(content, require_word=False):
        raise AppValidationError("Excel 附件内容与类型不匹配（需为有效的 .xlsx / OOXML）。")
      return normalized_content_type

    if normalized_content_type == "audio/wav":
      if not _is_valid_wav(content):
        raise AppValidationError("WAV 附件内容与声明类型不匹配。")
      return normalized_content_type

    if normalized_content_type == "audio/mpeg":
      if not _is_valid_mp3(content):
        raise AppValidationError("MP3 附件内容与声明类型不匹配。")
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
    bypass_uploader_filter: bool = False,
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
        statement.join(Attachment.links).where(
          AttachmentLink.target_type == target_type,
          AttachmentLink.target_id == target_id,
        )
      )
    if not bypass_uploader_filter and actor.role not in {UserRole.ADMIN, UserRole.HR}:
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
