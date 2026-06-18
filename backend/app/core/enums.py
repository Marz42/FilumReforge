from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
  ADMIN = "admin"
  HR = "hr"
  EMPLOYEE = "employee"


class UserStatus(StrEnum):
  ACTIVE = "active"
  INACTIVE = "inactive"
  SUSPENDED = "suspended"
  OFFBOARDED = "offboarded"


class TaskStatus(StrEnum):
  TODO = "todo"
  DOING = "doing"
  REVIEW = "review"
  DONE = "done"


class TaskPriority(StrEnum):
  LOW = "low"
  MEDIUM = "medium"
  HIGH = "high"
  URGENT = "urgent"


class TaskSourceType(StrEnum):
  MANUAL = "manual"
  TEMPLATE = "template"
  EVENT = "event"
  AI = "ai"


class TaskActionType(StrEnum):
  CREATED = "created"
  ASSIGNED = "assigned"
  STATUS_CHANGED = "status_changed"
  COMMENTED = "commented"
  ATTACHMENT_ADDED = "attachment_added"
  DUE_DATE_CHANGED = "due_date_changed"
  CLOSED = "closed"


class CommentFormat(StrEnum):
  PLAIN_TEXT = "plain_text"
  MARKDOWN = "markdown"


class AttachmentVisibility(StrEnum):
  PRIVATE = "private"
  INTERNAL = "internal"
  PUBLIC = "public"


class AttachmentStatus(StrEnum):
  UPLOADED = "uploaded"
  DELETED = "deleted"
  QUARANTINED = "quarantined"


class AttachmentTargetType(StrEnum):
  TASK_COMMENT = "task_comment"
  TASK = "task"
  PROFILE = "profile"
  DOCUMENT = "document"
  NOTIFICATION_MESSAGE = "notification_message"
  REPORT = "report"


class NotificationChannel(StrEnum):
  EMAIL = "email"
  WEB_PUSH = "web_push"
  WEBSOCKET = "websocket"


DEFAULT_USER_NOTIFICATION_CHANNELS: tuple[NotificationChannel, ...] = (
  NotificationChannel.WEBSOCKET,
  NotificationChannel.EMAIL,
  NotificationChannel.WEB_PUSH,
)


class NotificationMessageStatus(StrEnum):
  QUEUED = "queued"
  PROCESSING = "processing"
  COMPLETED = "completed"
  FAILED = "failed"


class NotificationDeliveryStatus(StrEnum):
  PENDING = "pending"
  SENT = "sent"
  FAILED = "failed"
  RETRYING = "retrying"


class NotificationReceiptType(StrEnum):
  DELIVERED = "delivered"
  READ = "read"
  ACKNOWLEDGED = "acknowledged"


class PositionAssignmentType(StrEnum):
  PRIMARY = "primary"
  PART_TIME = "part_time"
  ACTING = "acting"


class ReportingLineType(StrEnum):
  SOLID = "solid"
  DOTTED = "dotted"


class EmploymentEventType(StrEnum):
  ONBOARD = "onboard"
  TRANSFER = "transfer"
  PROMOTION = "promotion"
  REWARD = "reward"
  DISCIPLINE = "discipline"
  OFFBOARD = "offboard"
  REHIRE = "rehire"


class EmploymentEventTriggerStatus(StrEnum):
  PENDING = "pending"
  PROCESSING = "processing"
  SUCCEEDED = "succeeded"
  FAILED = "failed"
  SKIPPED = "skipped"


class DelegationScopeType(StrEnum):
  APPROVAL = "approval"
  TASK = "task"
  DATA_ACCESS = "data_access"
  ALL = "all"


class DelegationStatus(StrEnum):
  PENDING = "pending"
  ACTIVE = "active"
  EXPIRED = "expired"
  REVOKED = "revoked"


class WorkflowDefinitionStatus(StrEnum):
  DRAFT = "draft"
  ACTIVE = "active"
  ARCHIVED = "archived"


class WorkflowStepType(StrEnum):
  TASK = "task"
  APPROVAL = "approval"
  NOTIFY = "notify"


