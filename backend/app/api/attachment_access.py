from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AttachmentTargetType, UserRole
from app.core.exceptions import AuthorizationError, NotFoundError
from app.models import Attachment, TaskComment, User
from app.services.document_service import DocumentService
from app.services.message_center_service import MessageCenterService
from app.services.profile_service import ProfileService
from app.services.report_service import ReportService
from app.services.task_service import TaskService


async def assert_can_download_attachment(
  *,
  session: AsyncSession,
  actor: User,
  attachment: Attachment,
  task_service: TaskService,
  report_service: ReportService,
  document_service: DocumentService,
  message_center_service: MessageCenterService,
  profile_service: ProfileService,
) -> None:
  if actor.role in {UserRole.ADMIN, UserRole.HR} or attachment.uploader_id == actor.id:
    return

  if not attachment.links:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在。")

  for link in attachment.links:
    try:
      if link.target_type == AttachmentTargetType.TASK:
        await task_service.get_task(actor=actor, task_id=link.target_id)
        return
      if link.target_type == AttachmentTargetType.TASK_COMMENT:
        comment = await session.get(TaskComment, link.target_id)
        if comment is None:
          continue
        await task_service.get_task(actor=actor, task_id=comment.task_id)
        return
      if link.target_type == AttachmentTargetType.REPORT:
        await report_service.get_report(actor=actor, report_id=link.target_id)
        return
      if link.target_type == AttachmentTargetType.DOCUMENT:
        await document_service.get_document(actor=actor, document_id=link.target_id)
        return
      if link.target_type == AttachmentTargetType.NOTIFICATION_MESSAGE:
        await message_center_service.get_message(actor=actor, message_id=link.target_id)
        return
      if link.target_type == AttachmentTargetType.PROFILE:
        await profile_service.get_profile(actor=actor, user_id=link.target_id)
        return
    except (NotFoundError, AuthorizationError):
      continue

  raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在。")
