from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services.announcement_service import AnnouncementService
from app.services.board_service import BoardService, ScopeOption
from app.services.notification_service import NotificationService
from app.services.task_service import TaskInboxEntry, TaskService, TaskTrackingEntry


@dataclass(slots=True)
class OverviewSnapshot:
  board_cards: list
  announcements: list
  task_inbox: list[TaskInboxEntry]
  task_tracking: list[TaskTrackingEntry]
  board_scope_options: list[ScopeOption]
  announcement_scope_options: list
  can_publish_announcement: bool


class OverviewService:
  def __init__(
    self,
    session: AsyncSession,
    notification_service: NotificationService | None = None,
  ) -> None:
    self._session = session
    self._notification_service = notification_service

  async def get_overview(self, *, actor: User) -> OverviewSnapshot:
    task_service = TaskService(self._session, self._notification_service)
    board_service = BoardService(self._session)
    announcement_service = AnnouncementService(self._session, self._notification_service)

    board_cards = await board_service.list_active_cards(actor=actor)
    announcements = await announcement_service.list_active_announcements(actor=actor)
    task_inbox = (await task_service.list_task_inbox(actor=actor)).items
    task_tracking = (await task_service.list_task_tracking(actor=actor)).items
    board_scope_options = await board_service.list_publish_scope_options(actor=actor)
    announcement_scope_options = await announcement_service.list_publish_scope_options(actor=actor)

    return OverviewSnapshot(
      board_cards=board_cards,
      announcements=announcements,
      task_inbox=task_inbox,
      task_tracking=task_tracking,
      board_scope_options=board_scope_options,
      announcement_scope_options=announcement_scope_options,
      can_publish_announcement=bool(announcement_scope_options),
    )
