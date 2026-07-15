from __future__ import annotations

from datetime import UTC, datetime
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
from sqlalchemy.schema import conv

from app.core.db_types import build_json_type, build_value_enum
from app.core.enums import (
  WorkflowGraphInstanceStatus,
  WorkflowGraphNodeType,
  WorkflowGraphTemplateStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
  WorkflowOutboxEventStatus,
)
from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class WorkflowGraphTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "workflow_graph_templates"
  __table_args__ = (
    UniqueConstraint("code", name="uq_wf_graph_tpls_code"),
    UniqueConstraint("base_code", "version", name="uq_wf_graph_tpls_base_ver"),
    Index("idx_wf_graph_tpls_status", "status"),
    Index("idx_wf_graph_tpls_base_code", "base_code"),
    CheckConstraint("scope_mode in ('global', 'departments')", name="wf_graph_tpls_scope_mode_chk"),
  )

  code: Mapped[str] = mapped_column(String(64), nullable=False)
  base_code: Mapped[str] = mapped_column(String(64), nullable=False)
  version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
  name: Mapped[str] = mapped_column(String(120), nullable=False)
  description: Mapped[str | None] = mapped_column(Text, nullable=True)
  status: Mapped[WorkflowGraphTemplateStatus] = mapped_column(
    build_value_enum(enum_cls=WorkflowGraphTemplateStatus, name="workflow_graph_template_status"),
    default=WorkflowGraphTemplateStatus.DRAFT,
    nullable=False,
  )
  context_schema: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  config: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  scope_mode: Mapped[str] = mapped_column(String(16), default="global", nullable=False)
  scope_department_ids: Mapped[list[Any]] = mapped_column(build_json_type(), default=list, nullable=False)
  created_by: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_wf_graph_tpls_created_by"),
    nullable=False,
  )
  source_template_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("workflow_graph_templates.id", name="fk_wf_graph_tpls_source"),
    nullable=True,
  )

  creator = relationship("User", foreign_keys=[created_by])
  source_template = relationship("WorkflowGraphTemplate", remote_side="WorkflowGraphTemplate.id")
  nodes = relationship(
    "WorkflowGraphTemplateNode",
    back_populates="template",
    cascade="all, delete-orphan",
    order_by="WorkflowGraphTemplateNode.sort_order",
  )
  edges = relationship(
    "WorkflowGraphTemplateEdge",
    back_populates="template",
    cascade="all, delete-orphan",
  )
  instances = relationship("WorkflowGraphInstance", back_populates="template")
  schedules = relationship(
    "WorkflowGraphTemplateSchedule",
    back_populates="template",
    cascade="all, delete-orphan",
  )


class WorkflowGraphTemplateNode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "workflow_graph_template_nodes"
  __table_args__ = (
    UniqueConstraint("template_id", "node_key", name="uq_wf_graph_tpl_nodes_key"),
    Index("idx_wf_graph_tpl_nodes_order", "template_id", "sort_order"),
    CheckConstraint("assignment_mode in ('single', 'fan_out')", name="wf_graph_tpl_nodes_assign_chk"),
    CheckConstraint("join_mode in ('all', 'any')", name="wf_graph_tpl_nodes_join_chk"),
    CheckConstraint(
      "routing_mode in ('exclusive', 'inclusive', 'parallel', 'first_match')",
      name="wf_graph_tpl_nodes_route_chk",
    ),
  )

  template_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_graph_templates.id", name="fk_wf_graph_tpl_nodes_template", ondelete="CASCADE"),
    nullable=False,
  )
  node_key: Mapped[str] = mapped_column(String(64), nullable=False)
  title: Mapped[str] = mapped_column(String(255), nullable=False)
  description: Mapped[str | None] = mapped_column(Text, nullable=True)
  node_type: Mapped[WorkflowGraphNodeType] = mapped_column(
    build_value_enum(enum_cls=WorkflowGraphNodeType, name="workflow_graph_node_type"),
    default=WorkflowGraphNodeType.TASK,
    nullable=False,
  )
  assignment_mode: Mapped[str] = mapped_column(String(32), default="single", nullable=False)
  join_mode: Mapped[str] = mapped_column(String(32), default="all", nullable=False)
  routing_mode: Mapped[str] = mapped_column(String(16), default="inclusive", nullable=False)
  assignee_rule: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  config: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

  template = relationship("WorkflowGraphTemplate", back_populates="nodes")
  outgoing_edges = relationship(
    "WorkflowGraphTemplateEdge",
    back_populates="from_node",
    foreign_keys="WorkflowGraphTemplateEdge.from_node_id",
    cascade="all, delete-orphan",
  )
  incoming_edges = relationship(
    "WorkflowGraphTemplateEdge",
    back_populates="to_node",
    foreign_keys="WorkflowGraphTemplateEdge.to_node_id",
    cascade="all, delete-orphan",
  )
  node_instances = relationship("WorkflowNodeInstance", back_populates="template_node")