class ApprovalMode(StrEnum):
  SINGLE = "single"
  PARALLEL_ALL = "parallel_all"
  PARALLEL_ANY = "parallel_any"


class WorkflowInstanceStatus(StrEnum):
  PENDING = "pending"
  IN_PROGRESS = "in_progress"
  APPROVED = "approved"
  REJECTED = "rejected"
  RETURNED = "returned"
  CANCELLED = "cancelled"
  COMPLETED = "completed"


class WorkflowStepRunStatus(StrEnum):
  PENDING = "pending"
  APPROVED = "approved"
  REJECTED = "rejected"
  RETURNED = "returned"
  DELEGATED = "delegated"
  SKIPPED = "skipped"


class WorkflowGraphTemplateStatus(StrEnum):
  DRAFT = "draft"
  ACTIVE = "active"
  ARCHIVED = "archived"


class WorkflowGraphNodeType(StrEnum):
  TASK = "task"
  APPROVAL = "approval"
  NOTICE = "notice"


class WorkflowGraphInstanceStatus(StrEnum):
  PENDING = "pending"
  ACTIVE = "active"
  COMPLETED = "completed"
  CANCELLED = "cancelled"
  TERMINATED = "terminated"


class WorkflowNodeEngineState(StrEnum):
  PENDING = "pending"
  ACTIVATED = "activated"
  ACKNOWLEDGED = "acknowledged"
  COMPLETED = "completed"
  TERMINATED = "terminated"


class WorkflowNodeBusinessState(StrEnum):
  DRAFT = "draft"
  ASSIGNED = "assigned"
  ACCEPTED = "accepted"
  REJECTED = "rejected"
  DELEGATED = "delegated"
  DOING = "doing"
  PENDING_REVIEW = "pending_review"
  DONE = "done"
  RETURNED_FOR_REWORK = "returned_for_rework"
  CANCELLED = "cancelled"


class WorkflowOutboxEventStatus(StrEnum):
  PENDING = "pending"
  RETRYING = "retrying"
  DISPATCHED = "dispatched"
  FAILED = "failed"


class PushSubscriptionStatus(StrEnum):
  ACTIVE = "active"
  EXPIRED = "expired"
  REVOKED = "revoked"


class DocumentCategory(StrEnum):
  POLICY = "policy"
  SOP = "sop"
  ANNOUNCEMENT = "announcement"
  FAQ = "faq"
  OTHER = "other"


class DocumentStatus(StrEnum):
  DRAFT = "draft"
  PUBLISHED = "published"
  ARCHIVED = "archived"


class DepartmentCapability(StrEnum):
  PUBLISH_ANNOUNCEMENT = "publish_announcement"
  PUBLISH_ORG_TASK = "publish_org_task"
  MANAGE_TEMPLATES = "manage_templates"


class ReportDirection(StrEnum):
  UPWARD = "upward"
  DOWNWARD = "downward"


class ReportStatus(StrEnum):
  IN_PROGRESS = "in_progress"
  COMPLETED = "completed"
  RETURNED = "returned"
  ARCHIVED = "archived"


class ReportRouteStatus(StrEnum):
  QUEUED = "queued"
  PENDING = "pending"
  FORWARDED = "forwarded"
  COMPLETED = "completed"


class TaskDetailUiProfile(StrEnum):
  VIDEO_N1_CAPTURE = "video_n1_capture"
  VIDEO_N2_AGGREGATE = "video_n2_aggregate"
  VIDEO_BATCH_ROOT = "video_batch_root"
  VIDEO_PRODUCTION_STEP = "video_production_step"
  VIDEO_PRODUCTION_MULTI = "video_production_multi"
  VIDEO_PRODUCTION_PLATFORM = "video_production_platform"
  VIDEO_CAPTURE_ASSIGN = "video_capture_assign"
  VIDEO_CAPTURE_SCHEDULE = "video_capture_schedule"
  GRAPH_MANUAL = "graph_manual"
  LEGACY_TASK = "legacy_task"
  RETURNED = "returned"
