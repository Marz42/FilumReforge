"""Read-only schema comparison; isolated mode creates and removes a fresh test database."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
EXPECTED_REVISION = "20260827_01"
EXPECTED_NULLABLE = {
    ("workflow_graph_templates", "scope_mode"),
    ("workflow_graph_instances", "engine_version"),
    ("workflow_graph_instances", "executor_kind"),
}


def classify_diffs(diffs, revision, allow_compatibility):
    flattened = [item for group in diffs for item in (group if isinstance(group, list) else [group])]
    expected = []
    unexpected = []
    for diff in flattened:
        if (allow_compatibility and revision == EXPECTED_REVISION
            and diff[0] == "modify_nullable" and len(diff) == 7
            and diff[1] in (None, "public") and (diff[2], diff[3]) in EXPECTED_NULLABLE
            and diff[5] is True and diff[6] is False):
            expected.append((diff[2], diff[3]))
        else:
            unexpected.append(str(diff[0]))
    # The exception belongs to this exact expand revision and exact three-column state.
    if allow_compatibility and revision == EXPECTED_REVISION and set(expected) != EXPECTED_NULLABLE:
        unexpected.append("compatibility_drift_set_mismatch")
    return {"revision": revision, "expected_nullable": sorted(expected),
            "unexpected_operations": unexpected, "schema_clean": not flattened,
            "passed": not unexpected}


async def inspect_schema(dsn, allow_compatibility):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.models import Base
    engine = create_async_engine(dsn)
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.execute(text("SET TRANSACTION READ ONLY"))
                revisions = (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalars().all()
                if len(revisions) != 1:
                    raise RuntimeError("database must have exactly one revision")
                diffs = await connection.run_sync(lambda sync: compare_metadata(
                    MigrationContext.configure(sync, opts={"compare_type": True}), Base.metadata))
                return classify_diffs(diffs, revisions[0], allow_compatibility)
    finally:
        await engine.dispose()


def run(isolated, allow_compatibility):
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    config = Config(str(ROOT / "backend/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend/alembic"))
    heads = ScriptDirectory.from_config(config).get_heads()
    if len(heads) != 1:
        raise RuntimeError("migration repository must have exactly one head")
    database_name = None
    admin = os.environ.get("POSTGRES_TEST_ADMIN_DSN", "")
    try:
        if isolated:
            if not admin:
                raise RuntimeError("POSTGRES_TEST_ADMIN_DSN must be explicit")
            from tests.postgres_migration_support import provision_ephemeral_database
            dsn, _, database_name = asyncio.run(provision_ephemeral_database(admin, prefix="filum_schema"))
            env = {**os.environ, "POSTGRES_DSN": dsn, "APP_ENV": "development"}
            result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                                    cwd=ROOT / "backend", env=env, capture_output=True, timeout=180)
            if result.returncode:
                raise RuntimeError("isolated schema migration failed")
        else:
            dsn = os.environ.get("POSTGRES_DSN", "")
            if not dsn:
                raise RuntimeError("POSTGRES_DSN must be explicit for read-only release inspection")
        report = asyncio.run(inspect_schema(dsn, allow_compatibility))
        report["passed"] = report["passed"] and report["revision"] == heads[0]
        print(json.dumps(report, sort_keys=True))
        return 0 if report["passed"] else 1
    finally:
        if database_name:
            from tests.postgres_migration_support import drop_ephemeral_database
            asyncio.run(drop_ephemeral_database(admin, database_name))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated", action="store_true")
    parser.add_argument("--allow-ki014-compatibility", action="store_true")
    args = parser.parse_args()
    try:
        raise SystemExit(run(args.isolated, args.allow_ki014_compatibility))
    except Exception as exc:
        print(f"Schema check failed ({type(exc).__name__}); no connection details printed", file=sys.stderr)
        raise SystemExit(1)
