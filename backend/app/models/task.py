from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import build_enum, build_json_type
from app.core.enums import CommentFormat, TaskActionType, TaskPriority, TaskSourceType, TaskStatus
from app.models.base import Base
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "tasks"
  __table_args__ = (
    Index("idx_tasks_assignee_status", "assignee_id", "status"),
    Index("idx_tasks_department_status", "department_id", "status"),
    Index("idx_tasks_due_date", "due_date"),
    Index("idx_tasks_template_instance_id", "template_instance_id"),
    Index("idx_tasks_template_step_run_id", "template_step_run_id"),
  )

  title: Mapped[str] = mapped_column(String(255), nullable=False)
  description: Mapped[str | None] = mapped_column(Text, nullable=True)
  creator_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
  assignee_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
  department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
  status: Mapped[TaskStatus] = mapped_column(
    build_enum(enum_cls=TaskStatus, name="task_status"),
    default=TaskStatus.TODO,
    nullable=False,
  )
  priority: Mapped[TaskPriority] = mapped_column(
    build_enum(enum_cls=TaskPriority, name="task_priority"),
    default=TaskPriority.MEDIUM,
    nullable=False,
  )
  due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  parent_task_id: Mapped[UUID | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
  template_instance_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("task_template_instances.id", name="fk_tasks_template_instance", ondelete="SET NULL"),
    nullable=True,
  )
  template_step_run_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("task_template_step_runs.id", name="fk_tasks_template_step_run", ondelete="SET NULL"),
    nullable=True,
  )
  source_type: Mapped[TaskSourceType] = mapped_column(
    build_enum(enum_cls=TaskSourceType, name="task_source_type"),
    default=TaskSourceType.MANUAL,
    nullable=False,
  )
  extra_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", build_json_type(), default=dict, nullable=False)

  creator = relationship("User", back_populates="created_tasks", foreign_keys=[creator_id])
  assignee = relationship("User", back_populates="assigned_tasks", foreign_keys=[assignee_id])
  department = relationship("Department", back_populates="tasks")
  template_instance = relationship("TaskTemplateInstance", back_populates="tasks", foreign_keys=[template_instance_id])
  template_step_run = relationship("TaskTemplateStepRun", back_populates="task", foreign_keys=[template_step_run_id])
  parent_task = relationship("Task", remote_side="Task.id", back_populates="child_tasks")
  child_tasks = relationship("Task", back_populates="parent_task")
  dependencies = relationship(
    "TaskDependency",
    back_populates="task",
    foreign_keys="TaskDependency.task_id",
    cascade="all, delete-orphan",
  )
  blocked_by = relationship(
    "TaskDependency",
    back_populates="depends_on_task",
    foreign_keys="TaskDependency.depends_on_task_id",
    cascade="all, delete-orphan",
  )
  comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan")
  logs = relationship("TaskLog", back_populates="task", cascade="all, delete-orphan")
  watchers = relationship("TaskWatcher", back_populates="task", cascade="all, delete-orphan")
  memos = relationship("TaskMemo", back_populates="related_task")


class TaskDependency(Base):
  __tablename__ = "task_dependencies"
  __table_args__ = (
    CheckConstraint("task_id <> depends_on_task_id", name="task_dependencies_self_reference"),
    Index("idx_task_dependencies_depends_on_task_id", "depends_on_task_id"),
  )

  task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
  depends_on_task_id: Mapped[UUID] = mapped_column(
    ForeignKey("tasks.id", ondelete="CASCADE"),
    primary_key=True,
  )
  dependency_type: Mapped[str] = mapped_column(String(32), default="blocks", nullable=False)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

  task = relationship("Task", back_populates="dependencies", foreign_keys=[task_id])
  depends_on_task = relationship("Task", back_populates="blocked_by", foreign_keys=[depends_on_task_id])


class TaskLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
  __tablename__ = "task_logs"
  __table_args__ = (
    Index("idx_task_logs_task_id_created_at", "task_id", "created_at"),
    Index("idx_task_logs_operator_id", "operator_id"),
  )

  task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
  operator_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
  action_type: Mapped[TaskActionType] = mapped_column(
    build_enum(enum_cls=TaskActionType, name="task_action_type"),
    nullable=False,
  )
  from_status: Mapped[TaskStatus | None] = mapped_column(
    build_enum(enum_cls=TaskStatus, name="task_status"),
    nullable=True,
  )
  to_status: Mapped[TaskStatus | None] = mapped_column(
    build_enum(enum_cls=TaskStatus, name="task_status"),
    nullable=True,
  )
  detail: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)

  task = relationship("Task", back_populates="logs")
  operator = relationship("User", back_populates="operated_task_logs")


class TaskComment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "task_comments"
  __table_args__ = (
    CheckConstraint("length(trim(content)) > 0", name="task_comments_non_empty_content"),
    Index("idx_task_comments_task_id_created_at", "task_id", "created_at"),
    Index("idx_task_comments_user_id", "user_id"),
  )

  task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
  user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
  content: Mapped[str] = mapped_column(Text, nullable=False)
  content_format: Mapped[CommentFormat] = mapped_column(
    build_enum(enum_cls=CommentFormat, name="comment_format"),
    default=CommentFormat.MARKDOWN,
    nullable=False,
  )
  is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

  task = relationship("Task", back_populates="comments")
  user = relationship("User", back_populates="task_comments")


class TaskMemo(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "task_memos"
  __table_args__ = (
    CheckConstraint("length(trim(content)) > 0", name="task_memos_non_empty_content"),
    Index("idx_task_memos_owner_pinned_updated", "owner_user_id", "is_pinned", "updated_at"),
    Index("idx_task_memos_related_task", "related_task_id"),
  )

  owner_user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_task_memos_owner", ondelete="CASCADE"),
    nullable=False,
  )
  related_task_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("tasks.id", name="fk_task_memos_related_task", ondelete="SET NULL"),
    nullable=True,
  )
  title: Mapped[str | None] = mapped_column(String(200), nullable=True)
  content: Mapped[str] = mapped_column(Text, nullable=False)
  is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

  owner = relationship("User", back_populates="task_memos", foreign_keys=[owner_user_id])
  related_task = relationship("Task", back_populates="memos", foreign_keys=[related_task_id])
