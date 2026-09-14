from __future__ import annotations

import time
from types import SimpleNamespace
from uuid import uuid4

from app.services.department_service import DepartmentService


def _fake_department(*, name: str, code: str, parent_id=None, sort_order: int = 0):
  return SimpleNamespace(
    id=uuid4(),
    name=name,
    code=code,
    parent_id=parent_id,
    manager_id=None,
    sort_order=sort_order,
    is_active=True,
    capabilities=[],
  )


def test_department_build_tree_scales_for_deep_and_wide_sample() -> None:
  """W12-C: measure in-memory build_tree on a realistic-scale synthetic sample."""
  root = _fake_department(name="Root", code="root")
  departments = [root]
  # 20 branches × 25 depth ≈ 500 nodes (plus root)
  for branch in range(20):
    parent = root
    for depth in range(25):
      node = _fake_department(
        name=f"B{branch}-D{depth}",
        code=f"b{branch}_d{depth}",
        parent_id=parent.id,
        sort_order=depth,
      )
      departments.append(node)
      parent = node

  assert len(departments) == 1 + 20 * 25

  started = time.perf_counter()
  tree = DepartmentService.build_tree(departments)  # type: ignore[arg-type]
  elapsed_ms = (time.perf_counter() - started) * 1000

  assert len(tree) == 1
  assert tree[0]["code"] == "root"
  # Evidence gate: pure CPU tree build should stay well under 50ms for ~500 nodes.
  assert elapsed_ms < 50, f"build_tree too slow: {elapsed_ms:.2f}ms"

  # Count nodes in tree
  def count(nodes: list[dict]) -> int:
    total = 0
    for node in nodes:
      total += 1 + count(node["children"])
    return total

  assert count(tree) == len(departments)
