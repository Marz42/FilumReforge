from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
  Boolean,
  CheckConstraint,
  Date,
  DateTime,
  ForeignKey,
  Index,
  Integer,
  String,
  Text,
  UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import build_enum, build_json_type, build_value_enum
from app.core.enums import (
  DelegationScopeType,
  DelegationStatus,
  EmploymentEventTriggerStatus,
  EmploymentEventType,
  PositionAssignmentType,
  ReportingLineType,
)
from app.models.base import Base
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Position(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "positions"
  __table_args__ = (
    Index("idx_positions_is_active", "is_active"),
  )

  code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
  name: Mapped[str] = mapped_column(String(120), nullable=False)
  level: Mapped[str | None] = mapped_column(String(64), nullable=True)
  extra_metadata: Mapped[dict[str, Any]] = mapped_column(
    "metadata",
    build_json_type(),
    default=dict,
    nullable=False,
  )
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

  assignments = relationship("ProfilePosition", back_populates="position")


class ProfilePosition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "profile_positions"
  __table_args__ = (
    UniqueConstraint(
      "user_id",
      "position_id",
      "department_id",
      "starts_at",
      name="uq_profile_positions_assignment",
    ),
    CheckConstraint("ends_at IS NULL OR ends_at >= starts_at", name="profile_positions_valid_period"),
    Index("idx_profile_positions_user_id", "user_id"),
    Index("idx_profile_positions_department_id", "department_id"),
    Index("idx_profile_positions_is_primary", "user_id", "is_primary"),
  )

  user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
  position_id: Mapped[UUID] = mapped_column(ForeignKey("positions.id"), nullable=False)
  department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id"), nullable=False)
  assignment_type: Mapped[PositionAssignmentType] = mapped_column(
    build_enum(enum_cls=PositionAssignmentType, name="position_assignment_type"),
    default=PositionAssignmentType.PRIMARY,
    nullable=False,
  )
  is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  starts_at: Mapped[date] = mapped_column(Date, nullable=False)
  ends_at: Mapped[date | None] = mapped_column(Date, nullable=True)

  user = relationship("User", back_populates="position_assignments")
  position = relationship("Position", back_populates="assignments")
  department = relationship("Department", back_populates="profile_positions")


class ReportingLine(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "reporting_lines"
  __table_args__ = (
    UniqueConstraint(
      "user_id",
      "manager_user_id",
      "line_type",
      "department_id",
      "starts_at",
      name="uq_reporting_lines_relation",
    ),
    CheckConstraint("user_id <> manager_user_id", name="reporting_lines_not_self"),
    CheckConstraint("ends_at IS NULL OR ends_at >= starts_at", name="reporting_lines_valid_period"),
    Index("idx_reporting_lines_user_id", "user_id"),
    Index("idx_reporting_lines_manager_user_id", "manager_user_id"),
  )

  user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
  manager_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
  department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
  line_type: Mapped[ReportingLineType] = mapped_column(
    build_enum(enum_cls=ReportingLineType, name="reporting_line_type"),
    nullable=False,
  )
  is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  starts_at: Mapped[date] = mapped_column(Date, nullable=False)
  ends_at: Mapped[date | None] = mapped_column(Date, nullable=True)

  user = relationship("User", foreign_keys=[user_id], back_populates="reporting_lines")
  manager = relationship("User", foreign_keys=[manager_user_id], back_populates="managed_reporting_lines")
  department = relationship("Department", back_populates="reporting_lines")


class ProfileFieldDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "profile_field_definitions"
  __table_args__ = (
    Index("idx_profile_field_definitions_is_active", "is_active"),
  )

  field_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
  label: Mapped[str] = mapped_column(String(120), nullable=False)
  field_type: Mapped[str] = mapped_column(String(32), nullable=False)
  storage_target: Mapped[str] = mapped_column(String(32), nullable=False)
  is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  config: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

  permissions = relationship(
    "ProfileFieldPermission",
    back_populates="field_definition",
    cascade="all, delete-orphan",
  )


class ProfileFieldPermission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "profile_field_permissions"
  __table_args__ = (
    Index("idx_profile_field_permissions_definition", "field_definition_id"),
    Index("idx_profile_field_permissions_priority", "priority"),
  )

  field_definition_id: Mapped[UUID] = mapped_column(
    ForeignKey(
      "profile_field_definitions.id",
      name="fk_profile_field_permissions_definition",
      ondelete="CASCADE",
    ),
    nullable=False,
  )
  subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
  subject_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
  can_view: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  can_edit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  scope_filters: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

  field_definition = relationship("ProfileFieldDefinition", back_populates="permissions")


class EmploymentEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
  __tablename__ = "employment_events"
  __table_args__ = (
    Index("idx_employment_events_user_id_date", "user_id", "effective_date"),
    Index("idx_employment_events_type", "event_type"),
  )

  user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
  event_type: Mapped[EmploymentEventType] = mapped_column(
    build_enum(enum_cls=EmploymentEventType, name="employment_event_type"),
    nullable=False,
  )
  effective_date: Mapped[date] = mapped_column(Date, nullable=False)
  title: Mapped[str] = mapped_column(String(255), nullable=False)
  summary: Mapped[str | None] = mapped_column(Text, nullable=True)
  payload: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  task_template_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("task_templates.id", name="fk_employment_events_task_template"),
    nullable=True,
  )
  workflow_definition_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("workflow_definitions.id", name="fk_employment_events_workflow_definition"),
    nullable=True,
  )
  trigger_status: Mapped[EmploymentEventTriggerStatus] = mapped_column(
    build_value_enum(enum_cls=EmploymentEventTriggerStatus, name="employment_event_trigger_status"),
    default=EmploymentEventTriggerStatus.SKIPPED,
    nullable=False,
  )
  triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  trigger_error: Mapped[str | None] = mapped_column(Text, nullable=True)
  trigger_attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  triggered_template_instance_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("task_template_instances.id", name="fk_employment_events_template_instance"),
    nullable=True,
  )
  triggered_workflow_instance_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("workflow_instances.id", name="fk_employment_events_workflow_instance"),
    nullable=True,
  )
  created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

  user = relationship("User", foreign_keys=[user_id], back_populates="employment_events")
  creator = relationship("User", foreign_keys=[created_by], back_populates="created_employment_events")
  task_template = relationship("TaskTemplate", foreign_keys=[task_template_id])
  workflow_definition = relationship("WorkflowDefinition", foreign_keys=[workflow_definition_id])
  triggered_template_instance = relationship("TaskTemplateInstance", foreign_keys=[triggered_template_instance_id])
  triggered_workflow_instance = relationship("WorkflowInstance", foreign_keys=[triggered_workflow_instance_id])


class Delegation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "delegations"
  __table_args__ = (
    CheckConstraint("delegator_user_id <> delegate_user_id", name="delegations_not_self"),
    CheckConstraint("ends_at > starts_at", name="delegations_valid_window"),
    Index("idx_delegations_delegator_status", "delegator_user_id", "status"),
    Index("idx_delegations_delegate_status", "delegate_user_id", "status"),
  )

  delegator_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
  delegate_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
  scope_type: Mapped[DelegationScopeType] = mapped_column(
    build_enum(enum_cls=DelegationScopeType, name="delegation_scope_type"),
    default=DelegationScopeType.DATA_ACCESS,
    nullable=False,
  )
  scope_department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
  scope_filters: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  status: Mapped[DelegationStatus] = mapped_column(
    build_enum(enum_cls=DelegationStatus, name="delegation_status"),
    default=DelegationStatus.PENDING,
    nullable=False,
  )
  starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

  delegator = relationship("User", foreign_keys=[delegator_user_id], back_populates="delegations_granted")
  delegate = relationship("User", foreign_keys=[delegate_user_id], back_populates="delegations_received")
  creator = relationship("User", foreign_keys=[created_by], back_populates="created_delegations")
  scope_department = relationship("Department", back_populates="delegations")
