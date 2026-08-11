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
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from app.core.db_types import build_json_type
from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class ProjectionMetadataMixin:
  """Version and replay anchors shared by rebuildable read models."""

  projection_schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
  source_revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  last_event_id: Mapped[UUID | None] = mapped_column(nullable=True)
  projected_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=utc_now,
    nullable=False,
  )


class TaskCenterItem(
  ProjectionMetadataMixin,
  UUIDPrimaryKeyMixin,
  TimestampMixin,
  Base,
):
  """Actor-neutral Task Center candidate row; request-time policy remains authoritative."""

  __tablename__ = "task_center_items"
  __table_args__ = (
    UniqueConstraint("subject_type", "subject_id", name="uq_task_center_items_subject"),
    UniqueConstraint("task_id", name="uq_task_center_items_task"),
    CheckConstraint(
      "subject_type in ('work_item', 'process_run', 'system_alert')",
      name=conv("task_center_items_subject_type_chk"),
    ),
    CheckConstraint(
      "item_kind in ('standalone', 'human_task', 'approval', 'process_run', 'system_alert')",
      name=conv("task_center_items_kind_chk"),
    ),
    CheckConstraint(
      "(subject_type = 'work_item' AND task_id IS NOT NULL) "
      "OR (subject_type = 'process_run' AND process_run_id IS NOT NULL) "
      "OR subject_type = 'system_alert'",
      name=conv("task_center_items_subject_target_chk"),
    ),
    CheckConstraint(
      "(subject_type = 'work_item' AND item_kind in ('standalone', 'human_task', 'approval')) "
      "OR (subject_type = 'process_run' AND item_kind = 'process_run') "
      "OR (subject_type = 'system_alert' AND item_kind = 'system_alert')",
      name=conv("task_center_items_subject_kind_chk"),
    ),
    CheckConstraint("rework_count >= 0", name=conv("task_center_items_rework_chk")),
    CheckConstraint(
      "review_quality_score IS NULL OR review_quality_score between 1 and 5",
      name=conv("task_center_items_quality_chk"),
    ),
    CheckConstraint(
      "projection_schema_version > 0",
      name=conv("task_center_items_schema_ver_chk"),
    ),
    CheckConstraint(
      "source_revision >= 0",
      name=conv("task_center_items_source_rev_chk"),
    ),
    Index(
      "idx_task_center_items_action_due",
      "current_action_owner_user_id",
      "raw_status",
      "due_at",
    ),
    Index(
      "idx_task_center_items_department_due",
      "department_id",
      "raw_status",
      "due_at",
    ),
    Index("idx_task_center_items_history", "completed_at", "subject_id"),
    Index("idx_task_center_items_process_run", "process_run_id", "raw_status"),
  )

  subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
  item_kind: Mapped[str] = mapped_column(String(32), nullable=False)
  subject_id: Mapped[UUID] = mapped_column(nullable=False)
  task_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("tasks.id", name="fk_task_center_items_task", ondelete="CASCADE"),
    nullable=True,
  )
  process_run_id: Mapped[UUID | None] = mapped_column(
    ForeignKey(
      "workflow_graph_instances.id",
      name="fk_task_center_items_process_run",
      ondelete="CASCADE",
    ),
    nullable=True,
  )
  node_instance_id: Mapped[UUID | None] = mapped_column(
    ForeignKey(
      "workflow_node_instances.id",
      name="fk_task_center_items_node",
      ondelete="SET NULL",
    ),
    nullable=True,
  )
  title: Mapped[str] = mapped_column(String(255), nullable=False)
  priority: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
  raw_status: Mapped[str] = mapped_column(String(32), nullable=False)
  engine_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
  business_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
  user_facing_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
  current_stage_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
  current_handler_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
  run_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
  creator_user_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("users.id", name="fk_task_center_items_creator", ondelete="SET NULL"),
    nullable=True,
  )
  assignee_user_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("users.id", name="fk_task_center_items_assignee", ondelete="SET NULL"),
    nullable=True,
  )
  current_action_owner_user_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("users.id", name="fk_task_center_items_action_owner", ondelete="SET NULL"),
    nullable=True,
  )
  department_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("departments.id", name="fk_task_center_items_department", ondelete="SET NULL"),
    nullable=True,
  )
  execution_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
  assignment_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
  requires_action: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  action_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
  latest_deliverable_submitted_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True),
    nullable=True,
  )
  rework_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  review_quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
  source_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  hidden_for_non_management: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  audience_user_ids: Mapped[list[Any]] = mapped_column(
    build_json_type(),
    default=list,
    nullable=False,
  )
  audience_department_ids: Mapped[list[Any]] = mapped_column(
    build_json_type(),
    default=list,
    nullable=False,
  )


