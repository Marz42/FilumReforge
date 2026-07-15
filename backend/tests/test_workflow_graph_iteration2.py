from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.enums import (
  WorkflowGraphInstanceStatus,
  WorkflowGraphTemplateStatus,
  WorkflowNodeEngineState,
)
from app.core.exceptions import ConflictError
from app.models import (
  User,
  WorkflowEdgeTraversal,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateEdge,
  WorkflowGraphTemplateNode,
  WorkflowNodeActivationDependency,
  WorkflowNodeInstance,
  WorkflowRunEvent,
)
from app.services.auth_service import AuthService
from app.services.workflow_graph_service import MultiNodeWorkflowResult, WorkflowGraphService


@dataclass(slots=True)
class Iteration2Seed:
  actor: User
  template: WorkflowGraphTemplate
  nodes: dict[str, WorkflowGraphTemplateNode]


async def _seed_graph(
  db_session,
  *,
  node_keys: tuple[str, ...],
  edges: tuple[tuple[str, str, dict, int], ...],
  routing_modes: dict[str, str] | None = None,
  join_modes: dict[str, str] | None = None,
  node_configs: dict[str, dict] | None = None,
) -> Iteration2Seed:
  actor = await AuthService(
    db_session,
    Settings(jwt_secret_key="iteration-2-test-secret-key-32-bytes"),
  ).bootstrap_admin(
    email=f"iteration2-{uuid4().hex}@example.com",
    password="StrongPassword123!",
    real_name="Iteration 2",
    employee_no=f"I2-{uuid4().hex[:12]}",
  )
  code = f"iteration2-{uuid4().hex}"
  template = WorkflowGraphTemplate(
    code=code,
    base_code=code,
    version=1,
    name="Iteration 2 Path Semantics",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    scope_mode="global",
    scope_department_ids=[],
    created_by=actor.id,
  )
  db_session.add(template)
  await db_session.flush()

  routing_modes = routing_modes or {}
  join_modes = join_modes or {}
  node_configs = node_configs or {}
  nodes = {
    node_key: WorkflowGraphTemplateNode(
      template_id=template.id,
      node_key=node_key,
      title=node_key,
      routing_mode=routing_modes.get(node_key, "inclusive"),
      join_mode=join_modes.get(node_key, "all"),
      config=node_configs.get(node_key, {}),
      sort_order=index,
    )
    for index, node_key in enumerate(node_keys, start=1)
  }
  db_session.add_all(nodes.values())
  await db_session.flush()
  db_session.add_all(
    [
      WorkflowGraphTemplateEdge(
        template_id=template.id,
        from_node_id=nodes[from_key].id,
        to_node_id=nodes[to_key].id,
        condition=condition,
        priority=priority,
      )
      for from_key, to_key, condition, priority in edges
    ]
  )
  await db_session.commit()
  return Iteration2Seed(actor=actor, template=template, nodes=nodes)


async def _create_run(db_session, seed: Iteration2Seed, *, context: dict | None = None):
  return await WorkflowGraphService(db_session).create_multi_node_instance(
    template_id=seed.template.id,
    initiator_id=seed.actor.id,
    context=context,
  )


def _node(result: MultiNodeWorkflowResult, node_key: str, *, iteration: int = 1):
  return next(
    node
    for node in result.node_instances
    if node.node_key == node_key and node.iteration == iteration
  )


