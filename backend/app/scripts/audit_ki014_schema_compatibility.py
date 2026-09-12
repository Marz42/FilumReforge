"""Privacy-safe, transactionally read-only KI-014 compatibility audit."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

EXPECTED_REVISION = "20260827_01"
VALID_TASK_STATUSES = frozenset({"todo", "doing", "review", "blocked", "done"})
REQUIRED_CONSTRAINTS = frozenset(
  {
    "ck_tasks_status_compat_ki014",
    "ck_task_logs_from_status_compat_ki014",
    "ck_task_logs_to_status_compat_ki014",
    "ck_wf_graph_tpls_scope_mode_nn_ki014",
    "ck_wf_graph_instances_engine_version_nn_ki014",
    "ck_wf_graph_instances_executor_kind_nn_ki014",
  }
)
INVITATION_INDEX = "idx_users_invitation_token_hash"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description=(
      "Run the KI-014 aggregate audit inside a forced read-only PostgreSQL transaction. "
      "The report never includes task, user, token, or JSON payload data."
    )
  )
  parser.add_argument(
    "--since",
    type=_parse_timestamp,
    default=None,
    help="Optional timezone-aware ISO-8601 start of the compatibility observation window.",
  )
  parser.add_argument(
    "--dsn-env",
    default="POSTGRES_DSN",
    help="Name of the environment variable containing the target DSN (default: POSTGRES_DSN).",
  )
  parser.add_argument("--expected-revision", default=EXPECTED_REVISION)
  parser.add_argument(
    "--no-fail",
    action="store_true",
    help="Print failed automated gates without returning a non-zero exit code.",
  )
  return parser.parse_args(argv)


def _parse_timestamp(value: str) -> datetime:
  normalized = value.strip().replace("Z", "+00:00")
  parsed = datetime.fromisoformat(normalized)
  if parsed.tzinfo is None or parsed.utcoffset() is None:
    raise argparse.ArgumentTypeError("--since must include an explicit timezone offset")
  return parsed


def summarize_status_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
  counts = {str(row["value"]): int(row["count"]) for row in rows}
  unknown_count = sum(
    count for value, count in counts.items() if value.lower() not in VALID_TASK_STATUSES
  )
  uppercase_count = sum(count for value, count in counts.items() if value != value.lower())
  return {
    "counts": counts,
    "row_count": sum(counts.values()),
    "unknown_count": unknown_count,
    "noncanonical_case_count": uppercase_count,
  }


def _gate(name: str, passed: bool, detail: str) -> dict[str, Any]:
  return {"name": name, "passed": passed, "detail": detail}


def evaluate_automated_gates(report: Mapping[str, Any], expected_revision: str) -> list[dict[str, Any]]:
  database = report["database"]
  statuses = report["task_statuses"]
  workflow_nulls = report["workflow_nulls"]
  constraints = report["constraints"]
  invitation_index = report["invitation_index"]
  recent_statuses = statuses.get("observation_window")
  recent_nulls = workflow_nulls.get("observation_window")

  gates = [
    _gate(
      "read_only_transaction",
      database["transaction_read_only"] == "on",
      f"transaction_read_only={database['transaction_read_only']}",
    ),
    _gate(
      "expected_revision",
      database["revision"] == expected_revision,
      f"observed={database['revision']}; expected={expected_revision}",
    ),
    _gate(
      "known_status_values",
      all(item["unknown_count"] == 0 for item in statuses["all"].values()),
      "all persisted task status values must match the compatibility set case-insensitively",
    ),
    _gate(
      "workflow_nulls",
      all(int(value) == 0 for value in workflow_nulls["all"].values()),
      "all three KI-014 workflow metadata columns must contain no NULL values",
    ),
    _gate(
      "required_constraints",
      constraints["missing"] == [] and constraints["unvalidated"] == [],
      "all six KI-014 compatibility constraints must exist and be validated",
    ),
    _gate(
      "invitation_index",
      invitation_index["exists"]
      and invitation_index["valid"]
      and invitation_index["ready"]
      and invitation_index["planner_eligible"],
      "invitation token hash index must be valid, ready, and planner-eligible",
    ),
  ]
  if recent_statuses is not None:
    gates.append(
      _gate(
        "observation_window_status_writes",
        all(
          item["unknown_count"] == 0 and item["noncanonical_case_count"] == 0
          for item in recent_statuses.values()
        ),
        "status rows written or updated during the window must use canonical lowercase values",
      )
    )
  if recent_nulls is not None:
    gates.append(
      _gate(
        "observation_window_workflow_writes",
        all(int(value) == 0 for value in recent_nulls.values()),
        "workflow rows written or updated during the window must contain no KI-014 NULL values",
      )
    )
  return gates


async def _status_distribution(
  connection: AsyncConnection,
  *,
  table: str,
  column: str,
  timestamp_column: str,
  since: datetime | None,
) -> dict[str, Any]:
  where = f"WHERE {column} IS NOT NULL"
  parameters: dict[str, Any] = {}
  if since is not None:
    where += f" AND {timestamp_column} >= :since"
    parameters["since"] = since
  result = await connection.execute(
    text(
      f"SELECT {column}::text AS value, count(*) AS count "  # noqa: S608 - identifiers are constants
      f"FROM {table} {where} GROUP BY {column}::text ORDER BY value"
    ),
    parameters,
  )
  return summarize_status_rows(result.mappings().all())


async def _collect_statuses(
  connection: AsyncConnection,
  since: datetime | None,
) -> dict[str, Any]:
  definitions = {
    "tasks.status": ("tasks", "status", "updated_at"),
    "task_logs.from_status": ("task_logs", "from_status", "created_at"),
    "task_logs.to_status": ("task_logs", "to_status", "created_at"),
  }
  all_values = {
    name: await _status_distribution(
      connection,
      table=table,
      column=column,
      timestamp_column=timestamp_column,
      since=None,
    )
    for name, (table, column, timestamp_column) in definitions.items()
  }
  window_values = None
  if since is not None:
    window_values = {
      name: await _status_distribution(
        connection,
        table=table,
        column=column,
        timestamp_column=timestamp_column,
        since=since,
      )
      for name, (table, column, timestamp_column) in definitions.items()
    }
  return {"all": all_values, "observation_window": window_values}


async def _workflow_nulls(
  connection: AsyncConnection,
  since: datetime | None,
) -> dict[str, Any]:
  async def collect(window_start: datetime | None) -> dict[str, int]:
    template_filter = "" if window_start is None else " AND updated_at >= :since"
    instance_filter = "" if window_start is None else " AND updated_at >= :since"
    parameters = {} if window_start is None else {"since": window_start}
    template_nulls = await connection.scalar(
      text(
        "SELECT count(*) FROM workflow_graph_templates "
        f"WHERE scope_mode IS NULL{template_filter}"
      ),
      parameters,
    )
    instance_row = (
      await connection.execute(
        text(
          "SELECT "
          "count(*) FILTER (WHERE engine_version IS NULL) AS engine_version_nulls, "
          "count(*) FILTER (WHERE executor_kind IS NULL) AS executor_kind_nulls "
          "FROM workflow_graph_instances WHERE true"
          f"{instance_filter}"
        ),
        parameters,
      )
    ).mappings().one()
    return {
      "workflow_graph_templates.scope_mode": int(template_nulls or 0),
      "workflow_graph_instances.engine_version": int(instance_row["engine_version_nulls"]),
      "workflow_graph_instances.executor_kind": int(instance_row["executor_kind_nulls"]),
    }

  return {
    "all": await collect(None),
    "observation_window": await collect(since) if since is not None else None,
  }


def _find_index_names(plan: Any) -> set[str]:
  names: set[str] = set()
  if isinstance(plan, Mapping):
    name = plan.get("Index Name")
    if isinstance(name, str):
      names.add(name)
    for value in plan.values():
      names.update(_find_index_names(value))
  elif isinstance(plan, list):
    for value in plan:
      names.update(_find_index_names(value))
  return names


async def _invitation_index(connection: AsyncConnection) -> dict[str, Any]:
  row = (
    await connection.execute(
      text(
        "SELECT ix.indisvalid AS valid, ix.indisready AS ready "
        "FROM pg_index ix "
        "JOIN pg_class index_relation ON index_relation.oid = ix.indexrelid "
        "JOIN pg_class table_relation ON table_relation.oid = ix.indrelid "
        "JOIN pg_namespace namespace ON namespace.oid = table_relation.relnamespace "
        "WHERE namespace.nspname = current_schema() "
        "AND table_relation.relname = 'users' "
        "AND index_relation.relname = :index_name"
      ),
      {"index_name": INVITATION_INDEX},
    )
  ).mappings().one_or_none()
  await connection.execute(text("SET LOCAL enable_seqscan = off"))
  explain = await connection.scalar(
    text(
      "EXPLAIN (FORMAT JSON, COSTS OFF) "
      "SELECT id FROM users WHERE invitation_token_hash = repeat('0', 64)"
    )
  )
  index_names = sorted(_find_index_names(explain))
  return {
    "exists": row is not None,
    "valid": bool(row and row["valid"]),
    "ready": bool(row and row["ready"]),
    "planner_eligible": INVITATION_INDEX in index_names,
    "planner_indexes": index_names,
    "planner_note": "EXPLAIN used SET LOCAL enable_seqscan=off to prove eligibility, not production hit rate.",
  }


async def collect_audit(
  connection: AsyncConnection,
  *,
  since: datetime | None,
  expected_revision: str = EXPECTED_REVISION,
) -> dict[str, Any]:
  transaction = await connection.begin()
  try:
    await connection.execute(text("SET TRANSACTION READ ONLY"))
    read_only = str(await connection.scalar(text("SHOW transaction_read_only")))
    database_row = (
      await connection.execute(
        text(
          "SELECT current_schema() AS schema_name, "
          "current_setting('server_version_num') AS server_version_num"
        )
      )
    ).mappings().one()
    revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
    constraint_rows = (
      await connection.execute(
        text(
          "SELECT c.conname, c.convalidated "
          "FROM pg_constraint c "
          "WHERE c.conname = ANY(:constraint_names) ORDER BY c.conname"
        ),
        {"constraint_names": sorted(REQUIRED_CONSTRAINTS)},
      )
    ).mappings().all()
    found_constraints = {str(row["conname"]): bool(row["convalidated"]) for row in constraint_rows}
    task_statuses = await _collect_statuses(connection, since)
    all_status_rows = sum(item["row_count"] for item in task_statuses["all"].values())
    window_status_rows = (
      sum(item["row_count"] for item in task_statuses["observation_window"].values())
      if task_statuses["observation_window"] is not None
      else None
    )
    report: dict[str, Any] = {
      "report_schema_version": 1,
      "observed_at": datetime.now(timezone.utc).isoformat(),
      "observation_since": since.isoformat() if since is not None else None,
      "database": {
        "schema": database_row["schema_name"],
        "server_version_num": database_row["server_version_num"],
        "revision": str(revision),
        "transaction_read_only": read_only,
      },
      "evidence_scope": {
        "kind": "aggregate_data" if all_status_rows > 0 else "structure_only_empty_status_tables",
        "all_status_rows": all_status_rows,
        "observation_window_status_rows": window_status_rows,
        "representative_data_claimed": False,
      },
      "task_statuses": task_statuses,
      "workflow_nulls": await _workflow_nulls(connection, since),
      "constraints": {
        "found": found_constraints,
        "missing": sorted(REQUIRED_CONSTRAINTS - found_constraints.keys()),
        "unvalidated": sorted(name for name, valid in found_constraints.items() if not valid),
      },
      "invitation_index": await _invitation_index(connection),
      "manual_evidence_required": [
        "observation window covers at least one complete business cycle",
        "BLOCKED task creation, read, and task-log replay pass in the target application",
        "invitation authentication behavior has no regression under representative traffic",
        "deployment and Phase D approval are recorded by the responsible humans",
      ],
    }
    gates = evaluate_automated_gates(report, expected_revision)
    report["automated_gates"] = gates
    report["automated_gate_passed"] = all(gate["passed"] for gate in gates)
    report["phase_d_ready"] = False
    report["phase_d_ready_note"] = (
      "Automated database gates cannot replace a complete business-cycle observation and approval."
    )
    return report
  finally:
    await transaction.rollback()


async def _run(args: argparse.Namespace) -> dict[str, Any]:
  dsn = os.environ.get(args.dsn_env, "").strip()
  if not dsn:
    raise RuntimeError(f"environment variable {args.dsn_env} is not set")
  engine = create_async_engine(dsn, future=True)
  try:
    async with engine.connect() as connection:
      if connection.dialect.name != "postgresql":
        raise RuntimeError("KI-014 compatibility audit requires PostgreSQL")
      return await collect_audit(
        connection,
        since=args.since,
        expected_revision=args.expected_revision,
      )
  finally:
    await engine.dispose()


async def main(args: argparse.Namespace) -> None:
  report = await _run(args)
  print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
  if not args.no_fail and not report["automated_gate_passed"]:
    raise SystemExit(2)


if __name__ == "__main__":
  asyncio.run(main(parse_args()))
