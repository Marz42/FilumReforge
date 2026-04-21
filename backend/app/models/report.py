from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import build_value_enum
from app.core.enums import ReportDirection, ReportRouteStatus, ReportStatus
from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
  from app.models.task_workflow import WorkflowDefinition, WorkflowInstance


class Report(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "reports"
  __table_args__ = (
    Index("idx_reports_initiator_status", "initiator_user_id", "status"),
    Index("idx_reports_current_recipient", "current_recipient_user_id", "status"),
    Index("idx_reports_target_status", "target_user_id", "status"),
  )

  direction: Mapped[ReportDirection] = mapped_column(
    build_value_enum(enum_cls=ReportDirection, name="report_direction"),
    nullable=False,
  )
  status: Mapped[ReportStatus] = mapped_column(
    build_value_enum(enum_cls=ReportStatus, name="report_status"),
    default=ReportStatus.IN_PROGRESS,
    nullable=False,
  )
  title: Mapped[str] = mapped_column(String(255), nullable=False)
  content_md: Mapped[str] = mapped_column(Text, nullable=False)
  initiator_user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_reports_initiator"),
    nullable=False,
  )
  target_user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_reports_target"),
    nullable=False,
  )
  current_recipient_user_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("users.id", name="fk_reports_current_recipient"),
    nullable=True,
  )
  current_route_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
  workflow_definition_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("workflow_definitions.id", name="fk_reports_workflow_definition"),
    nullable=True,
  )
  workflow_instance_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("workflow_instances.id", name="fk_reports_workflow_instance"),
    nullable=True,
  )
  completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

  initiator = relationship(
    "User",
    foreign_keys=[initiator_user_id],
    back_populates="reports_initiated",
  )
  target = relationship(
    "User",
    foreign_keys=[target_user_id],
    back_populates="reports_targeted",
  )
  current_recipient = relationship(
    "User",
    foreign_keys=[current_recipient_user_id],
    back_populates="reports_currently_received",
  )
  workflow_definition = relationship("WorkflowDefinition", foreign_keys=[workflow_definition_id])
  workflow_instance = relationship("WorkflowInstance", foreign_keys=[workflow_instance_id])
  routes = relationship(
    "ReportRoute",
    back_populates="report",
    cascade="all, delete-orphan",
    order_by="ReportRoute.sequence_no",
  )


class ReportRoute(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "report_routes"
  __table_args__ = (
    UniqueConstraint("report_id", "sequence_no", name="uq_report_routes_sequence"),
    Index("idx_report_routes_assigned_status", "assigned_user_id", "status"),
    Index("idx_report_routes_report_status", "report_id", "status"),
  )

  report_id: Mapped[UUID] = mapped_column(
    ForeignKey("reports.id", name="fk_report_routes_report", ondelete="CASCADE"),
    nullable=False,
  )
  sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
  sender_user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_report_routes_sender"),
    nullable=False,
  )
  recipient_user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_report_routes_recipient"),
    nullable=False,
  )
  assigned_user_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("users.id", name="fk_report_routes_assigned"),
    nullable=True,
  )
  status: Mapped[ReportRouteStatus] = mapped_column(
    build_value_enum(enum_cls=ReportRouteStatus, name="report_route_status"),
    default=ReportRouteStatus.QUEUED,
    nullable=False,
  )
  activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  note: Mapped[str | None] = mapped_column(Text, nullable=True)

  report = relationship("Report", back_populates="routes")
  sender = relationship(
    "User",
    foreign_keys=[sender_user_id],
    back_populates="report_routes_sent",
  )
  recipient = relationship(
    "User",
    foreign_keys=[recipient_user_id],
    back_populates="report_routes_received",
  )
  assigned_user = relationship(
    "User",
    foreign_keys=[assigned_user_id],
    back_populates="report_routes_assigned",
  )
