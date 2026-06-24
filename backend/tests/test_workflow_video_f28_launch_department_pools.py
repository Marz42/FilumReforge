"""F-28: production fork uses batch launch department for copywriters pool (N4/N12)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.enums import (
  UserRole,
  WorkflowGraphTemplateStatus,
)
from app.models import (
  Task,
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateEdge,
  WorkflowGraphTemplateNode,
  WorkflowNodeInstance,
)
from app.schemas.workflow_video import ApprovedTopic
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.profile_service import ProfileService
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_video_instantiation_service import WorkflowVideoInstantiationService
from app.services.workflow_video_template_seed_data import (
  build_production_edges,
  build_production_nodes,
  build_production_template_config,
)

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


def _enabled_settings() -> Settings:
  return Settings(
    jwt_secret_key=TEST_JWT_SECRET,
    workflow_graph_template_engine_enabled=True,
  )


async def _seed_two_copywriting_departments(db_session):
  auth = AuthService(db_session, Settings(jwt_secret_key=TEST_JWT_SECRET))
  admin = await auth.bootstrap_admin(
    email="f28-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-F28-ROOT",
  )
  user_service = UserService(db_session)
  dept_service = DepartmentService(db_session)
  profile_service = ProfileService(db_session)

  manager_a = await user_service.create_user(
    actor=admin,
    email="f28-mgr-a@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  manager_b = await user_service.create_user(
    actor=admin,
    email="f28-mgr-b@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  script_author = await user_service.create_user(
    actor=admin,
    email="f28-author@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  copy_dept_a = await dept_service.create_department(
    actor=admin,
    name="文案部 A",
    code="f28-copy-a",
    manager_id=manager_a.id,
  )
  copy_dept_b = await dept_service.create_department(
    actor=admin,
    name="文案部 B",
    code="f28-copy-b",
    manager_id=manager_b.id,
  )
  post_lead = await user_service.create_user(
    actor=admin,
    email="f28-post@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  post_dept = await dept_service.create_department(
    actor=admin,
    name="后期部",
    code="f28-post",
    manager_id=post_lead.id,
  )

  for user, suffix, dept_id in (
    (manager_a, "MGR-A", copy_dept_a.id),
    (manager_b, "MGR-B", copy_dept_b.id),
    (script_author, "AUTH", copy_dept_b.id),
  ):
    await profile_service.create_profile(
      actor=admin,
      user_id=user.id,
      employee_no=f"EMP-F28-{suffix}",
      real_name=suffix,
      department_id=dept_id,
      custom_fields={},
    )

  template = WorkflowGraphTemplate(
    code="video_production_f28_test_v1",
    base_code="video_production_f28_test_v1",
    version=1,
    name="单题制作 F28",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    config=build_production_template_config(
      copywriting_department_id=copy_dept_a.id,
      voice_department_id=copy_dept_a.id,
      post_department_id=post_dept.id,
    ),
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_models: dict[str, WorkflowGraphTemplateNode] = {}
  for node_data in build_production_nodes():
    node = WorkflowGraphTemplateNode(
      template_id=template.id,
      node_key=node_data["node_key"],
      title=node_data["title"],
      sort_order=node_data["sort_order"],
      assignee_rule=node_data.get("assignee_rule") or {},
      config=node_data.get("config") or {},
    )
    db_session.add(node)
    node_models[node_data["node_key"]] = node
  await db_session.flush()

  for from_key, to_key, is_reject in build_production_edges():
    db_session.add(
      WorkflowGraphTemplateEdge(
        template_id=template.id,
        from_node_id=node_models[from_key].id,
        to_node_id=node_models[to_key].id,
        is_reject_path=is_reject,
      )
    )
  await db_session.flush()

  return {
    "admin": admin,
    "manager_a": manager_a,
    "manager_b": manager_b,
    "script_author": script_author,
    "post_lead": post_lead,
    "template": template,
    "copy_dept_a": copy_dept_a,
    "copy_dept_b": copy_dept_b,
    "post_dept": post_dept,
  }


async def _node_task_id(db_session, *, instance_id, node_key: str):
  node = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == instance_id,
      WorkflowNodeInstance.node_key == node_key,
    )
  )
  assert node is not None
  return node, (node.config or {}).get("task_id")


@pytest.mark.asyncio
async def test_f28_production_fork_copywriters_pool_follows_launch_department(db_session) -> None:
  seed = await _seed_two_copywriting_departments(db_session)
  instantiation = WorkflowVideoInstantiationService(
    db_session,
    settings=_enabled_settings(),
    task_service=TaskService(db_session, settings=_enabled_settings()),
  )

  batch_stub = WorkflowGraphInstance(
    initiator_user_id=seed["admin"].id,
    department_id=seed["copy_dept_b"].id,
    source_type="template",
    context={"run_kind": "batch", "manager_user_id": str(seed["manager_b"].id)},
  )
  db_session.add(batch_stub)
  await db_session.flush()

  run = await instantiation.instantiate_production_child_run(
    actor=seed["admin"],
    template=seed["template"],
    parent_instance=batch_stub,
    topic=ApprovedTopic(
      topic_id=uuid4(),
      title="B 部选题",
      script_author_id=seed["script_author"].id,
    ),
    parent_task_id=None,
  )
  instance = run.instance
  context_pools = (instance.context or {}).get("department_pools")
  assert isinstance(context_pools, dict)
  assert context_pools["copywriters"] == str(seed["copy_dept_b"].id)
  assert context_pools["post_production"] == str(seed["post_dept"].id)

  task_service = TaskService(db_session, settings=_enabled_settings())
  n3_node, raw_n3_task_id = await _node_task_id(db_session, instance_id=instance.id, node_key="N3_SCRIPT_WRITE")
  assert n3_node.assignee_user_id == seed["script_author"].id

  await task_service.submit_task_deliverable(
    actor=seed["script_author"],
    task_id=UUID(str(raw_n3_task_id)),
    summary="脚本",
    attachment_ids=[],
  )

  n4_node = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == instance.id,
      WorkflowNodeInstance.node_key == "N4_SCRIPT_REVIEW",
    )
  )
  assert n4_node is not None
  assert n4_node.assignee_user_id == seed["manager_b"].id
  assert n4_node.assignee_user_id != seed["manager_a"].id

  n4_task = await db_session.get(Task, UUID(str((n4_node.config or {})["task_id"])))
  assert n4_task is not None
  assert n4_task.assignee_id == seed["manager_b"].id