class WorkflowGraphTemplateEdge(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "workflow_graph_template_edges"
  __table_args__ = (
    UniqueConstraint("template_id", "from_node_id", "to_node_id", name="uq_wf_graph_tpl_edges_path"),
    CheckConstraint("from_node_id <> to_node_id", name="wf_graph_tpl_edges_not_self"),
    Index("idx_wf_graph_tpl_edges_from", "template_id", "from_node_id"),
  )

  template_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_graph_templates.id", name="fk_wf_graph_tpl_edges_template", ondelete="CASCADE"),
    nullable=False,
  )
  from_node_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_graph_template_nodes.id", name="fk_wf_graph_tpl_edges_from", ondelete="CASCADE"),
    nullable=False,
  )
  to_node_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_graph_template_nodes.id", name="fk_wf_graph_tpl_edges_to", ondelete="CASCADE"),
    nullable=False,
  )
  is_reject_path: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  condition: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

  template = relationship("WorkflowGraphTemplate", back_populates="edges")
  from_node = relationship(
    "WorkflowGraphTemplateNode",
    back_populates="outgoing_edges",
    foreign_keys=[from_node_id],
  )
  to_node = relationship(
    "WorkflowGraphTemplateNode",
    back_populates="incoming_edges",
    foreign_keys=[to_node_id],
  )


class WorkflowGraphInstance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "workflow_graph_instances"
  __table_args__ = (
    CheckConstraint("context_version > 0", name="wf_graph_instances_ctx_ver_chk"),
    CheckConstraint("max_iterations > 0", name="wf_graph_instances_max_iter_chk"),
    CheckConstraint("executor_kind in ('legacy', 'snapshot')", name="wf_graph_instances_executor_chk"),
    CheckConstraint(
      "result IS NULL OR result in ('success', 'approved', 'rejected', 'cancelled', 'terminated', 'failed')",
      name="wf_graph_instances_result_chk",
    ),
    Index("idx_wf_graph_instances_status", "status"),
    Index("idx_wf_graph_instances_template", "template_id", "status"),
    Index("idx_wf_graph_instances_source", "source_type", "source_id"),
    Index("idx_wf_graph_instances_parent", "parent_instance_id"),
  )

  template_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("workflow_graph_templates.id", name="fk_wf_graph_instances_template"),
    nullable=True,
  )
  initiator_user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_wf_graph_instances_initiator"),
    nullable=False,
  )
  department_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("departments.id", name="fk_wf_graph_instances_department"),
    nullable=True,
  )
  source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
  source_id: Mapped[UUID | None] = mapped_column(nullable=True)
  status: Mapped[WorkflowGraphInstanceStatus] = mapped_column(
    build_value_enum(enum_cls=WorkflowGraphInstanceStatus, name="workflow_graph_instance_status"),
    default=WorkflowGraphInstanceStatus.PENDING,
    nullable=False,
  )
  current_node_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
  run_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
  parent_instance_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("workflow_graph_instances.id", name="fk_wf_graph_instances_parent"),
    nullable=True,
  )
  context: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  definition_snapshot: Mapped[dict[str, Any] | None] = mapped_column(build_json_type(), nullable=True)
  definition_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
  engine_version: Mapped[str] = mapped_column(String(32), default="legacy-v1", nullable=False)
  executor_kind: Mapped[str] = mapped_column(String(16), default="legacy", nullable=False)
  result: Mapped[str | None] = mapped_column(String(32), nullable=True)
  diagnostics: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  context_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
  max_iterations: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
  completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

  template = relationship("WorkflowGraphTemplate", back_populates="instances")
  initiator = relationship("User", foreign_keys=[initiator_user_id])
  department = relationship("Department", foreign_keys=[department_id])
  parent_instance = relationship(
    "WorkflowGraphInstance",
    remote_side="WorkflowGraphInstance.id",
    foreign_keys=[parent_instance_id],
  )
  node_instances = relationship(
    "WorkflowNodeInstance",
    back_populates="instance",
    cascade="all, delete-orphan",
  )
  outbox_events = relationship(
    "WorkflowOutboxEvent",
    back_populates="instance",
    cascade="all, delete-orphan",
  )
  run_events = relationship(
    "WorkflowRunEvent",
    back_populates="instance",
    cascade="all, delete-orphan",
    order_by="WorkflowRunEvent.created_at",
  )
  edge_traversals = relationship(
    "WorkflowEdgeTraversal",
    back_populates="instance",
    cascade="all, delete-orphan",
  )
  activation_dependencies = relationship(
    "WorkflowNodeActivationDependency",
    back_populates="instance",
    cascade="all, delete-orphan",
  )