@pytest.mark.asyncio
async def test_exclusive_route_persists_taken_and_not_taken_evidence(db_session) -> None:
  seed = await _seed_graph(
    db_session,
    node_keys=("A", "B", "C"),
    edges=(
      ("A", "B", {"field": "route", "operator": "eq", "value": "B"}, 0),
      ("A", "C", {"else": True}, 1),
    ),
    routing_modes={"A": "exclusive"},
  )
  result = await _create_run(db_session, seed, context={"route": "B"})

  await WorkflowGraphService(db_session).complete_node_instance(
    node_instance_id=_node(result, "A").id,
    actor_id=seed.actor.id,
  )
  await db_session.refresh(_node(result, "B"))
  await db_session.refresh(_node(result, "C"))

  traversals = list(
    await db_session.scalars(
      select(WorkflowEdgeTraversal)
      .where(WorkflowEdgeTraversal.source_node_instance_id == _node(result, "A").id)
      .order_by(WorkflowEdgeTraversal.to_node_key)
    )
  )
  assert [(item.to_node_key, item.status) for item in traversals] == [
    ("B", "taken"),
    ("C", "not_taken"),
  ]
  assert traversals[0].context_version == 1
  assert traversals[0].evidence["reason"] == "exclusive_selected"
  assert _node(result, "B").engine_state == WorkflowNodeEngineState.ACTIVATED
  assert _node(result, "C").engine_state == WorkflowNodeEngineState.SKIPPED

  dependencies = list(
    await db_session.scalars(
      select(WorkflowNodeActivationDependency).where(
        WorkflowNodeActivationDependency.instance_id == result.instance.id,
      )
    )
  )
  assert len(dependencies) == 1
  assert dependencies[0].node_instance_id == _node(result, "B").id
  assert dependencies[0].source_node_instance_id == _node(result, "A").id
  assert dependencies[0].status == "satisfied"

  await WorkflowGraphService(db_session).complete_node_instance(
    node_instance_id=_node(result, "B").id,
    actor_id=seed.actor.id,
  )
  await db_session.refresh(result.instance)
  assert result.instance.status == WorkflowGraphInstanceStatus.COMPLETED
  assert result.instance.result == "success"


@pytest.mark.asyncio
async def test_inclusive_wait_all_waits_for_each_produced_branch(db_session) -> None:
  seed = await _seed_graph(
    db_session,
    node_keys=("A", "B", "C", "D"),
    edges=(
      ("A", "B", {"field": "amount", "operator": "gte", "value": 10}, 0),
      ("A", "C", {"field": "urgent", "operator": "eq", "value": True}, 1),
      ("B", "D", {}, 0),
      ("C", "D", {}, 0),
    ),
    routing_modes={"A": "inclusive"},
    join_modes={"D": "all"},
  )
  result = await _create_run(db_session, seed, context={"amount": 20, "urgent": True})
  service = WorkflowGraphService(db_session)

  await service.complete_node_instance(node_instance_id=_node(result, "A").id, actor_id=seed.actor.id)
  await service.complete_node_instance(node_instance_id=_node(result, "B").id, actor_id=seed.actor.id)
  await db_session.refresh(_node(result, "D"))
  assert _node(result, "D").engine_state == WorkflowNodeEngineState.PENDING

  await service.complete_node_instance(node_instance_id=_node(result, "C").id, actor_id=seed.actor.id)
  await db_session.refresh(_node(result, "D"))
  assert _node(result, "D").engine_state == WorkflowNodeEngineState.ACTIVATED

  dependencies = list(
    await db_session.scalars(
      select(WorkflowNodeActivationDependency).where(
        WorkflowNodeActivationDependency.node_instance_id == _node(result, "D").id,
        WorkflowNodeActivationDependency.status == "satisfied",
      )
    )
  )
  assert {item.source_node_instance_id for item in dependencies} == {
    _node(result, "B").id,
    _node(result, "C").id,
  }


@pytest.mark.parametrize(
  ("routing_mode", "expected_active"),
  [("first_match", {"B"}), ("parallel", {"B", "C"})],
)
@pytest.mark.asyncio
async def test_routing_modes_have_explicit_selection_semantics(
  db_session,
  routing_mode: str,
  expected_active: set[str],
) -> None:
  seed = await _seed_graph(
    db_session,
    node_keys=("A", "B", "C"),
    edges=(("A", "B", {}, 0), ("A", "C", {}, 1)),
    routing_modes={"A": routing_mode},
  )
  result = await _create_run(db_session, seed)

  await WorkflowGraphService(db_session).complete_node_instance(
    node_instance_id=_node(result, "A").id,
    actor_id=seed.actor.id,
  )
  for node_key in ("B", "C"):
    await db_session.refresh(_node(result, node_key))
  assert {
    node_key
    for node_key in ("B", "C")
    if _node(result, node_key).engine_state == WorkflowNodeEngineState.ACTIVATED
  } == expected_active


