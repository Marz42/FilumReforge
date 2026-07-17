"""Production progression tests: N5 VO upload -> N7 assign -> N12 cosign archive."""

from __future__ import annotations

from uuid import UUID, uuid4

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.enums import (
  TaskStatus,
  UserRole,
  WorkflowGraphInstanceStatus,
  WorkflowGraphTemplateStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.models import (
  Task,
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateEdge,
  WorkflowGraphTemplateNode,
  WorkflowNodeInstance,
)
from app.schemas.workflow_video import ApprovedTopic, TopicCaptureRow
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.profile_service import ProfileService
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_orchestration_service import WorkflowOrchestrationService
from app.services.workflow_video_form_service import WorkflowVideoFormService
from app.services.workflow_video_instantiation_service import WorkflowVideoInstantiationService
from app.services.workflow_video_template_seed_data import (
  EDIT_ASSIGN_CAPTURE_SCHEMA,
  SCHEDULE_CAPTURE_SCHEMA,
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


async def _seed_production_workspace(db_session):
  auth = AuthService(db_session, Settings(jwt_secret_key=TEST_JWT_SECRET))
  admin = await auth.bootstrap_admin(
    email="w4p-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-W4P-ROOT",
  )
  user_service = UserService(db_session)
  review_admin = await user_service.create_user(
    actor=admin,
    email="w4p-review-admin@example.com",
    password="StrongPassword123!",
    role=UserRole.ADMIN,
  )
  dept_service = DepartmentService(db_session)
  profile_service = ProfileService(db_session)

  post_lead = await user_service.create_user(
    actor=admin,
    email="w4p-post-lead@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  editor = await user_service.create_user(
    actor=admin,
    email="w4p-editor@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  script_author = await user_service.create_user(
    actor=admin,
    email="w4p-author@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  copy_dept = await dept_service.create_department(
    actor=admin,
    name="文案部",
    code="w4p-copy",
    manager_id=admin.id,
  )
  voice_dept = await dept_service.create_department(
    actor=admin,
    name="配音部",
    code="w4p-voice",
    manager_id=admin.id,
  )
  post_dept = await dept_service.create_department(
    actor=admin,
    name="后期部",
    code="w4p-post",
    manager_id=post_lead.id,
  )

  for user, suffix, dept_id in (
    (post_lead, "PL", post_dept.id),
    (editor, "ED", post_dept.id),
    (script_author, "AU", copy_dept.id),
  ):
    await profile_service.create_profile(
      actor=admin,
      user_id=user.id,
      employee_no=f"EMP-W4P-{suffix}",
      real_name=suffix,
      department_id=dept_id,
      custom_fields={},
    )

  template = WorkflowGraphTemplate(
    code="video_production_w4p_test_v1",
    base_code="video_production_w4p_test_v1",
    version=1,
    name="单题制作",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    config=build_production_template_config(
      copywriting_department_id=copy_dept.id,
      voice_department_id=voice_dept.id,
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
    "review_admin": review_admin,
    "post_lead": post_lead,
    "editor": editor,
    "script_author": script_author,
    "template": template,
    "copy_dept": copy_dept,
    "post_dept": post_dept,
  }


async def _instantiate_production_run(db_session, *, seed: dict):
  instantiation = WorkflowVideoInstantiationService(
    db_session,
    settings=_enabled_settings(),
    task_service=TaskService(db_session, settings=_enabled_settings()),
  )
  topic_id = uuid4()
  batch_stub = WorkflowGraphInstance(
    initiator_user_id=seed["admin"].id,
    department_id=seed["copy_dept"].id,
    source_type="template",
    context={"run_kind": "batch"},
  )
  db_session.add(batch_stub)
  await db_session.flush()

  result = await instantiation.instantiate_production_child_run(
    actor=seed["admin"],
    template=seed["template"],
    parent_instance=batch_stub,
    topic=ApprovedTopic(
      topic_id=topic_id,
      title="测试选题",
      script_author_id=seed["script_author"].id,
    ),
    parent_task_id=None,
  )
  await db_session.commit()
  return result


async def _node_task_id(db_session, *, instance_id: UUID, node_key: str) -> UUID:
  node = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == instance_id,
      WorkflowNodeInstance.node_key == node_key,
    )
  )
  assert node is not None
  return UUID(str((node.config or {}).get("task_id")))


@pytest.mark.asyncio
async def test_w4p_single_node_done_does_not_complete_run(db_session) -> None:
  seed = await _seed_production_workspace(db_session)
  run = await _instantiate_production_run(db_session, seed=seed)
  assert len(run.activated_tasks) == 1
  n3_task_id = run.activated_tasks[0].id

  task_service = TaskService(db_session, settings=_enabled_settings())
  await task_service.submit_task_deliverable(
    actor=seed["script_author"],
    task_id=n3_task_id,
    summary="脚本附件",
    attachment_ids=[],
  )
  await db_session.refresh(run.instance)
  assert run.instance.status != "completed"


@pytest.mark.asyncio
async def test_w4p_n5_vo_upload_activates_n7_for_post_lead(db_session) -> None:
  seed = await _seed_production_workspace(db_session)
  run = await _instantiate_production_run(db_session, seed=seed)
  instance = run.instance
  task_service = TaskService(db_session, settings=_enabled_settings())

  await task_service.submit_task_deliverable(
    actor=seed["script_author"],
    task_id=await _node_task_id(db_session, instance_id=instance.id, node_key="N3_SCRIPT_WRITE"),
    summary="脚本",
    attachment_ids=[],
  )

  n4_task_id = await _node_task_id(db_session, instance_id=instance.id, node_key="N4_SCRIPT_REVIEW")
  n4_task = await db_session.get(Task, n4_task_id)
  assert n4_task is not None
  assert n4_task.status == TaskStatus.REVIEW

  await task_service.review_task_deliverable(
    actor=seed["review_admin"],
    task_id=n4_task_id,
    approve=True,
    comment="脚本审核通过",
    quality_score=5,
  )

  n5 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == instance.id,
      WorkflowNodeInstance.node_key == "N5_VO_UPLOAD",
    )
  )
  assert n5 is not None
  assert n5.assignee_user_id == seed["script_author"].id

  await task_service.submit_task_deliverable(
    actor=seed["script_author"],
    task_id=await _node_task_id(db_session, instance_id=instance.id, node_key="N5_VO_UPLOAD"),
    summary="配音文件",
    attachment_ids=[],
  )

  n7 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == instance.id,
      WorkflowNodeInstance.node_key == "N7_EDIT_ASSIGN",
    )
  )
  assert n7 is not None
  assert n7.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert n7.assignee_user_id == seed["post_lead"].id


