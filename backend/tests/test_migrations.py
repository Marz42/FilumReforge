from __future__ import annotations

import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


BASE_DIR = Path(__file__).resolve().parents[1]
POSTGRES_IDENTIFIER_MAX_LENGTH = 63
MIGRATION_IDENTIFIER_PATTERNS = (
  re.compile(r'name="([^"]+)"'),
  re.compile(r'create_index\(\s*"([^"]+)"'),
  re.compile(r'drop_index\(\s*"([^"]+)"'),
)


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


def test_alembic_upgrade_and_downgrade(tmp_path, monkeypatch) -> None:
  db_path = tmp_path / "phase1_migration.db"
  async_url = f"sqlite+aiosqlite:///{db_path}"
  sync_url = f"sqlite:///{db_path}"

  monkeypatch.setenv("POSTGRES_DSN", async_url)

  alembic_config = Config(str(BASE_DIR / "alembic.ini"))
  alembic_config.set_main_option("script_location", str(BASE_DIR / "alembic"))

  command.upgrade(alembic_config, "head")

  upgraded_tables = set(inspect(create_engine(sync_url)).get_table_names())
  assert {
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
    "workflow_deliverables",
    "workflow_outbox_events",
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
  }.issubset(upgraded_tables)

  command.downgrade(alembic_config, "base")

  downgraded_tables = set(inspect(create_engine(sync_url)).get_table_names())
  assert "users" not in downgraded_tables
