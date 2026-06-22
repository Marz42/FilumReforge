"""Canonical schema + node definitions for workflow video v1 graph templates (W6)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

TOPIC_MEETING_BATCH_CODE = "topic_meeting_batch_v1"
VIDEO_PRODUCTION_CODE = "video_production_per_topic_v1"
SEED_VERSION = 4

CAPTURE_SCHEMA_TOPIC: dict[str, Any] = {
  "mode": "row_table",
  "min_rows": 1,
  "max_rows": 20,
  "columns": [
    {"key": "title", "label": "选题标题", "type": "text", "required": True},
    {"key": "content", "label": "选题内容", "type": "textarea"},
    {"key": "reason", "label": "选题理由", "type": "textarea"},
  ],
  "storage": "deliverable_payload",
  "completion_policy": "on_capture_submitted",
}

AGGREGATE_SCHEMA_TOPIC: dict[str, Any] = {
  "mode": "submission_matrix",
  "source_node_key": "N1_PROPOSE",
  "row_id_field": "topic_id",
  "row_actions": ["approve", "reject"],
  "assignee_column": {"key": "script_author_id", "label": "脚本撰写人", "type": "user"},
  "on_confirm": {
    "action": "finalize_topics_and_fork",
    "child_template_code": VIDEO_PRODUCTION_CODE,
    "idempotency_key": "topic_id",
  },
}

LAUNCH_SCHEMA_TOPIC: dict[str, Any] = {
  "fields": [
    {"key": "theme", "label": "征集主题", "type": "text", "required": True},
    {"key": "manager_user_id", "label": "负责人", "type": "user", "required": True},
    {"key": "due_at", "label": "截止", "type": "datetime"},
  ]
}

EDIT_ASSIGN_CAPTURE_SCHEMA: dict[str, Any] = {
  "mode": "row_table",
  "min_rows": 1,
  "max_rows": 1,
  "columns": [
    {"key": "edit_assignee_id", "label": "剪辑师", "type": "user", "required": True, "pool_key": "post_production"},
  ],
  "storage": "deliverable_payload",
  "completion_policy": "on_capture_submitted",
}

SCHEDULE_CAPTURE_SCHEMA: dict[str, Any] = {
  "mode": "row_table",
  "min_rows": 1,
  "max_rows": 1,
  "columns": [
    {"key": "publish_at", "label": "发布时间", "type": "datetime", "required": True},
    {"key": "platform", "label": "发布平台", "type": "text", "required": True},
    {"key": "publish_title", "label": "标题", "type": "text", "required": True},
  ],
  "storage": "deliverable_payload",
  "completion_policy": "on_capture_submitted",
}


def build_topic_meeting_batch_config(
  *,
  copywriting_department_id: UUID,
) -> dict[str, Any]:
  return {
    "seed_version": SEED_VERSION,
    "run_kind": "batch",
    "aggregate_mode": "streaming",
    "aggregate_node_key": "N2_AGGREGATE",
    "child_template_code": VIDEO_PRODUCTION_CODE,
    "launch_schema": LAUNCH_SCHEMA_TOPIC,
    "root_assignee_var": "manager_user_id",
    "participant_policies": {
      "copywriters": {
        "type": "department_members",
        "department_id": str(copywriting_department_id),
      },
    },
  }


def build_production_template_config(
  *,
  copywriting_department_id: UUID,
  voice_department_id: UUID,
  post_department_id: UUID,
) -> dict[str, Any]:
  return {
    "seed_version": SEED_VERSION,
    "run_kind": "production",
    "root_assignee_var": "script_author_id",
    "department_pools": {
      "copywriters": str(copywriting_department_id),
      "voice_over": str(voice_department_id),
      "post_production": str(post_department_id),
    },
  }


def build_topic_meeting_nodes() -> list[dict[str, Any]]:
  return [
    {
      "node_key": "N1_PROPOSE",
      "title": "提交选题",
      "sort_order": 1,
      "assignee_rule": {},
      "config": {
        "kind": "multi_instance",
        "expand_from": "copywriters",
        "participant_policy_ref": "copywriters",
        "capture_schema": CAPTURE_SCHEMA_TOPIC,
        "ui_profile": "video_n1_capture",
      },
    },
    {
      "node_key": "N2_AGGREGATE",
      "title": "汇总派发",
      "sort_order": 2,
      "assignee_rule": {"type": "context_var", "var": "manager_user_id"},
      "config": {
        "kind": "single",
        "aggregate_schema": AGGREGATE_SCHEMA_TOPIC,
        "completion_policy": "on_aggregate_confirmed",
        "ui_profile": "video_n2_aggregate",
      },
    },
  ]


def build_production_nodes() -> list[dict[str, Any]]:
  return [
    {
      "node_key": "N3_SCRIPT_WRITE",
      "title": "撰写脚本",
      "sort_order": 10,
      "assignee_rule": {"type": "context_var", "var": "script_author_id"},
      "config": {"kind": "single", "completion_policy": "on_submit_deliverable", "ui_profile": "video_production_step"},
    },
    {
      "node_key": "N4_SCRIPT_REVIEW",
      "title": "脚本审核",
      "sort_order": 20,
      "assignee_rule": {"type": "department_pool", "pool_key": "copywriters", "assignee_role": "manager"},
      "config": {
        "kind": "single",
        "acceptance_spec": {"reject_to": {"node_key": "N3_SCRIPT_WRITE"}},
        "completion_policy": "on_review_approved",
      },
    },
    {
      "node_key": "N5_VO_UPLOAD",
      "title": "配音审核并上传",
      "sort_order": 30,
      "assignee_rule": {"type": "context_var", "var": "script_author_id"},
      "config": {
        "kind": "single",
        "completion_policy": "on_submit_deliverable",
        "ui_profile": "video_production_multi",
        "max_deliverable_attachments": 10,
      },
    },
    {
      "node_key": "N7_EDIT_ASSIGN",
      "title": "指派剪辑",
      "sort_order": 50,
      "assignee_rule": {"type": "department_pool", "pool_key": "post_production", "assignee_role": "manager"},
      "config": {
        "kind": "single",
        "capture_schema": EDIT_ASSIGN_CAPTURE_SCHEMA,
        "ui_profile": "video_capture_assign",
      },
    },
    {
      "node_key": "N8_EDIT_WORK",
      "title": "粗剪制作",
      "sort_order": 60,
      "assignee_rule": {"type": "context_var", "var": "edit_assignee_id"},
      "config": {"kind": "single", "completion_policy": "on_submit_deliverable", "ui_profile": "video_production_step"},
    },
    {
      "node_key": "N9_EDIT_REVIEW",
      "title": "粗剪审核",
      "sort_order": 70,
      "assignee_rule": {"type": "context_var", "var": "script_author_id"},
      "config": {
        "kind": "single",
        "acceptance_spec": {"reject_to": {"node_key": "N8_EDIT_WORK"}},
        "completion_policy": "on_review_approved",
      },
    },
    {
      "node_key": "N10_UPLOAD",
      "title": "上传平台",
      "sort_order": 80,
      "assignee_rule": {"type": "context_var", "var": "edit_assignee_id"},
      "config": {
        "kind": "single",
        "completion_policy": "on_submit_deliverable",
        "ui_profile": "video_production_platform",
      },
    },
    {
      "node_key": "N11_SCHEDULE",
      "title": "排期发布",
      "sort_order": 90,
      "assignee_rule": {"type": "department_pool", "pool_key": "post_production", "assignee_role": "manager"},
      "config": {
        "kind": "single",
        "capture_schema": SCHEDULE_CAPTURE_SCHEMA,
        "ui_profile": "video_capture_schedule",
      },
    },
    {
      "node_key": "N12_CLOSE",
      "title": "结案确认",
      "sort_order": 100,
      "assignee_rule": {"type": "department_pool", "pool_key": "post_production", "assignee_role": "manager"},
      "config": {"kind": "single", "completion_policy": "on_review_approved"},
    },
    {
      "node_key": "N12_COSIGN",
      "title": "文案会签归档",
      "sort_order": 110,
      "assignee_rule": {"type": "department_pool", "pool_key": "copywriters", "assignee_role": "manager"},
      "config": {"kind": "single", "completion_policy": "on_review_approved", "archive_on_complete": True},
    },
  ]


def build_topic_meeting_edges() -> list[tuple[str, str, bool]]:
  return [("N1_PROPOSE", "N2_AGGREGATE", False)]


def build_production_edges() -> list[tuple[str, str, bool]]:
  return [
    ("N3_SCRIPT_WRITE", "N4_SCRIPT_REVIEW", False),
    ("N4_SCRIPT_REVIEW", "N5_VO_UPLOAD", False),
    ("N5_VO_UPLOAD", "N7_EDIT_ASSIGN", False),
    ("N7_EDIT_ASSIGN", "N8_EDIT_WORK", False),
    ("N8_EDIT_WORK", "N9_EDIT_REVIEW", False),
    ("N9_EDIT_REVIEW", "N10_UPLOAD", False),
    ("N10_UPLOAD", "N11_SCHEDULE", False),
    ("N11_SCHEDULE", "N12_CLOSE", False),
    ("N12_CLOSE", "N12_COSIGN", False),
    ("N4_SCRIPT_REVIEW", "N3_SCRIPT_WRITE", True),
    ("N9_EDIT_REVIEW", "N8_EDIT_WORK", True),
  ]
