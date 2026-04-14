from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
  Boolean,
  CheckConstraint,
  DateTime,
  ForeignKey,
  Index,
  Integer,
  String,
  Text,
  UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import build_enum, build_json_type
from app.core.enums import (
  ApprovalMode,
  WorkflowDefinitionStatus,
  WorkflowInstanceStatus,
  WorkflowStepRunStatus,
  WorkflowStepType,
)
from app.models.base import Base
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class TaskTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "task_templates"
  __table_args__ = (
    Index("idx_task_templates_category_active", "category", "is_active"),
  )

  code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
  name: Mapped[str] = mapped_column(String(120), nullable=False)
  category: Mapped[str] = mapped_column(String(64), nullable=False)
  description: Mapped[str | None] = mapped_column(Text, nullable=True)
  trigger_type: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
  config: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
  created_by: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_task_templates_created_by"),
    nullable=False,
  )

  creator = relationship("User", back_populates="created_task_templates")
  steps = relationship(
    "TaskTemplateStep",
    back_populates="template",
    cascade="all, delete-orphan",
    order_by="TaskTemplateStep.sort_order",
  )
  schedules = relationship("TaskSchedule", back_populates="template", cascade="all, delete-orphan")


class TaskTemplateStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "task_template_steps"
  __table_args__ = (
    UniqueConstraint("template_id", "step_key", name="uq_task_template_steps_template_key"),
    Index("idx_task_template_steps_template_order", "template_id", "sort_order"),
  )

  template_id: Mapped[UUID] = mapped_column(
    ForeignKey("task_templates.id", name="fk_task_template_steps_template"),
    nullable=False,
  )
  step_key: Mapped[str] = mapped_column(String(64), nullable=False)
  title: Mapped[str] = mapped_column(String(255), nullable=False)
  description: Mapped[str | None] = mapped_column(Text, nullable=True)
  step_type: Mapped[str] = mapped_column(String(32), default="task", nullable=False)
  default_assignee_rule: Mapped[dict[str, Any]] = mapped_column(
    build_json_type(),
    default=dict,
    nullable=False,
  )
  default_due_offset_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
  sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  config: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)

  template = relationship("TaskTemplate", back_populates="steps")
  dependencies = relationship(
    "TaskTemplateStepDependency",
    back_populates="step",
    foreign_keys="TaskTemplateStepDependency.step_id",
    cascade="all, delete-orphan",
  )
  blocked_by = relationship(
    "TaskTemplateStepDependency",
    back_populates="depends_on_step",
    foreign_keys="TaskTemplateStepDependency.depends_on_step_id",
    cascade="all, delete-orphan",
  )


class TaskTemplateStepDependency(Base):
  __tablename__ = "task_template_step_dependencies"
  __table_args__ = (
    CheckConstraint("step_id <> depends_on_step_id", name="task_tpl_step_deps_not_self"),
    Index("idx_task_tpl_step_deps_depends_on", "depends_on_step_id"),
  )

  step_id: Mapped[UUID] = mapped_column(
    ForeignKey(
      "task_template_steps.id",
      name="fk_task_tpl_step_deps_step",
      ondelete="CASCADE",
    ),
    primary_key=True,
  )
  depends_on_step_id: Mapped[UUID] = mapped_column(
    ForeignKey(
      "task_template_steps.id",
      name="fk_task_tpl_step_deps_depends_on",
      ondelete="CASCADE",
    ),
    primary_key=True,
  )
  dependency_type: Mapped[str] = mapped_column(String(32), default="blocks", nullable=False)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

  step = relationship("TaskTemplateStep", back_populates="dependencies", foreign_keys=[step_id])
  depends_on_step = relationship(
    "TaskTemplateStep",
    back_populates="blocked_by",
    foreign_keys=[depends_on_step_id],
  )


class WorkflowDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "workflow_definitions"
  __table_args__ = (
    Index("idx_workflow_definitions_scope_status", "scope_type", "status"),
  )

  code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
  name: Mapped[str] = mapped_column(String(120), nullable=False)
  scope_type: Mapped[str] = mapped_column(String(64), nullable=False)
  status: Mapped[WorkflowDefinitionStatus] = mapped_column(
    build_enum(enum_cls=WorkflowDefinitionStatus, name="workflow_definition_status"),
    default=WorkflowDefinitionStatus.DRAFT,
    nullable=False,
  )
  version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
  config: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  created_by: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_workflow_definitions_created_by"),
    nullable=False,
  )

  creator = relationship("User", back_populates="workflow_definitions_created")
  steps = relationship(
    "WorkflowStep",
    back_populates="definition",
    cascade="all, delete-orphan",
    order_by="WorkflowStep.sort_order",
  )
  instances = relationship("WorkflowInstance", back_populates="definition")


class WorkflowStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "workflow_steps"
  __table_args__ = (
    UniqueConstraint("definition_id", "step_key", name="uq_workflow_steps_definition_key"),
    Index("idx_workflow_steps_definition_order", "definition_id", "sort_order"),
  )

  definition_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_definitions.id", name="fk_workflow_steps_definition"),
    nullable=False,
  )
  step_key: Mapped[str] = mapped_column(String(64), nullable=False)
  name: Mapped[str] = mapped_column(String(120), nullable=False)
  step_type: Mapped[WorkflowStepType] = mapped_column(
    build_enum(enum_cls=WorkflowStepType, name="workflow_step_type"),
    nullable=False,
  )
  approval_mode: Mapped[ApprovalMode | None] = mapped_column(
    build_enum(enum_cls=ApprovalMode, name="approval_mode"),
    nullable=True,
  )
  assignee_rule: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  reject_target_step_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
  sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  config: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)

  definition = relationship("WorkflowDefinition", back_populates="steps")
  step_runs = relationship("WorkflowStepRun", back_populates="step")


class WorkflowInstance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "workflow_instances"
  __table_args__ = (
    Index("idx_workflow_instances_source", "source_type", "source_id"),
    Index("idx_workflow_instances_status", "status"),
  )

  definition_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_definitions.id", name="fk_workflow_instances_definition"),
    nullable=False,
  )
  source_type: Mapped[str] = mapped_column(String(64), nullable=False)
  source_id: Mapped[UUID | None] = mapped_column(nullable=True)
  initiator_user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_workflow_instances_initiator"),
    nullable=False,
  )
  status: Mapped[WorkflowInstanceStatus] = mapped_column(
    build_enum(enum_cls=WorkflowInstanceStatus, name="workflow_instance_status"),
    default=WorkflowInstanceStatus.PENDING,
    nullable=False,
  )
  current_step_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
  payload: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
  completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

  definition = relationship("WorkflowDefinition", back_populates="instances")
  initiator = relationship("User", back_populates="workflow_instances_started")
  step_runs = relationship("WorkflowStepRun", back_populates="instance", cascade="all, delete-orphan")


class WorkflowStepRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "workflow_step_runs"
  __table_args__ = (
    Index("idx_workflow_step_runs_instance_status", "instance_id", "status"),
    Index("idx_workflow_step_runs_assignee_status", "assignee_user_id", "status"),
  )

  instance_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_instances.id", name="fk_workflow_step_runs_instance"),
    nullable=False,
  )
  step_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_steps.id", name="fk_workflow_step_runs_step"),
    nullable=False,
  )
  assignee_user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_workflow_step_runs_assignee"),
    nullable=False,
  )
  delegated_from_user_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("users.id", name="fk_workflow_step_runs_delegated_from"),
    nullable=True,
  )
  status: Mapped[WorkflowStepRunStatus] = mapped_column(
    build_enum(enum_cls=WorkflowStepRunStatus, name="workflow_step_run_status"),
    default=WorkflowStepRunStatus.PENDING,
    nullable=False,
  )
  acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  comment: Mapped[str | None] = mapped_column(Text, nullable=True)
  payload: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)

  instance = relationship("WorkflowInstance", back_populates="step_runs")
  step = relationship("WorkflowStep", back_populates="step_runs")
  assignee = relationship(
    "User",
    foreign_keys=[assignee_user_id],
    back_populates="workflow_step_runs_assigned",
  )
  delegated_from = relationship(
    "User",
    foreign_keys=[delegated_from_user_id],
    back_populates="workflow_step_runs_delegated",
  )


class TaskWatcher(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
  __tablename__ = "task_watchers"
  __table_args__ = (
    UniqueConstraint("task_id", "user_id", "relation", name="uq_task_watchers_binding"),
    Index("idx_task_watchers_user_id", "user_id"),
  )

  task_id: Mapped[UUID] = mapped_column(
    ForeignKey("tasks.id", name="fk_task_watchers_task", ondelete="CASCADE"),
    nullable=False,
  )
  user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_task_watchers_user"),
    nullable=False,
  )
  relation: Mapped[str] = mapped_column(String(32), default="cc", nullable=False)
  created_by: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_task_watchers_created_by"),
    nullable=False,
  )

  task = relationship("Task", back_populates="watchers")
  user = relationship("User", foreign_keys=[user_id], back_populates="task_watches")
  creator = relationship("User", foreign_keys=[created_by], back_populates="created_task_watches")


class TaskSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "task_schedules"
  __table_args__ = (
    Index("idx_task_schedules_active_next_run", "is_active", "next_run_at"),
    Index("idx_task_schedules_owner_user_id", "owner_user_id"),
  )

  template_id: Mapped[UUID] = mapped_column(
    ForeignKey("task_templates.id", name="fk_task_schedules_template"),
    nullable=False,
  )
  owner_user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_task_schedules_owner"),
    nullable=False,
  )
  cron_expr: Mapped[str] = mapped_column(String(128), nullable=False)
  timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
  next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
  payload: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)

  template = relationship("TaskTemplate", back_populates="schedules")
  owner = relationship("User", back_populates="task_schedules")
