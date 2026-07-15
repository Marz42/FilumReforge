from __future__ import annotations

import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.core.config import get_settings
from tests.postgres_migration_support import (
  drop_ephemeral_database,
  list_public_tables,
  postgres_admin_dsn,
  postgres_tests_required,
  provision_ephemeral_database,
  run_async,
)


BASE_DIR = Path(__file__).resolve().parents[1]
POSTGRES_IDENTIFIER_MAX_LENGTH = 63
MIGRATION_IDENTIFIER_PATTERNS = (
  re.compile(r'name="([^"]+)"'),
  re.compile(r'create_index\(\s*"([^"]+)"'),
  re.compile(r'drop_index\(\s*"([^"]+)"'),
)

EXPECTED_UPGRADED_TABLES = {
  "users",
  "departments",
  "profiles",
  "positions",
  "profile_positions",
  "reporting_lines",
  "profile_field_definitions",
  "profile_field_permissions",
  "employment_events",
  "delegations",
  "task_templates",
  "task_template_steps",
  "task_template_step_dependencies",
  "workflow_definitions",
  "workflow_graph_templates",
  "workflow_graph_template_nodes",
  "workflow_graph_template_edges",
  "workflow_graph_instances",
  "workflow_node_instances",
  "workflow_edge_traversals",
  "workflow_node_activation_dependencies",
  "workflow_human_task_links",
  "workflow_command_receipts",
  "workflow_deliverables",
  "workflow_outbox_events",
  "workflow_run_events",
  "workflow_steps",
  "workflow_instances",
  "workflow_step_runs",
  "task_watchers",
  "task_schedules",
  "notification_receipts",
  "refresh_tokens",
  "attachments",
  "attachment_links",
  "tasks",
  "task_dependencies",
  "task_comments",
  "task_logs",
  "notification_messages",
  "notification_deliveries",
  "documents",
  "document_embeddings",
  "push_subscriptions",
  "board_cards",
  "board_card_archives",
  "announcements",
  "announcement_archives",
  "task_memos",
  "reports",
  "report_routes",
  "error_events",
}


def test_alembic_identifier_names_fit_postgresql_limit() -> None:
  invalid_names: dict[str, int] = {}
  versions_dir = BASE_DIR / "alembic" / "versions"

  for revision_path in versions_dir.glob("*.py"):
    content = revision_path.read_text(encoding="utf-8")
    for pattern in MIGRATION_IDENTIFIER_PATTERNS:
      for name in pattern.findall(content):
        if len(name) > POSTGRES_IDENTIFIER_MAX_LENGTH:
          invalid_names[f"{revision_path.name}:{name}"] = len(name)

  assert invalid_names == {}


@pytest.mark.postgres
def test_alembic_upgrade_and_downgrade(monkeypatch: pytest.MonkeyPatch) -> None:
  """Run Alembic head↔base on ephemeral PostgreSQL (production dialect)."""
  admin_dsn = postgres_admin_dsn()
  try:
    async_dsn, sync_dsn, database_name = run_async(provision_ephemeral_database(admin_dsn))
  except Exception as exc:
    if postgres_tests_required():
      pytest.fail(f"Required PostgreSQL test database is unavailable: {type(exc).__name__}: {exc}")
    pytest.skip(f"PostgreSQL unavailable at {admin_dsn}: {exc}")

  monkeypatch.setenv("POSTGRES_DSN", async_dsn)
  get_settings.cache_clear()

  alembic_config = Config(str(BASE_DIR / "alembic.ini"))
  alembic_config.set_main_option("script_location", str(BASE_DIR / "alembic"))

  try:
    command.upgrade(alembic_config, "head")

    upgraded_tables = run_async(list_public_tables(sync_dsn))
    assert EXPECTED_UPGRADED_TABLES.issubset(upgraded_tables)

    command.downgrade(alembic_config, "base")

    downgraded_tables = run_async(list_public_tables(sync_dsn))
    assert "users" not in downgraded_tables
  finally:
    get_settings.cache_clear()
    run_async(drop_ephemeral_database(admin_dsn, database_name))