@pytest.mark.asyncio
async def test_w4p_n7_capture_assigns_n8_to_editor(db_session) -> None:
  seed = await _seed_production_workspace(db_session)
  run = await _instantiate_production_run(db_session, seed=seed)
  instance = run.instance
  graph_service = WorkflowGraphService(db_session)
  orchestration = WorkflowOrchestrationService(db_session, workflow_graph_service=graph_service)

  n5 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == instance.id,
      WorkflowNodeInstance.node_key == "N5_VO_UPLOAD",
    )
  )
  assert n5 is not None
  n5.engine_state = WorkflowNodeEngineState.COMPLETED
  n5.assignee_user_id = seed["script_author"].id
  await graph_service.progress_from_completed_node(node_instance_id=n5.id)
  await db_session.commit()

  n7 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == instance.id,
      WorkflowNodeInstance.node_key == "N7_EDIT_ASSIGN",
    )
  )
  assert n7 is not None
  assert n7.assignee_user_id == seed["post_lead"].id

  n7_tasks = await orchestration.ensure_projection_tasks(
    actor=seed["admin"],
    instance=instance,
    node_instances=[n7],
  )
  assert len(n7_tasks) == 1

  form = WorkflowVideoFormService(db_session, orchestration_service=orchestration)
  await form.submit_capture(
    actor=seed["post_lead"],
    task_id=n7_tasks[0].id,
    topics=[TopicCaptureRow(edit_assignee_id=str(seed["editor"].id))],
  )
  await db_session.refresh(instance)

  context = instance.context or {}
  assert str(context.get("edit_assignee_id")) == str(seed["editor"].id)

  n8 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == instance.id,
      WorkflowNodeInstance.node_key == "N8_EDIT_WORK",
    )
  )
  assert n8 is not None
  assert n8.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert n8.assignee_user_id == seed["editor"].id
  assert EDIT_ASSIGN_CAPTURE_SCHEMA["columns"][0]["type"] == "user"
  assert EDIT_ASSIGN_CAPTURE_SCHEMA["columns"][0]["pool_key"] == "post_production"
  assert SCHEDULE_CAPTURE_SCHEMA["columns"][0]["type"] == "datetime"


