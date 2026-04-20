from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import TaskPriority, TaskStatus


class OverviewScopeOptionRead(BaseModel):
  id: UUID | None
  label: str


class BoardCardRead(BaseModel):
  id: UUID
  scope_department_id: UUID | None
  scope_label: str
  author_user_id: UUID
  author_label: str
  title: str
  content_md: str
  expires_at: datetime
  created_at: datetime


class BoardCardCreateRequest(BaseModel):
  scope_department_id: UUID | None = None
  title: str = Field(min_length=1, max_length=120)
  content_md: str = Field(min_length=1, max_length=5000)


class AnnouncementRead(BaseModel):
  id: UUID
  publisher_department_id: UUID
  publisher_department_name: str
  author_user_id: UUID
  author_label: str
  title: str
  content_md: str
  published_at: datetime
  created_at: datetime


class AnnouncementCreateRequest(BaseModel):
  publisher_department_id: UUID
  title: str = Field(min_length=1, max_length=160)
  content_md: str = Field(min_length=1, max_length=8000)


class OverviewTaskInboxItemRead(BaseModel):
  task_id: UUID
  title: str
  priority: TaskPriority
  status: TaskStatus
  due_date: datetime | None
  department_name: str | None
  current_stage_label: str
  current_handler_label: str | None


class OverviewTaskTrackingItemRead(BaseModel):
  task_id: UUID
  title: str
  priority: TaskPriority
  status: TaskStatus
  due_date: datetime | None
  department_name: str | None
  relation_types: list[str] = Field(default_factory=list)
  current_stage_label: str
  current_handler_label: str | None


class OverviewPermissionsRead(BaseModel):
  board_scope_options: list[OverviewScopeOptionRead] = Field(default_factory=list)
  announcement_scope_options: list[OverviewScopeOptionRead] = Field(default_factory=list)
  can_publish_board: bool
  can_publish_announcement: bool


class OverviewRead(BaseModel):
  board_cards: list[BoardCardRead] = Field(default_factory=list)
  announcements: list[AnnouncementRead] = Field(default_factory=list)
  task_inbox: list[OverviewTaskInboxItemRead] = Field(default_factory=list)
  task_tracking: list[OverviewTaskTrackingItemRead] = Field(default_factory=list)
  permissions: OverviewPermissionsRead