class WorkflowRunEvent(UUIDPrimaryKeyMixin, Base):
  __tablename__ = "workflow_run_events"
  __table_args__ = (
    Index("idx_wf_run_events_instance_created", "instance_id", "created_at"),
    Index("idx_wf_run_events_instance_type", "instance_id", "event_type"),
  )

  instance_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_graph_instances.id", name="fk_wf_run_events_instance", ondelete="CASCADE"),
    nullable=False,
  )
  event_type: Mapped[str] = mapped_column(String(64), nullable=False)
  actor_user_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("users.id", name="fk_wf_run_events_actor", ondelete="SET NULL"),
    nullable=True,
  )
  payload: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=lambda: datetime.now(UTC),
    nullable=False,
  )

  instance = relationship("WorkflowGraphInstance", back_populates="run_events")
  actor = relationship("User", foreign_keys=[actor_user_id])


class WorkflowNodeInstance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "workflow_node_instances"
  __table_args__ = (
    UniqueConstraint(
      "instance_id",
      "node_key",
      "instance_key",
      "iteration",
      name="uq_wf_node_instances_iter",
    ),
    CheckConstraint("iteration > 0", name="wf_node_instances_iter_chk"),
    CheckConstraint("node_instance_version > 0", name="wf_node_instances_ver_chk"),
    Index("idx_wf_node_instances_inst_eng", "instance_id", "engine_state"),
    Index("idx_wf_node_instances_assignee", "assignee_user_id", "engine_state"),
  )

  instance_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_graph_instances.id", name="fk_wf_node_instances_instance", ondelete="CASCADE"),
    nullable=False,
  )
  template_node_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("workflow_graph_template_nodes.id", name="fk_wf_node_instances_template_node"),
    nullable=True,
  )
  node_key: Mapped[str] = mapped_column(String(64), nullable=False)
  instance_key: Mapped[str] = mapped_column(String(64), default="singleton", nullable=False)
  title: Mapped[str] = mapped_column(String(255), nullable=False)
  node_type: Mapped[WorkflowGraphNodeType] = mapped_column(
    build_value_enum(enum_cls=WorkflowGraphNodeType, name="workflow_graph_node_type"),
    default=WorkflowGraphNodeType.TASK,
    nullable=False,
  )
  engine_state: Mapped[WorkflowNodeEngineState] = mapped_column(
    build_value_enum(enum_cls=WorkflowNodeEngineState, name="workflow_node_engine_state"),
    default=WorkflowNodeEngineState.PENDING,
    nullable=False,
  )
  business_state: Mapped[WorkflowNodeBusinessState] = mapped_column(
    build_value_enum(enum_cls=WorkflowNodeBusinessState, name="workflow_node_business_state"),
    default=WorkflowNodeBusinessState.DRAFT,
    nullable=False,
  )
  assignee_user_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("users.id", name="fk_wf_node_instances_assignee"),
    nullable=True,
  )
  iteration: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
  node_instance_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
  config: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

  instance = relationship("WorkflowGraphInstance", back_populates="node_instances")
  template_node = relationship("WorkflowGraphTemplateNode", back_populates="node_instances")
  assignee = relationship("User", foreign_keys=[assignee_user_id])
  deliverables = relationship(
    "WorkflowDeliverable",
    back_populates="node_instance",
    cascade="all, delete-orphan",
  )
  outbox_events = relationship("WorkflowOutboxEvent", back_populates="node_instance")