@pytest.mark.asyncio
async def test_w4p_post_stage_tasks_use_assignee_department_not_batch_department(db_session) -> None:
  seed = await _seed_production_workspace(db_session)
  run = await _instantiate_production_run(db_session, seed=seed)
  instance = run.instance
  graph_service = WorkflowGraphService(db_session)
  orchestration = WorkflowOrchestrationService(
    db_session,
    workflow_graph_service=graph_service,
    task_service=TaskService(db_session, settings=_enabled_settings()),
  )

  n3_task = await db_session.get(Task, run.activated_tasks[0].id)
  assert n3_task is not None
  assert n3_task.department_id == seed["copy_dept"].id

  n5 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == instance.id,
      WorkflowNodeInstance.node_key == "N5_VO_UPLOAD",
    )
  )
  assert n5 is not None
  n5.engine_state = WorkflowNodeEngineState.COMPLETED
  n5.assignee_user_id = seed["script_author"].id
  await graph_service.progress_from_completed_node(node_instance_id=n5.id)
  await db_session.commit()

  n7 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == instance.id,
      WorkflowNodeInstance.node_key == "N7_EDIT_ASSIGN",
    )
  )
  assert n7 is not None
  n7_tasks = await orchestration.ensure_projection_tasks(
    actor=seed["admin"],
    instance=instance,
    node_instances=[n7],
  )
  assert len(n7_tasks) == 1
  assert n7_tasks[0].department_id == seed["post_dept"].id
  assert instance.department_id == seed["copy_dept"].id


async def _progress_through_n9(db_session, *, seed: dict, instance: WorkflowGraphInstance) -> None:
  task_service = TaskService(db_session, settings=_enabled_settings())
  graph_service = WorkflowGraphService(db_session)
  orchestration = WorkflowOrchestrationService(
    db_session,
    workflow_graph_service=graph_service,
    task_service=task_service,
  )
  form = WorkflowVideoFormService(db_session, orchestration_service=orchestration)

  await task_service.submit_task_deliverable(
    actor=seed["script_author"],
    task_id=await _node_task_id(db_session, instance_id=instance.id, node_key="N3_SCRIPT_WRITE"),
    summary="脚本",
    attachment_ids=[],
  )
  await task_service.review_task_deliverable(
    actor=seed["review_admin"],
    task_id=await _node_task_id(db_session, instance_id=instance.id, node_key="N4_SCRIPT_REVIEW"),
    approve=True,
    comment="ok",
  )
  await task_service.submit_task_deliverable(
    actor=seed["script_author"],
    task_id=await _node_task_id(db_session, instance_id=instance.id, node_key="N5_VO_UPLOAD"),
    summary="配音",
    attachment_ids=[],
  )

  n7 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == instance.id,
      WorkflowNodeInstance.node_key == "N7_EDIT_ASSIGN",
    )
  )
  assert n7 is not None
  await db_session.refresh(n7)
  assert n7.engine_state == WorkflowNodeEngineState.ACTIVATED

  n7_task_id_raw = (n7.config or {}).get("task_id")
  if not n7_task_id_raw:
    n7_tasks = await orchestration.ensure_projection_tasks(
      actor=seed["admin"],
      instance=instance,
      node_instances=[n7],
    )
    assert len(n7_tasks) == 1
    n7_task_id = n7_tasks[0].id
  else:
    n7_task_id = UUID(str(n7_task_id_raw))

  await form.submit_capture(
    actor=seed["post_lead"],
    task_id=n7_task_id,
    topics=[TopicCaptureRow(edit_assignee_id=str(seed["editor"].id))],
  )

  await task_service.submit_task_deliverable(
    actor=seed["editor"],
    task_id=await _node_task_id(db_session, instance_id=instance.id, node_key="N8_EDIT_WORK"),
    summary="粗剪",
    attachment_ids=[],
  )
  await task_service.review_task_deliverable(
    actor=seed["admin"],
    task_id=await _node_task_id(db_session, instance_id=instance.id, node_key="N9_EDIT_REVIEW"),
    approve=True,
    comment="ok",
  )


@pytest.mark.asyncio
async def test_w4p_n10_upload_activates_n11_instead_of_archiving(db_session) -> None:
  seed = await _seed_production_workspace(db_session)
  run = await _instantiate_production_run(db_session, seed=seed)
  instance = run.instance
  task_service = TaskService(db_session, settings=_enabled_settings())

  await _progress_through_n9(db_session, seed=seed, instance=instance)

  await task_service.submit_task_deliverable(
    actor=seed["editor"],
    task_id=await _node_task_id(db_session, instance_id=instance.id, node_key="N10_UPLOAD"),
    summary="平台链接",
    attachment_ids=[],
  )
  await db_session.refresh(instance)

  n11 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == instance.id,
      WorkflowNodeInstance.node_key == "N11_SCHEDULE",
    )
  )
  assert n11 is not None
  assert n11.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert n11.assignee_user_id == seed["post_lead"].id
  assert instance.status == WorkflowGraphInstanceStatus.ACTIVE
  assert (instance.context or {}).get("archived") is not True


