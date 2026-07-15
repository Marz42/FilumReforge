from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete

from app.api.routes.workflow_graph_engine import (
  get_graph_instance,
  get_graph_template_designer,
  get_graph_template_stats,
  list_graph_instance_children,
  list_graph_instance_events,
  list_graph_instances_for_template,
  list_instance_submissions,
)
from app.core.config import Settings
from app.core.enums import (
  TaskPriority,
  TaskSourceType,
  TaskStatus,
  UserRole,
  WorkflowGraphInstanceStatus,
  WorkflowGraphTemplateStatus,
  WorkflowNodeEngineState,
)
from app.core.exceptions import NotFoundError
from app.models import (
  Department,
  Task,
  TaskWatcher,
  User,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateEdge,
  WorkflowGraphTemplateNode,
  WorkflowNodeInstance,
)
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_access_policy import WorkflowAccessPolicy
from app.services.workflow_graph_template_admin_service import WorkflowGraphTemplateAdminService
from app.services.workflow_run_event_service import WorkflowRunEventService
from app.services.workflow_video_form_service import WorkflowVideoFormService

TEST_JWT_SECRET = "iteration-0-test-secret-key-32-bytes!!"


@dataclass(slots=True)
class GraphSeed:
  admin: User
  template: WorkflowGraphTemplate
  nodes: dict[str, WorkflowGraphTemplateNode]
  edges: dict[tuple[str, str], WorkflowGraphTemplateEdge]


