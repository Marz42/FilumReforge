from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import DEFAULT_USER_NOTIFICATION_CHANNELS, DepartmentCapability, UserRole, UserStatus
from app.core.exceptions import AuthorizationError, NotFoundError
from app.models import Announcement, AnnouncementArchive, Department, Profile, User
from app.schemas.messages import NotificationMessage
from app.services.notification_source import build_announcement_source_payload
from app.services.access_control import ensure_active_user
from app.services.notification_service import NotificationService


@dataclass(slots=True)
class AnnouncementScopeOption:
  id: UUID
  label: str


class AnnouncementService:
  def __init__(
    self,
    session: AsyncSession,
    notification_service: NotificationService | None = None,
  ) -> None:
    self._session = session
    self._notification_service = notification_service

  @staticmethod
  def _user_label(user: User) -> str:
    if user.profile is not None and user.profile.real_name:
      return user.profile.real_name
    return user.email

  async def _actor_department(self, *, actor: User) -> Department | None:
    actor_department_id = await self._session.scalar(select(Profile.department_id).where(Profile.user_id == actor.id))
    if actor_department_id is None:
      return None
    return await self._session.get(Department, actor_department_id)

  async def list_publish_scope_options(self, *, actor: User) -> list[AnnouncementScopeOption]:
    ensure_active_user(actor)
    if actor.role == UserRole.ADMIN:
      departments = list(
        await self._session.scalars(
          select(Department).where(Department.is_active.is_(True)).order_by(Department.sort_order.asc(), Department.name.asc())
        )
      )
      return [AnnouncementScopeOption(id=department.id, label=department.name) for department in departments]

    actor_department = await self._actor_department(actor=actor)
    if actor_department is None:
      return []

    capabilities = set(actor_department.capabilities)
    if DepartmentCapability.PUBLISH_ANNOUNCEMENT.value not in capabilities:
      return []
    return [AnnouncementScopeOption(id=actor_department.id, label=actor_department.name)]

  async def can_publish_announcement(self, *, actor: User) -> bool:
    return bool(await self.list_publish_scope_options(actor=actor))

  async def list_active_announcements(self, *, actor: User) -> list[Announcement]:
    ensure_active_user(actor)
    return list(
      await self._session.scalars(
        select(Announcement)
        .options(
          selectinload(Announcement.author).selectinload(User.profile),
          selectinload(Announcement.publisher_department),
        )
        .order_by(Announcement.published_at.desc(), Announcement.created_at.desc())
      )
    )

  async def list_archives(self, *, actor: User) -> list[AnnouncementArchive]:
    ensure_active_user(actor)
    return list(
      await self._session.scalars(
        select(AnnouncementArchive)
        .options(
          selectinload(AnnouncementArchive.author).selectinload(User.profile),
          selectinload(AnnouncementArchive.publisher_department),
        )
        .order_by(AnnouncementArchive.archived_at.desc())
      )
    )

  async def create_announcement(
    self,
    *,
    actor: User,
    publisher_department_id: UUID,
    title: str,
    content_md: str,
  ) -> Announcement:
    ensure_active_user(actor)
    options = await self.list_publish_scope_options(actor=actor)
    allowed_scope_ids = {option.id for option in options}
    if publisher_department_id not in allowed_scope_ids:
      raise AuthorizationError("当前账号不能以该部门名义发布公告。")

    department = await self._session.get(Department, publisher_department_id)
    if department is None:
      raise NotFoundError("公告发布部门不存在。")

    announcement = Announcement(
      publisher_department_id=publisher_department_id,
      author_user_id=actor.id,
      title=title.strip(),
      content_md=content_md.strip(),
      published_at=datetime.now(UTC),
    )
    self._session.add(announcement)
    await self._session.commit()
    await self._session.refresh(announcement)

    if self._notification_service is not None:
      recipients = list(
        await self._session.scalars(
          select(User).where(User.status == UserStatus.ACTIVE, User.id != actor.id).order_by(User.created_at.asc())
        )
      )
      for recipient in recipients:
        await self._notification_service.send(
          NotificationMessage(
            source_type="announcement",
            source_id=announcement.id,
            recipient_user_id=recipient.id,
            recipient_email=recipient.email,
            message_type="company_announcement",
            title=f"新公告：{announcement.title}",
            body_text=f"{department.name} 发布了新公告「{announcement.title}」。",
            channels=list(DEFAULT_USER_NOTIFICATION_CHANNELS),
            payload=build_announcement_source_payload(
              announcement_id=announcement.id,
              announcement_title=announcement.title,
              extra_payload={
              "announcement_id": str(announcement.id),
              "publisher_department_id": str(department.id),
              },
            ),
          )
        )

    return await self._session.scalar(
      select(Announcement)
      .options(
        selectinload(Announcement.author).selectinload(User.profile),
        selectinload(Announcement.publisher_department),
      )
      .where(Announcement.id == announcement.id)
    )

  async def withdraw_announcement(self, *, actor: User, announcement_id: UUID) -> None:
    ensure_active_user(actor)
    announcement = await self._session.scalar(
      select(Announcement)
      .options(selectinload(Announcement.publisher_department))
      .where(Announcement.id == announcement_id)
    )
    if announcement is None:
      raise NotFoundError("公告不存在。")

    actor_department = await self._actor_department(actor=actor)
    can_withdraw = actor.role == UserRole.ADMIN or (
      actor_department is not None
      and actor_department.id == announcement.publisher_department_id
      and DepartmentCapability.PUBLISH_ANNOUNCEMENT.value in set(actor_department.capabilities)
    )
    if not can_withdraw:
      raise AuthorizationError("当前账号不能撤下该公告。")

    self._session.add(
      AnnouncementArchive(
        original_announcement_id=announcement.id,
        publisher_department_id=announcement.publisher_department_id,
        author_user_id=announcement.author_user_id,
        title=announcement.title,
        content_md=announcement.content_md,
        published_at=announcement.published_at,
        archived_at=datetime.now(UTC),
      )
    )
    await self._session.execute(
      delete(Announcement).where(Announcement.id == announcement.id)
    )
    await self._session.commit()