@pytest.mark.asyncio
async def test_w4p_legacy_n10_materializes_missing_tail_nodes_after_template_upgrade(db_session) -> None:
  seed = await _seed_production_workspace(db_session)
  run = await _instantiate_production_run(db_session, seed=seed)
  instance = run.instance
  instance.executor_kind = "legacy"
  instance.engine_version = "legacy-v1"
  instance.definition_snapshot = None
  instance.definition_hash = None
  task_service = TaskService(db_session, settings=_enabled_settings())

  await _progress_through_n9(db_session, seed=seed, instance=instance)

  tail_nodes = list(
    await db_session.scalars(
      select(WorkflowNodeInstance).where(
        WorkflowNodeInstance.instance_id == instance.id,
        WorkflowNodeInstance.node_key.in_(["N11_SCHEDULE", "N12_CLOSE", "N12_COSIGN"]),
      )
    )
  )
  for node in tail_nodes:
    await db_session.delete(node)
  await db_session.commit()

  await task_service.submit_task_deliverable(
    actor=seed["editor"],
    task_id=await _node_task_id(db_session, instance_id=instance.id, node_key="N10_UPLOAD"),
    summary="平台链接",
    attachment_ids=[],
  )
  await db_session.refresh(instance)

  n11 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == instance.id,
      WorkflowNodeInstance.node_key == "N11_SCHEDULE",
    )
  )
  assert n11 is not None
  assert n11.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert instance.status == WorkflowGraphInstanceStatus.ACTIVE
  assert (instance.context or {}).get("archived") is not True


@pytest.mark.asyncio
async def test_w4p_legacy_n10_resolves_outgoing_edges_when_template_node_id_is_stale(db_session) -> None:
  seed = await _seed_production_workspace(db_session)
  run = await _instantiate_production_run(db_session, seed=seed)
  instance = run.instance
  instance.executor_kind = "legacy"
  instance.engine_version = "legacy-v1"
  instance.definition_snapshot = None
  instance.definition_hash = None
  task_service = TaskService(db_session, settings=_enabled_settings())

  await _progress_through_n9(db_session, seed=seed, instance=instance)

  n10 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == instance.id,
      WorkflowNodeInstance.node_key == "N10_UPLOAD",
    )
  )
  assert n10 is not None
  n10.template_node_id = uuid4()
  await db_session.commit()

  await task_service.submit_task_deliverable(
    actor=seed["editor"],
    task_id=await _node_task_id(db_session, instance_id=instance.id, node_key="N10_UPLOAD"),
    summary="平台链接",
    attachment_ids=[],
  )
  await db_session.refresh(instance)

  n11 = await db_session.scalar(
    select(WorkflowNodeInstance).where(
      WorkflowNodeInstance.instance_id == instance.id,
      WorkflowNodeInstance.node_key == "N11_SCHEDULE",
    )
  )
  assert n11 is not None
  assert n11.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert instance.status == WorkflowGraphInstanceStatus.ACTIVE


@pytest.mark.asyncio
async def test_w4p_n12_cosign_archives_production_run(db_session) -> None:
  seed = await _seed_production_workspace(db_session)
  run = await _instantiate_production_run(db_session, seed=seed)
  instance = run.instance
  graph_service = WorkflowGraphService(db_session)

  nodes = list(
    await db_session.scalars(
      select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == instance.id)
    )
  )
  now = datetime.now(UTC)
  for node in nodes:
    node.engine_state = WorkflowNodeEngineState.COMPLETED
    node.business_state = WorkflowNodeBusinessState.DONE
    node.completed_at = now

  await graph_service._maybe_complete_instance(graph_instance=instance, now=now)
  await db_session.commit()
  await db_session.refresh(instance)

  assert instance.status == WorkflowGraphInstanceStatus.COMPLETED
  context = instance.context or {}
  assert context.get("archived") is True

  parent_id = instance.parent_instance_id
  assert parent_id is not None
  visible_children = await graph_service.list_child_instances(
    parent_instance_id=parent_id,
    include_completed=False,
  )
  assert all(child.id != instance.id for child in visible_children)
