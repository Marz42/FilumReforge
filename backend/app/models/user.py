from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import build_enum
from app.core.enums import UserRole, UserStatus
from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "users"
  __table_args__ = (
    Index("idx_users_role_status", "role", "status"),
  )

  email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
  password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
  role: Mapped[UserRole] = mapped_column(build_enum(enum_cls=UserRole, name="user_role"), nullable=False)
  status: Mapped[UserStatus] = mapped_column(
    build_enum(enum_cls=UserStatus, name="user_status"),
    default=UserStatus.ACTIVE,
    nullable=False,
  )
  last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

  profile = relationship("Profile", back_populates="user", uselist=False)
  managed_departments = relationship("Department", back_populates="manager")
  created_tasks = relationship("Task", back_populates="creator", foreign_keys="Task.creator_id")
  assigned_tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assignee_id")
  task_comments = relationship("TaskComment", back_populates="user")
  operated_task_logs = relationship("TaskLog", back_populates="operator")
  uploaded_attachments = relationship("Attachment", back_populates="uploader")
  refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
  notification_messages = relationship("NotificationMessage", back_populates="recipient_user")
