from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


BASE_DIR = Path(__file__).resolve().parents[1]


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
    "refresh_tokens",
    "attachments",
    "attachment_links",
    "tasks",
    "task_dependencies",
    "notification_messages",
    "notification_deliveries",
  }.issubset(upgraded_tables)

  command.downgrade(alembic_config, "base")

  downgraded_tables = set(inspect(create_engine(sync_url)).get_table_names())
  assert "users" not in downgraded_tables
