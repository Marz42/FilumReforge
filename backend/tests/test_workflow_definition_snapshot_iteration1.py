from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.enums import (
  WorkflowGraphInstanceStatus,
  WorkflowGraphNodeType,
  WorkflowGraphTemplateStatus,
)
from app.core.exceptions import ConflictError
from app.models import (
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateEdge,
  WorkflowGraphTemplateNode,
)
from app.services.auth_service import AuthService
from app.services.workflow_definition_snapshot import (
  build_definition_snapshot,
  definition_snapshot_hash,
  ensure_template_scope_allows_department,
)
from app.services.workflow_graph_service import WorkflowGraphService
from app.core.config import Settings
from app.scripts.report_workflow_legacy_runs import build_legacy_run_report


def _definition_objects():
  template = WorkflowGraphTemplate(
    id=uuid4(),
    code="canonical_v1",
    base_code="canonical",
    version=1,
    name="Canonical",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    config={"z": 1, "a": {"enabled": True}},
    context_schema={"type": "object"},
    scope_mode="global",
    scope_department_ids=[],
    created_by=uuid4(),
  )
  node_a = WorkflowGraphTemplateNode(
    id=uuid4(),
    template_id=template.id,
    node_key="A",
    title="A",
    node_type=WorkflowGraphNodeType.TASK,
    sort_order=1,
    assignee_rule={},
    config={"kind": "single"},
  )
  node_b = WorkflowGraphTemplateNode(
    id=uuid4(),
    template_id=template.id,
    node_key="B",
    title="B",
    node_type=WorkflowGraphNodeType.APPROVAL,
    sort_order=2,
    assignee_rule={},
    config={},
  )
  edge = WorkflowGraphTemplateEdge(
    id=uuid4(),
    template_id=template.id,
    from_node_id=node_a.id,
    to_node_id=node_b.id,
    condition={"field": "approved", "operator": "eq", "value": True},
    priority=5,
  )
  return template, node_a, node_b, edge


def test_canonical_snapshot_hash_is_stable_and_edges_use_node_keys() -> None:
  template, node_a, node_b, edge = _definition_objects()
  first = build_definition_snapshot(template=template, nodes=[node_b, node_a], edges=[edge])
  second = build_definition_snapshot(template=template, nodes=[node_a, node_b], edges=[edge])

  assert definition_snapshot_hash(first) == definition_snapshot_hash(second)
  assert first["edges"][0]["from_node_key"] == "A"
  assert first["edges"][0]["to_node_key"] == "B"
  assert "from_node_id" not in first["edges"][0]
  assert "to_node_id" not in first["edges"][0]

  node_b.title = "Changed"
  changed = build_definition_snapshot(template=template, nodes=[node_a, node_b], edges=[edge])
  assert definition_snapshot_hash(changed) != definition_snapshot_hash(first)


def test_explicit_department_scope_requires_final_department_match() -> None:
  template, _, _, _ = _definition_objects()
  allowed_department_id = uuid4()
  template.scope_mode = "departments"
  template.scope_department_ids = [str(allowed_department_id)]

  ensure_template_scope_allows_department(
    template=template,
    department_id=allowed_department_id,
  )
  with pytest.raises(ConflictError, match="不在该模板的作用范围"):
    ensure_template_scope_allows_department(template=template, department_id=uuid4())
  with pytest.raises(ConflictError, match="不在该模板的作用范围"):
    ensure_template_scope_allows_department(template=template, department_id=None)


@pytest.mark.asyncio
async def test_new_run_uses_snapshot_executor_and_legacy_report_is_read_only(db_session) -> None:
  admin = await AuthService(
    db_session,
    Settings(jwt_secret_key="iteration-1-snapshot-secret-32-bytes"),
  ).bootstrap_admin(
    email="iteration1-snapshot@example.com",
    password="StrongPassword123!",
    real_name="Iteration 1",
    employee_no="I1-SNAPSHOT",
  )
  template = WorkflowGraphTemplate(
    code="snapshot-run-v1",
    base_code="snapshot-run",
    version=1,
    name="Snapshot Run",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    scope_mode="global",
    scope_department_ids=[],
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()
  node = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="A",
    title="A",
    node_type=WorkflowGraphNodeType.TASK,
    sort_order=1,
  )
  db_session.add(node)
  await db_session.flush()

  result = await WorkflowGraphService(db_session).create_multi_node_instance(
    template_id=template.id,
    initiator_id=admin.id,
  )
  legacy = WorkflowGraphInstance(
    template_id=template.id,
    initiator_user_id=admin.id,
    status=WorkflowGraphInstanceStatus.ACTIVE,
    context={},
    executor_kind="legacy",
    engine_version="legacy-v1",
  )
  db_session.add(legacy)
  await db_session.commit()

  assert result.instance.executor_kind == "snapshot"
  assert result.instance.engine_version == "graph-v3"
  assert (result.instance.definition_snapshot or {}).get("format_version") == 2
  assert result.instance.definition_snapshot is not None
  assert len(result.instance.definition_hash or "") == 64

  report = await build_legacy_run_report(db_session)
  assert report.active_legacy_run_count == 1
  assert report.unprovable_definition_count == 1
  assert report.by_template_version[0].template_version == 1

  tampered_snapshot = dict(result.instance.definition_snapshot or {})
  tampered_snapshot["format_version"] = 999
  result.instance.definition_snapshot = tampered_snapshot
  await db_session.flush()
  with pytest.raises(ConflictError, match="快照校验失败"):
    await WorkflowGraphService(db_session).complete_node_instance(
      node_instance_id=result.node_instances[0].id,
      actor_id=admin.id,
    )
