"""W3 tests: graph template instantiation v2."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.enums import (
  TaskSourceType,
  UserRole,
  WorkflowGraphTemplateStatus,
  WorkflowNodeEngineState,
)
from app.core.exceptions import ConflictError
from app.models import Task, WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode
from app.schemas.workflow_video import ParticipantsSnapshotEntry
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.profile_service import ProfileService
from app.services.user_service import UserService
from app.services.workflow_video_instantiation_service import WorkflowVideoInstantiationService

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"

CAPTURE_SCHEMA = {
  "mode": "row_table",
  "min_rows": 1,
  "max_rows": 5,
  "columns": [
    {"key": "title", "label": "标题", "type": "text", "required": True},
    {"key": "content", "label": "内容", "type": "textarea"},
  ],
  "completion_policy": "on_capture_submitted",
}

AGGREGATE_SCHEMA = {
  "mode": "submission_matrix",
  "source_node_key": "N1_PROPOSE",
  "row_id_field": "topic_id",
  "row_actions": ["approve", "reject"],
  "on_confirm": {
    "action": "finalize_topics_and_fork",
    "child_template_code": "video_production_per_topic_v1",
    "idempotency_key": "topic_id",
  },
}

LAUNCH_SCHEMA = {
  "fields": [
    {"key": "theme", "label": "主题", "type": "text", "required": True},
    {"key": "manager_user_id", "label": "负责人", "type": "user", "required": True},
  ]
}


async def _seed_topic_meeting_batch_template(db_session):
  auth = AuthService(db_session, Settings(jwt_secret_key=TEST_JWT_SECRET))
  admin = await auth.bootstrap_admin(
    email="w3-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-W3-ROOT",
  )
  user_service = UserService(db_session)
  dept_service = DepartmentService(db_session)
  profile_service = ProfileService(db_session)

  manager = await user_service.create_user(
    actor=admin,
    email="w3-manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  editors = []
  for suffix, name in (("a", "编辑甲"), ("b", "编辑乙"), ("c", "编辑丙")):
    editor = await user_service.create_user(
      actor=admin,
      email=f"w3-editor-{suffix}@example.com",
      password="StrongPassword123!",
      role=UserRole.EMPLOYEE,
    )
    editors.append(editor)

  department = await dept_service.create_department(
    actor=admin,
    name="文案部",
    code="w3-copy",
    manager_id=manager.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=manager.id,
    employee_no="EMP-W3-M",
    real_name="负责人",
    department_id=department.id,
    custom_fields={},
  )
  for editor, suffix, name in zip(editors, ("a", "b", "c"), ("编辑甲", "编辑乙", "编辑丙"), strict=True):
    await profile_service.create_profile(
      actor=admin,
      user_id=editor.id,
      employee_no=f"EMP-W3-{suffix.upper()}",
      real_name=name,
      department_id=department.id,
      custom_fields={},
    )

  template = WorkflowGraphTemplate(
    code="topic_meeting_batch_v1",
    base_code="topic_meeting_batch_v1",
    version=1,
    name="选题会",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    config={
      "run_kind": "batch",
      "launch_schema": LAUNCH_SCHEMA,
      "root_assignee_var": "manager_user_id",
      "participant_policies": {
        "copywriters": {"type": "department_members", "department_id": str(department.id)},
      },
    },
    context_schema={},
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_n1 = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="N1_PROPOSE",
    title="提交选题",
    sort_order=1,
    config={
      "kind": "multi_instance",
      "expand_from": "copywriters",
      "participant_policy_ref": "copywriters",
      "capture_schema": CAPTURE_SCHEMA,
      "ui_profile": "video_n1_capture",
    },
  )
  node_n2 = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="N2_AGGREGATE",
    title="汇总派发",
    sort_order=2,
    assignee_rule={"type": "context_var", "var": "manager_user_id"},
    config={
      "kind": "single",
      "aggregate_schema": AGGREGATE_SCHEMA,
      "ui_profile": "video_n2_aggregate",
    },
  )
  db_session.add_all([node_n1, node_n2])
  await db_session.flush()

  edge = WorkflowGraphTemplateEdge(
    template_id=template.id,
    from_node_id=node_n1.id,
    to_node_id=node_n2.id,
  )
  db_session.add(edge)
  await db_session.flush()

  return {
    "admin": admin,
    "manager": manager,
    "editors": editors,
    "department": department,
    "template": template,
  }


def _enabled_settings() -> Settings:
  return Settings(
    jwt_secret_key=TEST_JWT_SECRET,
    workflow_graph_template_engine_enabled=True,
  )


@pytest.mark.asyncio
async def test_w3_instantiate_three_copywriters_three_n1_tasks(db_session) -> None:
  seed = await _seed_topic_meeting_batch_template(db_session)
  admin = seed["admin"]
  manager = seed["manager"]
  editors = seed["editors"]
  template = seed["template"]
  department = seed["department"]

  service = WorkflowVideoInstantiationService(db_session, settings=_enabled_settings())
  snapshot = {
    "copywriters": ParticipantsSnapshotEntry(
      mode="subset",
      user_ids=[editor.id for editor in editors],
    )
  }
  result = await service.instantiate_graph_template(
    actor=admin,
    template_id=template.id,
    inputs={
      "theme": "五月选题",
      "manager_user_id": str(manager.id),
    },
    participants_snapshot=snapshot,
    department_id=department.id,
  )

  n1_nodes = [ni for ni in result.node_instances if ni.node_key == "N1_PROPOSE"]
  n2_nodes = [ni for ni in result.node_instances if ni.node_key == "N2_AGGREGATE"]
  assert len(n1_nodes) == 3
  assert all(ni.engine_state == WorkflowNodeEngineState.ACTIVATED for ni in n1_nodes)
  assert {ni.instance_key for ni in n1_nodes} == {
    "branch:0001",
    "branch:0002",
    "branch:0003",
  }
  assert all(ni.instance_key != str(ni.assignee_user_id) for ni in n1_nodes)
  assert len(n2_nodes) == 1
  assert n2_nodes[0].engine_state == WorkflowNodeEngineState.PENDING
  assert len(result.activated_tasks) == 3
  assert result.instance.current_node_key == "N1_PROPOSE"
  assert result.instance.source_id == result.root_task.id
  assert result.instance.executor_kind == "snapshot"
  assert result.instance.engine_version == "graph-v3"
  assert (result.instance.definition_snapshot or {}).get("format_version") == 2
  assert result.instance.definition_snapshot is not None
  assert len(result.instance.definition_hash or "") == 64

  assignee_ids = {task.assignee_id for task in result.activated_tasks}
  assert assignee_ids == {editor.id for editor in editors}
  capture_tasks = [
    task
    for task in result.activated_tasks
    if str((task.extra_metadata or {}).get("template_node_key")) == "N1_PROPOSE"
  ]
  assert capture_tasks
  assert all(
    (task.extra_metadata or {}).get("ui_profile") == "video_n1_capture"
    for task in capture_tasks
  )
  assert (result.root_task.extra_metadata or {}).get("ui_profile") == "video_batch_root"

  all_tasks = list(
    await db_session.scalars(select(Task).where(Task.source_type == TaskSourceType.TEMPLATE))
  )
  tasks_for_n2 = [
    task
    for task in all_tasks
    if str((task.extra_metadata or {}).get("workflow_node_instance_id")) == str(n2_nodes[0].id)
  ]
  assert tasks_for_n2 == []


@pytest.mark.asyncio
async def test_w3_scope_check_uses_resolved_final_department_when_request_omits_it(db_session) -> None:
  seed = await _seed_topic_meeting_batch_template(db_session)
  other_department = await DepartmentService(db_session).create_department(
    actor=seed["admin"],
    name="Scope 外部门",
    code="w3-scope-other",
  )
  seed["template"].scope_mode = "departments"
  seed["template"].scope_department_ids = [str(other_department.id)]
  await db_session.flush()

  service = WorkflowVideoInstantiationService(db_session, settings=_enabled_settings())
  with pytest.raises(ConflictError, match="不在该模板的作用范围"):
    await service.instantiate_graph_template(
      actor=seed["admin"],
      template_id=seed["template"].id,
      inputs={"theme": "Scope", "manager_user_id": str(seed["manager"].id)},
      participants_snapshot={
        "copywriters": ParticipantsSnapshotEntry(
          mode="subset",
          user_ids=[editor.id for editor in seed["editors"]],
        )
      },
      department_id=None,
    )


@pytest.mark.asyncio
async def test_w3_schema_snapshot_written_to_context(db_session) -> None:
  seed = await _seed_topic_meeting_batch_template(db_session)
  service = WorkflowVideoInstantiationService(db_session, settings=_enabled_settings())
  result = await service.instantiate_graph_template(
    actor=seed["admin"],
    template_id=seed["template"].id,
    inputs={"theme": "测试", "manager_user_id": str(seed["manager"].id)},
    participants_snapshot={
      "copywriters": ParticipantsSnapshotEntry(
        mode="subset",
        user_ids=[editor.id for editor in seed["editors"]],
      )
    },
    department_id=seed["department"].id,
  )
  context = result.instance.context
  assert context["schema_snapshot"]["template_code"] == "topic_meeting_batch_v1"
  assert "N1_PROPOSE" in context["schema_snapshot"]["nodes"]
  assert context["root_task_id"] == str(result.root_task.id)
  assert context["run_kind"] == "batch"


@pytest.mark.asyncio
async def test_w3_engine_disabled_raises(db_session) -> None:
  seed = await _seed_topic_meeting_batch_template(db_session)
  service = WorkflowVideoInstantiationService(
    db_session,
    settings=Settings(jwt_secret_key=TEST_JWT_SECRET, workflow_graph_template_engine_enabled=False),
  )
  with pytest.raises(ConflictError, match="未启用"):
    await service.instantiate_graph_template(
      actor=seed["admin"],
      template_id=seed["template"].id,
      inputs={"theme": "x", "manager_user_id": str(seed["manager"].id)},
      participants_snapshot={
        "copywriters": ParticipantsSnapshotEntry(mode="subset", user_ids=[seed["editors"][0].id])
      },
    )


@pytest.mark.asyncio
async def test_w3_missing_launch_field_raises(db_session) -> None:
  seed = await _seed_topic_meeting_batch_template(db_session)
  service = WorkflowVideoInstantiationService(db_session, settings=_enabled_settings())
  with pytest.raises(ConflictError, match="必填"):
    await service.instantiate_graph_template(
      actor=seed["admin"],
      template_id=seed["template"].id,
      inputs={"manager_user_id": str(seed["manager"].id)},
      participants_snapshot={
        "copywriters": ParticipantsSnapshotEntry(mode="subset", user_ids=[seed["editors"][0].id])
      },
    )


@pytest.mark.asyncio
async def test_w3_excludes_initiator_from_n1_fanout_by_default(db_session) -> None:
  seed = await _seed_topic_meeting_batch_template(db_session)
  manager = seed["manager"]
  editors = seed["editors"]
  template = seed["template"]
  department = seed["department"]

  service = WorkflowVideoInstantiationService(db_session, settings=_enabled_settings())
  result = await service.instantiate_graph_template(
    actor=manager,
    template_id=template.id,
    inputs={"theme": "排除发起人", "manager_user_id": str(manager.id)},
    participants_snapshot={
      "copywriters": ParticipantsSnapshotEntry(
        mode="subset",
        user_ids=[manager.id, *[editor.id for editor in editors]],
        include_initiator=False,
      )
    },
    department_id=department.id,
  )

  n1_nodes = [ni for ni in result.node_instances if ni.node_key == "N1_PROPOSE"]
  assert len(n1_nodes) == 3
  assignee_ids = {ni.assignee_user_id for ni in n1_nodes}
  assert manager.id not in assignee_ids
  assert assignee_ids == {editor.id for editor in editors}


@pytest.mark.asyncio
async def test_w3_rejects_out_of_policy_participant(db_session) -> None:
  from uuid import uuid4

  seed = await _seed_topic_meeting_batch_template(db_session)
  service = WorkflowVideoInstantiationService(db_session, settings=_enabled_settings())
  with pytest.raises(ConflictError):
    await service.instantiate_graph_template(
      actor=seed["admin"],
      template_id=seed["template"].id,
      inputs={"theme": "越界", "manager_user_id": str(seed["manager"].id)},
      participants_snapshot={
        "copywriters": ParticipantsSnapshotEntry(
          mode="subset",
          user_ids=[uuid4()],
        )
      },
      department_id=seed["department"].id,
    )


@pytest.mark.asyncio
async def test_w3_rejects_empty_participants_after_initiator_filter(db_session) -> None:
  seed = await _seed_topic_meeting_batch_template(db_session)
  manager = seed["manager"]
  service = WorkflowVideoInstantiationService(db_session, settings=_enabled_settings())
  with pytest.raises(ConflictError, match="至少保留一名采集参与人"):
    await service.instantiate_graph_template(
      actor=manager,
      template_id=seed["template"].id,
      inputs={"theme": "仅发起人", "manager_user_id": str(manager.id)},
      participants_snapshot={
        "copywriters": ParticipantsSnapshotEntry(
          mode="subset",
          user_ids=[manager.id],
          include_initiator=False,
        )
      },
      department_id=seed["department"].id,
    )