async def _seed_graph(
  db_session,
  *,
  node_keys: tuple[str, ...],
  edge_specs: tuple[tuple[str, str, dict, int], ...],
  join_modes: dict[str, str] | None = None,
) -> GraphSeed:
  admin = await AuthService(
    db_session,
    Settings(jwt_secret_key=TEST_JWT_SECRET),
  ).bootstrap_admin(
    email=f"iteration0-admin-{uuid4().hex}@example.com",
    password="StrongPassword123!",
    real_name="Iteration 0 管理员",
    employee_no=f"I0-{uuid4().hex[:12]}",
  )
  code = f"iteration0-{uuid4().hex}"
  template = WorkflowGraphTemplate(
    code=code,
    base_code=code,
    version=1,
    name="Iteration 0 语义证据模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  join_modes = join_modes or {}
  nodes = {
    key: WorkflowGraphTemplateNode(
      template_id=template.id,
      node_key=key,
      title=key,
      sort_order=index,
      join_mode=join_modes.get(key, "all"),
    )
    for index, key in enumerate(node_keys, start=1)
  }
  db_session.add_all(nodes.values())
  await db_session.flush()

  edges: dict[tuple[str, str], WorkflowGraphTemplateEdge] = {}
  for from_key, to_key, condition, priority in edge_specs:
    edge = WorkflowGraphTemplateEdge(
      template_id=template.id,
      from_node_id=nodes[from_key].id,
      to_node_id=nodes[to_key].id,
      condition=condition,
      priority=priority,
    )
    edges[(from_key, to_key)] = edge
  db_session.add_all(edges.values())
  await db_session.commit()
  return GraphSeed(admin=admin, template=template, nodes=nodes, edges=edges)


async def _create_run(db_session, seed: GraphSeed, *, context: dict | None = None):
  return await WorkflowGraphService(db_session).create_multi_node_instance(
    template_id=seed.template.id,
    initiator_id=seed.admin.id,
    context=context,
  )


def _node(result, node_key: str) -> WorkflowNodeInstance:
  return next(item for item in result.node_instances if item.node_key == node_key)


@pytest.mark.asyncio
async def test_iteration0_gap_fixture_builds_isolated_graph(db_session) -> None:
  """基座自检不使用 xfail，避免测试初始化故障被缺陷标记掩盖。"""
  seed = await _seed_graph(
    db_session,
    node_keys=("A", "B"),
    edge_specs=(("A", "B", {}, 0),),
  )
  result = await _create_run(db_session, seed)

  assert _node(result, "A").engine_state == WorkflowNodeEngineState.ACTIVATED
  assert _node(result, "B").engine_state == WorkflowNodeEngineState.PENDING


@pytest.mark.workflow_gap
@pytest.mark.asyncio
async def test_wg_gap_001_unselected_exclusive_branch_does_not_block_completion(db_session) -> None:
  seed = await _seed_graph(
    db_session,
    node_keys=("A", "B", "C"),
    edge_specs=(
      ("A", "B", {"field": "route", "operator": "eq", "value": "B"}, 0),
      ("A", "C", {"else": True}, 1),
    ),
  )
  result = await _create_run(db_session, seed, context={"route": "B"})
  service = WorkflowGraphService(db_session)

  await service.complete_node_instance(node_instance_id=_node(result, "A").id, actor_id=seed.admin.id)
  await service.complete_node_instance(node_instance_id=_node(result, "B").id, actor_id=seed.admin.id)
  await db_session.refresh(result.instance)

  assert result.instance.status == WorkflowGraphInstanceStatus.COMPLETED


@pytest.mark.workflow_gap
@pytest.mark.asyncio
async def test_wg_gap_002_wait_all_joins_only_produced_exclusive_branch(db_session) -> None:
  seed = await _seed_graph(
    db_session,
    node_keys=("A", "B", "C", "D"),
    edge_specs=(
      ("A", "B", {"field": "route", "operator": "eq", "value": "B"}, 0),
      ("A", "C", {"else": True}, 1),
      ("B", "D", {}, 0),
      ("C", "D", {}, 0),
    ),
    join_modes={"D": "all"},
  )
  result = await _create_run(db_session, seed, context={"route": "B"})
  service = WorkflowGraphService(db_session)

  await service.complete_node_instance(node_instance_id=_node(result, "A").id, actor_id=seed.admin.id)
  await service.complete_node_instance(node_instance_id=_node(result, "B").id, actor_id=seed.admin.id)
  await db_session.refresh(_node(result, "D"))

  assert _node(result, "D").engine_state == WorkflowNodeEngineState.ACTIVATED


@pytest.mark.workflow_gap
@pytest.mark.asyncio
async def test_wg_gap_003_no_matching_route_fails_with_diagnostic(db_session) -> None:
  seed = await _seed_graph(
    db_session,
    node_keys=("A", "B"),
    edge_specs=(("A", "B", {"field": "route", "operator": "eq", "value": "B"}, 0),),
  )
  result = await _create_run(db_session, seed, context={"route": "none"})

  await WorkflowGraphService(db_session).complete_node_instance(
    node_instance_id=_node(result, "A").id,
    actor_id=seed.admin.id,
  )
  await db_session.refresh(result.instance)

  assert result.instance.status.value == "failed"
  assert (result.instance.context or {}).get("failure", {}).get("code") == "no_route"


@pytest.mark.workflow_gap
@pytest.mark.asyncio
async def test_wg_gap_004_in_flight_run_uses_instantiation_snapshot(db_session) -> None:
  seed = await _seed_graph(
    db_session,
    node_keys=("A", "B", "C"),
    edge_specs=(("A", "B", {}, 0), ("B", "C", {}, 0)),
  )
  result = await _create_run(db_session, seed)

  await db_session.execute(
    delete(WorkflowGraphTemplateEdge).where(
      WorkflowGraphTemplateEdge.id == seed.edges[("A", "B")].id,
    )
  )
  db_session.add(
    WorkflowGraphTemplateEdge(
      template_id=seed.template.id,
      from_node_id=seed.nodes["A"].id,
      to_node_id=seed.nodes["C"].id,
    )
  )
  await db_session.commit()

  await WorkflowGraphService(db_session).complete_node_instance(
    node_instance_id=_node(result, "A").id,
    actor_id=seed.admin.id,
  )
  await db_session.refresh(_node(result, "B"))
  await db_session.refresh(_node(result, "C"))

  assert _node(result, "B").engine_state == WorkflowNodeEngineState.ACTIVATED
  assert _node(result, "C").engine_state == WorkflowNodeEngineState.PENDING


async def _seed_authorization_case(db_session):
  seed = await _seed_graph(db_session, node_keys=("A",), edge_specs=())
  unrelated = await UserService(db_session).create_user(
    actor=seed.admin,
    email=f"iteration0-employee-{uuid4().hex}@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  result = await _create_run(db_session, seed)
  return seed, unrelated, result


@pytest.mark.asyncio
async def test_auth_gap_001_unrelated_employee_cannot_read_instance(db_session) -> None:
  _, unrelated, result = await _seed_authorization_case(db_session)
  with pytest.raises(NotFoundError):
    await get_graph_instance(
      instance_id=result.instance.id,
      actor=unrelated,
      session=db_session,
      workflow_graph_service=WorkflowGraphService(db_session),
    )


@pytest.mark.parametrize("resource", ["events", "children", "submissions"])
@pytest.mark.asyncio
async def test_auth_gap_002_unrelated_employee_cannot_read_run_related_resources(
  db_session,
  resource: str,
) -> None:
  _, unrelated, result = await _seed_authorization_case(db_session)
  with pytest.raises(NotFoundError):
    if resource == "events":
      await list_graph_instance_events(
        instance_id=result.instance.id,
        actor=unrelated,
        session=db_session,
        event_service=WorkflowRunEventService(db_session),
        limit=20,
        offset=0,
      )
    elif resource == "children":
      await list_graph_instance_children(
        instance_id=result.instance.id,
        actor=unrelated,
        session=db_session,
        workflow_graph_service=WorkflowGraphService(db_session),
        limit=50,
        include_completed=False,
      )
    else:
      await list_instance_submissions(
        instance_id=result.instance.id,
        actor=unrelated,
        session=db_session,
        form_service=WorkflowVideoFormService(db_session),
        node_key="A",
      )


@pytest.mark.parametrize("resource", ["designer", "stats", "instances"])
@pytest.mark.asyncio
async def test_auth_gap_003_employee_cannot_read_template_management_resources(
  db_session,
  resource: str,
) -> None:
  seed, unrelated, _ = await _seed_authorization_case(db_session)
  with pytest.raises(NotFoundError):
    if resource == "designer":
      await get_graph_template_designer(
        template_id=seed.template.id,
        actor=unrelated,
        session=db_session,
        admin_service=WorkflowGraphTemplateAdminService(db_session),
      )
    elif resource == "stats":
      await get_graph_template_stats(
        template_id=seed.template.id,
        actor=unrelated,
        session=db_session,
        admin_service=WorkflowGraphTemplateAdminService(db_session),
      )
    else:
      await list_graph_instances_for_template(
        template_id=seed.template.id,
        actor=unrelated,
        session=db_session,
        workflow_graph_service=WorkflowGraphService(db_session),
        limit=10,
      )


@pytest.mark.parametrize("relationship", ["initiator", "current_assignee", "historical_actor", "manager", "watcher"])
@pytest.mark.asyncio
async def test_iteration1_instance_read_policy_allows_registered_relationships(
  db_session,
  relationship: str,
) -> None:
  seed, unrelated, result = await _seed_authorization_case(db_session)
  actor = seed.admin if relationship == "initiator" else unrelated

  if relationship == "current_assignee":
    _node(result, "A").assignee_user_id = unrelated.id
  elif relationship == "historical_actor":
    await WorkflowRunEventService(db_session).append(
      instance_id=result.instance.id,
      event_type="node_completed",
      actor_user_id=unrelated.id,
      payload={"evidence": "iteration1-access-policy"},
    )
  elif relationship == "manager":
    department = Department(
      name=f"Iteration 1 部门 {uuid4().hex[:8]}",
      code=f"i1-{uuid4().hex}",
      manager_id=unrelated.id,
    )
    db_session.add(department)
    await db_session.flush()
    result.instance.department_id = department.id
  elif relationship == "watcher":
    task = Task(
      title="Iteration 1 watcher evidence",
      creator_id=seed.admin.id,
      assignee_id=seed.admin.id,
      status=TaskStatus.TODO,
      priority=TaskPriority.MEDIUM,
      source_type=TaskSourceType.MANUAL,
      extra_metadata={"workflow_graph_instance_id": str(result.instance.id)},
    )
    db_session.add(task)
    await db_session.flush()
    db_session.add(
      TaskWatcher(
        task_id=task.id,
        user_id=unrelated.id,
        relation="cc",
        created_by=seed.admin.id,
      )
    )
  await db_session.commit()

  authorized_instance = await WorkflowAccessPolicy(db_session).ensure_can_read_instance(
    actor=actor,
    instance_id=result.instance.id,
  )
  assert authorized_instance.id == result.instance.id


@pytest.mark.asyncio
async def test_iteration1_department_manager_can_read_template_management_resources(db_session) -> None:
  seed, manager, _ = await _seed_authorization_case(db_session)
  department = Department(
    name=f"Iteration 1 模板管理部门 {uuid4().hex[:8]}",
    code=f"i1-manage-{uuid4().hex}",
    manager_id=manager.id,
  )
  db_session.add(department)
  await db_session.flush()
  seed.template.scope_mode = "departments"
  seed.template.scope_department_ids = [str(department.id)]
  await db_session.commit()

  detail = await get_graph_template_designer(
    template_id=seed.template.id,
    actor=manager,
    session=db_session,
    admin_service=WorkflowGraphTemplateAdminService(db_session),
  )
  assert detail.id == seed.template.id
