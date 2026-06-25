"""WFK tests: per-topic production fork from batch runs."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.enums import (
  TaskSourceType,
  TaskStatus,
  WorkflowGraphTemplateStatus,
  WorkflowNodeEngineState,
)
from app.models import Task, WorkflowGraphInstance, WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode
from app.schemas.workflow_video import ApprovedTopic, ParticipantsSnapshotEntry, TopicCaptureRow
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_orchestration_service import WorkflowOrchestrationService
from app.services.workflow_video_fork_service import WorkflowVideoForkService
from app.services.workflow_video_form_service import WorkflowVideoFormService
from app.services.workflow_video_instantiation_service import WorkflowVideoInstantiationService
from app.services.workflow_video_template_seed_data import (
  VIDEO_PRODUCTION_CODE,
  build_production_edges,
  build_production_nodes,
  build_production_template_config,
)
from test_workflow_video_w3_instantiation import (
  TEST_JWT_SECRET,
  _enabled_settings,
  _seed_topic_meeting_batch_template,
)


async def _seed_production_template(db_session, *, admin_id, department_id):
  existing = await db_session.scalar(
    select(WorkflowGraphTemplate).where(
      WorkflowGraphTemplate.code == VIDEO_PRODUCTION_CODE,
      WorkflowGraphTemplate.status == WorkflowGraphTemplateStatus.ACTIVE,
    )
  )
  if existing is not None:
    return existing

  template = WorkflowGraphTemplate(
    code=VIDEO_PRODUCTION_CODE,
    base_code=VIDEO_PRODUCTION_CODE,
    version=1,
    name="单题视频制作",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    config=build_production_template_config(
      copywriting_department_id=department_id,
      voice_department_id=department_id,
      post_department_id=department_id,
    ),
    created_by=admin_id,
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
  return template


def _build_services(db_session):
  settings = _enabled_settings()
  graph = WorkflowGraphService(db_session)
  orchestration = WorkflowOrchestrationService(db_session, workflow_graph_service=graph)
  instantiation = WorkflowVideoInstantiationService(db_session, settings=settings)
  fork = WorkflowVideoForkService(
    db_session,
    instantiation_service=instantiation,
    orchestration_service=orchestration,
  )
  form = WorkflowVideoFormService(
    db_session,
    workflow_graph_service=graph,
    orchestration_service=orchestration,
    fork_service=fork,
  )
  return form, fork, instantiation


async def _run_batch_with_topics(db_session, *, topic_specs: list[tuple]):
  seed = await _seed_topic_meeting_batch_template(db_session)
  await _seed_production_template(
    db_session,
    admin_id=seed["admin"].id,
    department_id=seed["department"].id,
  )
  form, fork, instantiation = _build_services(db_session)

  editors = seed["editors"]
  snapshot = {
    "copywriters": ParticipantsSnapshotEntry(
      mode="subset",
      user_ids=[editor.id for editor in editors[: len(topic_specs)]],
    )
  }
  run = await instantiation.instantiate_graph_template(
    actor=seed["admin"],
    template_id=seed["template"].id,
    inputs={"theme": "WFK 批次", "manager_user_id": str(seed["manager"].id)},
    participants_snapshot=snapshot,
    department_id=seed["department"].id,
  )
  await db_session.commit()

  editor_tasks = {}
  for editor, (title, author) in zip(editors[: len(topic_specs)], topic_specs, strict=True):
    task = next(t for t in run.activated_tasks if t.assignee_id == editor.id)
    submit = await form.submit_capture(
      actor=editor,
      task_id=task.id,
      topics=[TopicCaptureRow(title=title)],
    )
    editor_tasks[author.id] = (editor, submit.topics[0].topic_id, title)

  return {**seed, "run": run, "form": form, "fork": fork, "editor_tasks": editor_tasks}


@pytest.mark.asyncio
async def test_wfk_fork_five_topics_five_child_runs(db_session) -> None:
  seed = await _seed_topic_meeting_batch_template(db_session)
  await _seed_production_template(
    db_session,
    admin_id=seed["admin"].id,
    department_id=seed["department"].id,
  )
  form, fork, instantiation = _build_services(db_session)
  author = seed["editors"][0]

  run = await instantiation.instantiate_graph_template(
    actor=seed["admin"],
    template_id=seed["template"].id,
    inputs={"theme": "WFK五题", "manager_user_id": str(seed["manager"].id)},
    participants_snapshot={
      "copywriters": ParticipantsSnapshotEntry(mode="subset", user_ids=[author.id])
    },
    department_id=seed["department"].id,
  )
  await db_session.commit()

  await form.submit_capture(
    actor=author,
    task_id=run.activated_tasks[0].id,
    topics=[TopicCaptureRow(title=f"题{i}") for i in range(5)],
  )

  approved = [
    ApprovedTopic(topic_id=uuid4(), title=f"题{i}", script_author_id=author.id)
    for i in range(5)
  ]
  fork_result = await fork.fork_production_runs(
    actor=seed["manager"],
    batch_instance_id=run.instance.id,
    approved_topics=approved,
  )
  assert fork_result.forked_count == 5
  assert fork_result.skipped_count == 0
  assert len(fork_result.child_instance_ids) == 5

  children = list(
    await db_session.scalars(
      select(WorkflowGraphInstance).where(
        WorkflowGraphInstance.parent_instance_id == run.instance.id
      )
    )
  )
  assert len(children) == 5


@pytest.mark.asyncio
async def test_wfk_same_author_two_topics_two_script_tasks(db_session) -> None:
  seed = await _seed_topic_meeting_batch_template(db_session)
  await _seed_production_template(
    db_session,
    admin_id=seed["admin"].id,
    department_id=seed["department"].id,
  )
  form, fork, _instantiation = _build_services(db_session)
  author = seed["editors"][0]

  snapshot = {"copywriters": ParticipantsSnapshotEntry(mode="subset", user_ids=[author.id])}
  run = await _instantiation.instantiate_graph_template(
    actor=seed["admin"],
    template_id=seed["template"].id,
    inputs={"theme": "小陈两题", "manager_user_id": str(seed["manager"].id)},
    participants_snapshot=snapshot,
    department_id=seed["department"].id,
  )
  await db_session.commit()

  task = run.activated_tasks[0]
  await form.submit_capture(
    actor=author,
    task_id=task.id,
    topics=[TopicCaptureRow(title="题1"), TopicCaptureRow(title="题2")],
  )

  approved = [
    ApprovedTopic(topic_id=uuid4(), title="题1", script_author_id=author.id),
    ApprovedTopic(topic_id=uuid4(), title="题2", script_author_id=author.id),
  ]
  fork_result = await fork.fork_production_runs(
    actor=seed["manager"],
    batch_instance_id=run.instance.id,
    approved_topics=approved,
  )
  assert fork_result.forked_count == 2

  script_tasks = list(
    await db_session.scalars(
      select(Task).where(
        Task.assignee_id == author.id,
        Task.source_type == TaskSourceType.TEMPLATE,
      )
    )
  )
  n3_tasks = [
    t
    for t in script_tasks
    if (t.extra_metadata or {}).get("template_node_key") == "N3_SCRIPT_WRITE"
    and t.status == TaskStatus.DOING
  ]
  assert len(n3_tasks) == 2


@pytest.mark.asyncio
async def test_wfk_idempotent_second_fork_skips(db_session) -> None:
  seed = await _seed_topic_meeting_batch_template(db_session)
  await _seed_production_template(
    db_session,
    admin_id=seed["admin"].id,
    department_id=seed["department"].id,
  )
  form, fork, instantiation = _build_services(db_session)
  author = seed["editors"][0]

  run = await instantiation.instantiate_graph_template(
    actor=seed["admin"],
    template_id=seed["template"].id,
    inputs={"theme": "幂等", "manager_user_id": str(seed["manager"].id)},
    participants_snapshot={"copywriters": ParticipantsSnapshotEntry(mode="subset", user_ids=[author.id])},
    department_id=seed["department"].id,
  )
  await db_session.commit()
  await form.submit_capture(
    actor=author,
    task_id=run.activated_tasks[0].id,
    topics=[TopicCaptureRow(title="题A")],
  )

  topic_id = uuid4()
  approved = [ApprovedTopic(topic_id=topic_id, title="题A", script_author_id=author.id)]

  first = await fork.fork_production_runs(
    actor=seed["manager"],
    batch_instance_id=run.instance.id,
    approved_topics=approved,
  )
  second = await fork.fork_production_runs(
    actor=seed["manager"],
    batch_instance_id=run.instance.id,
    approved_topics=approved,
  )
  assert first.forked_count == 1
  assert second.forked_count == 0
  assert second.skipped_count == 1
  assert second.fork_status == "completed"

  children = list(
    await db_session.scalars(
      select(WorkflowGraphInstance).where(
        WorkflowGraphInstance.parent_instance_id == run.instance.id
      )
    )
  )
  assert len(children) == 1

  child = children[0]
  assert child.parent_instance_id == run.instance.id
  root = await db_session.get(Task, child.source_id)
  assert root is not None
  assert root.parent_task_id == run.root_task.id
