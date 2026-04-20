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
  notification_receipts = relationship("NotificationReceipt", back_populates="user")
  authored_documents = relationship(
    "Document",
    back_populates="author",
    foreign_keys="Document.author_id",
  )
  push_subscriptions = relationship(
    "PushSubscription",
    back_populates="user",
    cascade="all, delete-orphan",
    foreign_keys="PushSubscription.user_id",
  )
  position_assignments = relationship("ProfilePosition", back_populates="user")
  created_task_templates = relationship(
    "TaskTemplate",
    back_populates="creator",
    foreign_keys="TaskTemplate.created_by",
  )
  workflow_definitions_created = relationship(
    "WorkflowDefinition",
    back_populates="creator",
    foreign_keys="WorkflowDefinition.created_by",
  )
  workflow_instances_started = relationship(
    "WorkflowInstance",
    back_populates="initiator",
    foreign_keys="WorkflowInstance.initiator_user_id",
  )
  workflow_step_runs_assigned = relationship(
    "WorkflowStepRun",
    back_populates="assignee",
    foreign_keys="WorkflowStepRun.assignee_user_id",
  )
  workflow_step_runs_delegated = relationship(
    "WorkflowStepRun",
    back_populates="delegated_from",
    foreign_keys="WorkflowStepRun.delegated_from_user_id",
  )
  task_watches = relationship(
    "TaskWatcher",
    back_populates="user",
    foreign_keys="TaskWatcher.user_id",
  )
  created_task_watches = relationship(
    "TaskWatcher",
    back_populates="creator",
    foreign_keys="TaskWatcher.created_by",
  )
  task_schedules = relationship(
    "TaskSchedule",
    back_populates="owner",
    foreign_keys="TaskSchedule.owner_user_id",
  )
  reporting_lines = relationship(
    "ReportingLine",
    foreign_keys="ReportingLine.user_id",
    back_populates="user",
  )
  managed_reporting_lines = relationship(
    "ReportingLine",
    foreign_keys="ReportingLine.manager_user_id",
    back_populates="manager",
  )
  employment_events = relationship(
    "EmploymentEvent",
    foreign_keys="EmploymentEvent.user_id",
    back_populates="user",
  )
  created_employment_events = relationship(
    "EmploymentEvent",
    foreign_keys="EmploymentEvent.created_by",
    back_populates="creator",
  )
  delegations_granted = relationship(
    "Delegation",
    foreign_keys="Delegation.delegator_user_id",
    back_populates="delegator",
  )
  delegations_received = relationship(
    "Delegation",
    foreign_keys="Delegation.delegate_user_id",
    back_populates="delegate",
  )
  created_delegations = relationship(
    "Delegation",
    foreign_keys="Delegation.created_by",
    back_populates="creator",
  )