class WorkflowEdgeTraversal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "workflow_edge_traversals"
  __table_args__ = (
    UniqueConstraint(
      "source_node_instance_id",
      "to_node_key",
      name="uq_wf_edge_traversals_source_target",
    ),
    CheckConstraint(
      "status in ('taken', 'not_taken', 'invalidated')",
      name="wf_edge_traversals_status_chk",
    ),
    CheckConstraint("iteration > 0", name="wf_edge_traversals_iter_chk"),
    CheckConstraint("context_version > 0", name="wf_edge_traversals_ctx_ver_chk"),
    Index("idx_wf_edge_traversals_instance_iter", "instance_id", "iteration"),
    Index("idx_wf_edge_traversals_source", "source_node_instance_id"),
  )

  instance_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_graph_instances.id", name="fk_wf_edge_traversals_instance", ondelete="CASCADE"),
    nullable=False,
  )
  source_node_instance_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_node_instances.id", name="fk_wf_edge_traversals_source", ondelete="CASCADE"),
    nullable=False,
  )
  iteration: Mapped[int] = mapped_column(Integer, nullable=False)
  from_node_key: Mapped[str] = mapped_column(String(64), nullable=False)
  to_node_key: Mapped[str] = mapped_column(String(64), nullable=False)
  status: Mapped[str] = mapped_column(String(16), nullable=False)
  condition: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  evidence: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  context_version: Mapped[int] = mapped_column(Integer, nullable=False)
  invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

  instance = relationship("WorkflowGraphInstance", back_populates="edge_traversals")
  source_node_instance = relationship("WorkflowNodeInstance", foreign_keys=[source_node_instance_id])


class WorkflowNodeActivationDependency(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "workflow_node_activation_dependencies"
  __table_args__ = (
    UniqueConstraint(
      "node_instance_id",
      "source_node_instance_id",
      name="uq_wf_node_activation_deps_pair",
    ),
    CheckConstraint(
      "status in ('waiting', 'satisfied', 'cancelled', 'invalidated')",
      name=conv("wf_node_activation_deps_status_chk"),
    ),
    CheckConstraint("iteration > 0", name=conv("wf_node_activation_deps_iter_chk")),
    Index("idx_wf_node_activation_deps_instance_iter", "instance_id", "iteration"),
    Index("idx_wf_node_activation_deps_node", "node_instance_id", "status"),
  )

  instance_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_graph_instances.id", name="fk_wf_node_activation_deps_instance", ondelete="CASCADE"),
    nullable=False,
  )
  node_instance_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_node_instances.id", name="fk_wf_node_activation_deps_node", ondelete="CASCADE"),
    nullable=False,
  )
  source_node_instance_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_node_instances.id", name="fk_wf_node_activation_deps_source", ondelete="CASCADE"),
    nullable=False,
  )
  traversal_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_edge_traversals.id", name="fk_wf_node_activation_deps_traversal", ondelete="CASCADE"),
    nullable=False,
  )
  iteration: Mapped[int] = mapped_column(Integer, nullable=False)
  target_node_key: Mapped[str] = mapped_column(String(64), nullable=False)
  status: Mapped[str] = mapped_column(String(16), default="waiting", nullable=False)
  invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

  instance = relationship("WorkflowGraphInstance", back_populates="activation_dependencies")
  node_instance = relationship("WorkflowNodeInstance", foreign_keys=[node_instance_id])
  source_node_instance = relationship("WorkflowNodeInstance", foreign_keys=[source_node_instance_id])
  traversal = relationship("WorkflowEdgeTraversal", foreign_keys=[traversal_id])