class ProcessRunSummary(
  ProjectionMetadataMixin,
  UUIDPrimaryKeyMixin,
  TimestampMixin,
  Base,
):
  """Rebuildable summary for a workflow graph process run."""

  __tablename__ = "process_run_summaries"
  __table_args__ = (
    UniqueConstraint("process_run_id", name="uq_process_run_summaries_run"),
    CheckConstraint(
      "total_node_count >= 0 AND completed_node_count >= 0 "
      "AND active_node_count >= 0 AND pending_node_count >= 0 AND blocked_node_count >= 0 "
      "AND completed_node_count <= total_node_count AND active_node_count <= total_node_count "
      "AND pending_node_count <= total_node_count AND blocked_node_count <= total_node_count",
      name=conv("process_run_summaries_counts_chk"),
    ),
    CheckConstraint(
      "progress_percent between 0 and 100",
      name=conv("process_run_summaries_progress_chk"),
    ),
    CheckConstraint(
      "projection_schema_version > 0",
      name=conv("process_run_summaries_schema_ver_chk"),
    ),
    CheckConstraint(
      "source_revision >= 0",
      name=conv("process_run_summaries_source_rev_chk"),
    ),
    Index("idx_process_run_summaries_status_updated", "status", "source_updated_at"),
    Index("idx_process_run_summaries_department", "department_id", "status"),
    Index("idx_process_run_summaries_parent", "parent_process_run_id"),
  )

  process_run_id: Mapped[UUID] = mapped_column(
    ForeignKey(
      "workflow_graph_instances.id",
      name="fk_process_run_summaries_process_run",
      ondelete="CASCADE",
    ),
    nullable=False,
  )
  template_id: Mapped[UUID | None] = mapped_column(
    ForeignKey(
      "workflow_graph_templates.id",
      name="fk_process_run_summaries_template",
      ondelete="SET NULL",
    ),
    nullable=True,
  )
  parent_process_run_id: Mapped[UUID | None] = mapped_column(
    ForeignKey(
      "workflow_graph_instances.id",
      name="fk_process_run_summaries_parent",
      ondelete="SET NULL",
    ),
    nullable=True,
  )
  source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
  source_id: Mapped[UUID | None] = mapped_column(nullable=True)
  department_id: Mapped[UUID | None] = mapped_column(
    ForeignKey(
      "departments.id",
      name="fk_process_run_summaries_department",
      ondelete="SET NULL",
    ),
    nullable=True,
  )
  initiator_user_id: Mapped[UUID | None] = mapped_column(
    ForeignKey(
      "users.id",
      name="fk_process_run_summaries_initiator",
      ondelete="SET NULL",
    ),
    nullable=True,
  )
  run_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
  status: Mapped[str] = mapped_column(String(32), nullable=False)
  result: Mapped[str | None] = mapped_column(String(32), nullable=True)
  current_node_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
  current_stage_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
  total_node_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  completed_node_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  active_node_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  pending_node_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  blocked_node_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  source_updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=utc_now,
    nullable=False,
  )
  completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  latest_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  audience_user_ids: Mapped[list[Any]] = mapped_column(
    build_json_type(),
    default=list,
    nullable=False,
  )
  audience_department_ids: Mapped[list[Any]] = mapped_column(
    build_json_type(),
    default=list,
    nullable=False,
  )


class NodeTimelineEntry(
  ProjectionMetadataMixin,
  UUIDPrimaryKeyMixin,
  TimestampMixin,
  Base,
):
  """Unified timeline reference; source records retain full business bodies."""

  __tablename__ = "node_timeline_entries"
  __table_args__ = (
    UniqueConstraint("source_type", "source_id", name="uq_node_timeline_entries_source"),
    CheckConstraint(
      "entry_type in ('node_event', 'work_item_activity', 'comment', 'deliverable', "
      "'approval', 'rework', 'takeover', 'system')",
      name=conv("node_timeline_entries_type_chk"),
    ),
    CheckConstraint(
      "visibility in ('public', 'internal', 'management')",
      name=conv("node_timeline_entries_visibility_chk"),
    ),
    CheckConstraint(
      "process_run_id IS NOT NULL OR task_id IS NOT NULL",
      name=conv("node_timeline_entries_parent_chk"),
    ),
    CheckConstraint(
      "projection_schema_version > 0",
      name=conv("node_timeline_entries_schema_ver_chk"),
    ),
    CheckConstraint(
      "source_revision >= 0",
      name=conv("node_timeline_entries_source_rev_chk"),
    ),
    Index("idx_node_timeline_entries_run_time", "process_run_id", "occurred_at", "id"),
    Index("idx_node_timeline_entries_task_time", "task_id", "occurred_at", "id"),
    Index("idx_node_timeline_entries_node_time", "node_instance_id", "occurred_at", "id"),
  )

  process_run_id: Mapped[UUID | None] = mapped_column(
    ForeignKey(
      "workflow_graph_instances.id",
      name="fk_node_timeline_entries_process_run",
      ondelete="CASCADE",
    ),
    nullable=True,
  )
  node_instance_id: Mapped[UUID | None] = mapped_column(
    ForeignKey(
      "workflow_node_instances.id",
      name="fk_node_timeline_entries_node",
      ondelete="SET NULL",
    ),
    nullable=True,
  )
  task_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("tasks.id", name="fk_node_timeline_entries_task", ondelete="CASCADE"),
    nullable=True,
  )
  source_type: Mapped[str] = mapped_column(String(32), nullable=False)
  source_id: Mapped[UUID] = mapped_column(nullable=False)
  entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
  event_type: Mapped[str] = mapped_column(String(64), nullable=False)
  actor_user_id: Mapped[UUID | None] = mapped_column(
    ForeignKey(
      "users.id",
      name="fk_node_timeline_entries_actor",
      ondelete="SET NULL",
    ),
    nullable=True,
  )
  visibility: Mapped[str] = mapped_column(String(16), default="public", nullable=False)
  title: Mapped[str] = mapped_column(String(255), nullable=False)
  summary: Mapped[str | None] = mapped_column(Text, nullable=True)
  payload: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
