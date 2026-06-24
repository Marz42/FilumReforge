"""W0 baseline tests for workflow-video-v1 (docs, flags, policy)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.workflow_video_policy import (
  use_graph_template_instantiation,
  use_legacy_task_template_instantiation,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
VIDEO_V1_PLAN = REPO_ROOT / "memory-bank" / "plans" / "workflow-video-v1-implementation-plan.md"
VIDEO_V1_W0_ADR = REPO_ROOT / "memory-bank" / "plans" / "workflow-video-v1-w0-adr.md"


def test_w0_video_v1_plan_document_exists_and_covers_batch_fork_and_form_engine() -> None:
  assert VIDEO_V1_PLAN.is_file(), "workflow-video-v1 implementation plan must exist"
  text = VIDEO_V1_PLAN.read_text(encoding="utf-8")
  assert "topic_meeting_batch_v1" in text
  assert "video_production_per_topic_v1" in text
  assert "capture_schema" in text
  assert "aggregate_schema" in text
  assert "finalize_topics_and_fork" in text or "fork_production_runs" in text
  assert "无单独" in text or "无独立" in text


def test_w0_adr_document_exists() -> None:
  assert VIDEO_V1_W0_ADR.is_file()


def test_w0_graph_template_engine_defaults_false() -> None:
  settings = Settings(jwt_secret_key="test-jwt-secret-key-for-suite-123456")
  assert settings.workflow_graph_template_engine_enabled is False
  assert use_graph_template_instantiation(settings) is False


def test_w0_graph_template_engine_can_be_enabled_via_settings() -> None:
  settings = Settings(
    jwt_secret_key="test-jwt-secret-key-for-suite-123456",
    workflow_graph_template_engine_enabled=True,
  )
  assert use_graph_template_instantiation(settings) is True


def test_w0_legacy_task_template_instantiation_disabled_after_b12() -> None:
  settings = Settings(
    jwt_secret_key="test-jwt-secret-key-for-suite-123456",
    workflow_graph_template_engine_enabled=True,
  )
  assert use_legacy_task_template_instantiation(settings) is False


@pytest.mark.parametrize(
  "env_value,expected",
  [
    ("true", True),
    ("false", False),
    ("1", True),
    ("0", False),
  ],
)
def test_w0_graph_template_engine_env_parsing(
  monkeypatch: pytest.MonkeyPatch,
  env_value: str,
  expected: bool,
) -> None:
  monkeypatch.setenv("WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED", env_value)
  monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-for-suite-123456")
  from app.core.config import Settings as FreshSettings

  settings = FreshSettings()
  assert settings.workflow_graph_template_engine_enabled is expected