@pytest.mark.asyncio
async def test_context_patch_requires_current_version_and_writes_diff_event(db_session) -> None:
  seed = await _seed_graph(
    db_session,
    node_keys=("A", "B", "C"),
    edges=(("A", "B", {}, 0), ("B", "C", {}, 0)),
  )
  result = await _create_run(db_session, seed, context={"amount": 10})
  service = WorkflowGraphService(db_session)

  await service.complete_node_instance(
    node_instance_id=_node(result, "A").id,
    actor_id=seed.actor.id,
    context_updates={"amount": 20},
    expected_context_version=1,
  )
  await db_session.refresh(result.instance)
  assert result.instance.context_version == 2

  event = await db_session.scalar(
    select(WorkflowRunEvent).where(
      WorkflowRunEvent.instance_id == result.instance.id,
      WorkflowRunEvent.event_type == "context_patched",
    )
  )
  assert event is not None
  assert event.payload["diff"] == {"amount": {"before": 10, "after": 20}}

  with pytest.raises(ConflictError, match="Context version 冲突"):
    await service.complete_node_instance(
      node_instance_id=_node(result, "B").id,
      actor_id=seed.actor.id,
      context_updates={"amount": 30},
      expected_context_version=1,
    )
  await db_session.rollback()


@pytest.mark.asyncio
async def test_deep_reject_invalidates_old_path_and_blocks_old_iteration(db_session) -> None:
  seed = await _seed_graph(
    db_session,
    node_keys=("A", "B", "C"),
    edges=(("A", "B", {}, 0), ("B", "C", {}, 0)),
  )
  result = await _create_run(db_session, seed)
  service = WorkflowGraphService(db_session)
  old_b = _node(result, "B")
  old_c = _node(result, "C")

  await service.complete_node_instance(node_instance_id=_node(result, "A").id, actor_id=seed.actor.id)
  await service.complete_node_instance(node_instance_id=old_b.id, actor_id=seed.actor.id)
  await service.deep_reject_to_upstream(
    node_instance_id=old_c.id,
    actor_id=seed.actor.id,
    target_node_key="B",
    reason="rework",
  )

  invalidated_traversals = list(
    await db_session.scalars(
      select(WorkflowEdgeTraversal).where(
        WorkflowEdgeTraversal.source_node_instance_id == old_b.id,
      )
    )
  )
  assert len(invalidated_traversals) == 1
  assert invalidated_traversals[0].status == "invalidated"
  assert invalidated_traversals[0].invalidated_at is not None

  invalidated_dependencies = list(
    await db_session.scalars(
      select(WorkflowNodeActivationDependency).where(
        WorkflowNodeActivationDependency.instance_id == result.instance.id,
        WorkflowNodeActivationDependency.status == "invalidated",
      )
    )
  )
  assert invalidated_dependencies

  replay_b = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == result.instance.id,
      WorkflowNodeInstance.node_key == "B",
      WorkflowNodeInstance.iteration == 2,
    )
  )
  assert replay_b is not None
  assert replay_b.engine_state == WorkflowNodeEngineState.ACTIVATED

  with pytest.raises(ConflictError, match="旧 iteration"):
    await service.progress_from_completed_node(node_instance_id=old_b.id)
  await db_session.rollback()


@pytest.mark.asyncio
async def test_graph_v2_snapshot_run_keeps_legacy_path_executor(db_session) -> None:
  seed = await _seed_graph(
    db_session,
    node_keys=("A", "B"),
    edges=(("A", "B", {}, 0),),
  )
  result = await _create_run(db_session, seed)
  result.instance.engine_version = "graph-v2"
  await db_session.commit()

  await WorkflowGraphService(db_session).complete_node_instance(
    node_instance_id=_node(result, "A").id,
    actor_id=seed.actor.id,
  )
  traversal = await db_session.scalar(
    select(WorkflowEdgeTraversal.id).where(
      WorkflowEdgeTraversal.instance_id == result.instance.id,
    )
  )
  await db_session.refresh(_node(result, "B"))
  assert traversal is None
  assert _node(result, "B").engine_state == WorkflowNodeEngineState.ACTIVATED
