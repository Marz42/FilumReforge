from datetime import timezone

import pytest

from app.scripts.audit_ki014_schema_compatibility import (
  _find_index_names,
  evaluate_automated_gates,
  parse_args,
  summarize_status_rows,
)


def _passing_report() -> dict[str, object]:
  status = {
    "counts": {"todo": 2, "blocked": 1},
    "row_count": 3,
    "unknown_count": 0,
    "noncanonical_case_count": 0,
  }
  return {
    "database": {"transaction_read_only": "on", "revision": "20260827_01"},
    "task_statuses": {
      "all": {
        "tasks.status": status,
        "task_logs.from_status": status,
        "task_logs.to_status": status,
      },
      "observation_window": {
        "tasks.status": status,
        "task_logs.from_status": status,
        "task_logs.to_status": status,
      },
    },
    "workflow_nulls": {
      "all": {
        "workflow_graph_templates.scope_mode": 0,
        "workflow_graph_instances.engine_version": 0,
        "workflow_graph_instances.executor_kind": 0,
      },
      "observation_window": {
        "workflow_graph_templates.scope_mode": 0,
        "workflow_graph_instances.engine_version": 0,
        "workflow_graph_instances.executor_kind": 0,
      },
    },
    "constraints": {"missing": [], "unvalidated": []},
    "invitation_index": {
      "exists": True,
      "valid": True,
      "ready": True,
      "planner_eligible": True,
    },
  }


def test_summarize_status_rows_distinguishes_case_from_unknown_values() -> None:
  summary = summarize_status_rows(
    [
      {"value": "todo", "count": 2},
      {"value": "BLOCKED", "count": 3},
      {"value": "paused", "count": 5},
    ]
  )

  assert summary == {
    "counts": {"todo": 2, "BLOCKED": 3, "paused": 5},
    "row_count": 10,
    "unknown_count": 5,
    "noncanonical_case_count": 3,
  }


def test_evaluate_automated_gates_rejects_new_uppercase_writes() -> None:
  report = _passing_report()
  report["task_statuses"]["observation_window"]["tasks.status"] = {
    "counts": {"TODO": 1},
    "row_count": 1,
    "unknown_count": 0,
    "noncanonical_case_count": 1,
  }

  gates = evaluate_automated_gates(report, "20260827_01")

  assert all(gate["passed"] for gate in gates if gate["name"] != "observation_window_status_writes")
  assert next(gate for gate in gates if gate["name"] == "observation_window_status_writes")[
    "passed"
  ] is False


def test_evaluate_automated_gates_accepts_clean_report() -> None:
  assert all(gate["passed"] for gate in evaluate_automated_gates(_passing_report(), "20260827_01"))


def test_parse_args_requires_timezone_aware_since() -> None:
  with pytest.raises(SystemExit):
    parse_args(["--since", "2026-08-27T20:00:00"])

  args = parse_args(["--since", "2026-08-27T20:00:00+08:00"])

  assert args.since.utcoffset() == timezone.utc.utcoffset(None) + args.since.utcoffset()


def test_find_index_names_walks_nested_json_plan() -> None:
  plan = [{"Plan": {"Node Type": "Bitmap Heap Scan", "Plans": [{"Index Name": "expected"}]}}]

  assert _find_index_names(plan) == {"expected"}
