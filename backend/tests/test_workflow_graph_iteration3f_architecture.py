from __future__ import annotations

import ast
from pathlib import Path

import pytest


APP_ROOT = Path(__file__).resolve().parents[1] / "app"
WORK_ITEM_OWNER_FILES = {
  "services/task_service.py",
  "services/work_item_write_service.py",
}
RUNTIME_OWNER_FILES = {
  "services/workflow_graph_service.py",
  "services/workflow_runtime_write_service.py",
  "services/workflow_node_config_helpers.py",
}
MIGRATION_EXCEPTIONS = {"services/legacy_task_graph_migration_service.py"}
COORDINATOR_FILE = "services/human_task_coordinator.py"

TASK_FIELDS = {
  "status",
  "assignee_id",
  "extra_metadata",
  "completed_at",
  "updated_at",
  "started_at",
  "parent_task_id",
}
NODE_FIELDS = {
  "engine_state",
  "business_state",
  "assignee_user_id",
  "config",
  "activated_at",
  "acknowledged_at",
  "completed_at",
  "terminated_at",
  "node_instance_version",
}


def _root_name(node: ast.expr) -> str | None:
  while isinstance(node, ast.Attribute):
    node = node.value
  return node.id if isinstance(node, ast.Name) else None


def _target_violations(
  target: ast.expr,
  *,
  relative_path: str,
  lineno: int,
) -> list[str]:
  if isinstance(target, (ast.Tuple, ast.List)):
    result: list[str] = []
    for item in target.elts:
      result.extend(_target_violations(item, relative_path=relative_path, lineno=lineno))
    return result
  if not isinstance(target, ast.Attribute):
    return []
  root = (_root_name(target) or "").lower()
  allowed_work_item = WORK_ITEM_OWNER_FILES | MIGRATION_EXCEPTIONS
  allowed_runtime = RUNTIME_OWNER_FILES | MIGRATION_EXCEPTIONS
  if "task" in root and target.attr in TASK_FIELDS and relative_path not in allowed_work_item:
    return [f"{relative_path}:{lineno} direct Work Item write {root}.{target.attr}"]
  if "node" in root and target.attr in NODE_FIELDS and relative_path not in allowed_runtime:
    return [f"{relative_path}:{lineno} direct Runtime node write {root}.{target.attr}"]
  return []


def _scan_source(source: str, *, relative_path: str) -> list[str]:
  tree = ast.parse(source)
  violations: list[str] = []
  function_stack: list[str] = []

  class Visitor(ast.NodeVisitor):
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
      function_stack.append(node.name)
      self.generic_visit(node)
      function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
      function_stack.append(node.name)
      self.generic_visit(node)
      function_stack.pop()

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
      for target in node.targets:
        violations.extend(
          _target_violations(target, relative_path=relative_path, lineno=node.lineno)
        )
      self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
      violations.extend(
        _target_violations(node.target, relative_path=relative_path, lineno=node.lineno)
      )
      self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:  # noqa: N802
      violations.extend(
        _target_violations(node.target, relative_path=relative_path, lineno=node.lineno)
      )
      self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
      constructor = node.func.id if isinstance(node.func, ast.Name) else None
      current_function = function_stack[-1] if function_stack else "<module>"
      if constructor == "Task" and relative_path not in WORK_ITEM_OWNER_FILES | MIGRATION_EXCEPTIONS:
        violations.append(
          f"{relative_path}:{node.lineno} Task constructor outside Work Item owner ({current_function})"
        )
      if constructor in {"WorkflowGraphInstance", "WorkflowNodeInstance"}:
        allowed = relative_path in RUNTIME_OWNER_FILES | MIGRATION_EXCEPTIONS
        ephemeral_assignee_probe = (
          relative_path == "services/workflow_video_instantiation_service.py"
          and current_function == "_resolve_node_assignee"
          and constructor == "WorkflowNodeInstance"
        )
        if not allowed and not ephemeral_assignee_probe:
          violations.append(
            f"{relative_path}:{node.lineno} {constructor} constructor outside Runtime owner "
            f"({current_function})"
          )
      if (
        relative_path in {COORDINATOR_FILE, "services/work_item_write_service.py", "services/workflow_runtime_write_service.py"}
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "commit"
      ):
        violations.append(f"{relative_path}:{node.lineno} owner/coordinator must be flush-only")
      self.generic_visit(node)

  Visitor().visit(tree)
  return violations


@pytest.mark.workflow_i4_gate
def test_i3f_production_write_ownership_is_enforced_across_app() -> None:
  violations: list[str] = []
  for path in sorted(APP_ROOT.rglob("*.py")):
    relative_path = path.relative_to(APP_ROOT).as_posix()
    violations.extend(_scan_source(path.read_text(encoding="utf-8"), relative_path=relative_path))
  assert violations == []


@pytest.mark.workflow_i4_gate
def test_i3f_architecture_scanner_rejects_new_cross_domain_writes() -> None:
  source = """
async def invalid(task, node_instance, session):
  task.status = 'done'
  node_instance.engine_state = 'completed'
  await session.commit()
"""
  violations = _scan_source(source, relative_path=COORDINATOR_FILE)
  assert any("direct Work Item write" in item for item in violations)
  assert any("direct Runtime node write" in item for item in violations)
  assert any("flush-only" in item for item in violations)
