"""W1 contract tests: video workflow schemas and graph model fields."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.workflow_video import (
  AggregateSchema,
  ApprovedTopic,
  CaptureSchema,
  LaunchSchema,
  ParticipantsSnapshotEntry,
  WorkflowGraphTemplateNodeConfigSchema,
  validate_aggregate_schema,
  validate_capture_schema,
  validate_launch_schema,
  validate_node_config,
  validate_run_context,
)


def test_w1_launch_schema_requires_fields() -> None:
  with pytest.raises(ValidationError):
    LaunchSchema.model_validate({"fields": []})
  parsed = validate_launch_schema(
    {
      "fields": [
        {"key": "theme", "label": "主题", "type": "text", "required": True},
        {"key": "copywriters", "label": "参与人", "type": "user_multi", "policy_ref": "copywriters"},
      ]
    }
  )
  assert len(parsed.fields) == 2


def test_w1_capture_schema_rejects_invalid_row_bounds() -> None:
  with pytest.raises(ValidationError, match="max_rows"):
    CaptureSchema.model_validate(
      {
        "min_rows": 5,
        "max_rows": 2,
        "columns": [{"key": "title", "label": "标题", "type": "text", "required": True}],
      }
    )


def test_w1_aggregate_schema_requires_source_and_fork_child() -> None:
  with pytest.raises(ValidationError):
    validate_aggregate_schema(
      {
        "source_node_key": "",
        "on_confirm": {"action": "advance_only"},
      }
    )
  with pytest.raises(ValidationError, match="child_template_code"):
    validate_aggregate_schema(
      {
        "source_node_key": "N1_PROPOSE",
        "on_confirm": {"action": "finalize_topics_and_fork", "idempotency_key": "topic_id"},
      }
    )
  parsed = validate_aggregate_schema(
    {
      "source_node_key": "N1_PROPOSE",
      "assignee_column": {"key": "script_author_id", "label": "撰写人", "type": "user"},
      "on_confirm": {
        "action": "finalize_topics_and_fork",
        "child_template_code": "video_production_per_topic_v1",
        "idempotency_key": "topic_id",
      },
    }
  )
  assert parsed.source_node_key == "N1_PROPOSE"


def test_w1_node_config_multi_instance_requires_expand_from() -> None:
  with pytest.raises(ValidationError, match="expand_from"):
    validate_node_config({"kind": "multi_instance"})


def test_w1_node_config_rejects_capture_and_aggregate_together() -> None:
  with pytest.raises(ValidationError, match="capture_schema"):
    validate_node_config(
      {
        "kind": "single",
        "capture_schema": {
          "columns": [{"key": "title", "label": "标题", "type": "text", "required": True}],
        },
        "aggregate_schema": {
          "source_node_key": "N1",
          "on_confirm": {"action": "advance_only"},
        },
      }
    )


def test_w1_participants_snapshot_subset_requires_users() -> None:
  with pytest.raises(ValidationError, match="subset"):
    ParticipantsSnapshotEntry.model_validate({"mode": "subset", "user_ids": []})


def test_w1_run_context_parses_batch_and_approved_topics() -> None:
  author_id = uuid4()
  topic_id = uuid4()
  parsed = validate_run_context(
    {
      "run_kind": "batch",
      "run_label": "第12周选题会",
      "participants_snapshot": {
        "copywriters": {"mode": "subset", "user_ids": [str(author_id)]},
      },
      "approved_topics": [
        {
          "topic_id": str(topic_id),
          "title": "年味",
          "script_author_id": str(author_id),
        }
      ],
      "fork_status": "pending",
    }
  )
  assert parsed.run_kind == "batch"
  assert len(parsed.approved_topics) == 1
  assert parsed.approved_topics[0].title == "年味"


def test_w1_migration_module_declares_revision_chain() -> None:
  import importlib.util
  from pathlib import Path

  migration_path = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260522_01_workflow_video_v1_foundation.py"
  )
  spec = importlib.util.spec_from_file_location("workflow_video_v1_migration", migration_path)
  assert spec and spec.loader
  migration = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(migration)
  assert migration.revision == "20260522_01"
  assert migration.down_revision == "20260519_01"


def test_w1_workflow_graph_models_expose_new_columns() -> None:
  from app.models.workflow_graph import WorkflowGraphInstance, WorkflowNodeInstance

  assert "run_label" in WorkflowGraphInstance.__table__.columns
  assert "parent_instance_id" in WorkflowGraphInstance.__table__.columns
  assert "instance_key" in WorkflowNodeInstance.__table__.columns