class WorkflowDeliverable(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "workflow_deliverables"
  __table_args__ = (
    UniqueConstraint("node_instance_id", name="uq_wf_deliverables_node"),
  )

  node_instance_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_node_instances.id", name="fk_wf_deliverables_node", ondelete="CASCADE"),
    nullable=False,
  )
  submitted_by_user_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("users.id", name="fk_wf_deliverables_user"),
    nullable=True,
  )
  submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  summary: Mapped[str | None] = mapped_column(Text, nullable=True)
  payload: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  signature: Mapped[str | None] = mapped_column(String(128), nullable=True)

  node_instance = relationship("WorkflowNodeInstance", back_populates="deliverables")
  submitted_by = relationship("User", foreign_keys=[submitted_by_user_id])


class WorkflowOutboxEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "workflow_outbox_events"
  __table_args__ = (
    Index("idx_wf_outbox_events_inst", "instance_id", "status"),
    Index("idx_wf_outbox_events_status", "status", "available_at"),
  )

  instance_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_graph_instances.id", name="fk_wf_outbox_events_instance", ondelete="CASCADE"),
    nullable=False,
  )
  node_instance_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("workflow_node_instances.id", name="fk_wf_outbox_events_node", ondelete="SET NULL"),
    nullable=True,
  )
  event_type: Mapped[str] = mapped_column(String(64), nullable=False)
  status: Mapped[WorkflowOutboxEventStatus] = mapped_column(
    build_value_enum(enum_cls=WorkflowOutboxEventStatus, name="workflow_outbox_event_status"),
    default=WorkflowOutboxEventStatus.PENDING,
    nullable=False,
  )
  attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
  payload: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)

  instance = relationship("WorkflowGraphInstance", back_populates="outbox_events")
  node_instance = relationship("WorkflowNodeInstance", back_populates="outbox_events")


class WorkflowGraphTemplateSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "workflow_graph_template_schedules"
  __table_args__ = (
    CheckConstraint("scope_mode in ('self', 'subtree')", name=conv("wf_graph_tpl_schedules_scope_mode_chk")),
    CheckConstraint(
      "participant_mode in ('all', 'subset')",
      name=conv("wf_graph_tpl_schedules_participant_mode_chk"),
    ),
    CheckConstraint(
      "last_run_status IS NULL OR last_run_status in ('success', 'failed', 'partial')",
      name=conv("wf_graph_tpl_schedules_last_run_status_chk"),
    ),
    Index("idx_wf_graph_tpl_schedules_active_next_run", "is_active", "next_run_at"),
    Index("idx_wf_graph_tpl_schedules_template", "template_id"),
  )

  template_id: Mapped[UUID] = mapped_column(
    ForeignKey("workflow_graph_templates.id", name="fk_wf_graph_tpl_schedules_template", ondelete="CASCADE"),
    nullable=False,
  )
  name: Mapped[str] = mapped_column(String(120), nullable=False)
  scope_department_id: Mapped[UUID] = mapped_column(
    ForeignKey("departments.id", name="fk_wf_graph_tpl_schedules_scope_department"),
    nullable=False,
  )
  scope_mode: Mapped[str] = mapped_column(String(16), default="self", nullable=False)
  cron_expr: Mapped[str] = mapped_column(String(128), nullable=False)
  timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai", nullable=False)
  default_inputs: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)
  run_label_template: Mapped[str | None] = mapped_column(String(255), nullable=True)
  participant_mode: Mapped[str] = mapped_column(String(16), default="all", nullable=False)
  participant_user_ids: Mapped[list[Any]] = mapped_column(build_json_type(), default=list, nullable=False)
  exclude_department_ids: Mapped[list[Any]] = mapped_column(build_json_type(), default=list, nullable=False)
  exclude_user_ids: Mapped[list[Any]] = mapped_column(build_json_type(), default=list, nullable=False)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
  created_by: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_wf_graph_tpl_schedules_created_by"),
    nullable=False,
  )
  next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  last_run_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
  last_run_message: Mapped[str | None] = mapped_column(Text, nullable=True)
  last_run_instance_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

  template = relationship("WorkflowGraphTemplate", back_populates="schedules")
  scope_department = relationship("Department", foreign_keys=[scope_department_id])
  creator = relationship("User", foreign_keys=[created_by])
