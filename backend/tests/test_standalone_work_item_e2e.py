"""API-level E2E for the standalone Work Item P0 batch (minimum regression matrix).

Scenario map (pre-release gate agreed for Iteration 3F convergence):
  A  direct-assignment full lifecycle closure
  B  return-for-rework cycle with preserved audit history
  C  delegation at TODO / DOING, forbidden at REVIEW, replay-safe
  D  candidate discovery consistent with command authorization (cross-department)
  E  conflicting-command semantics (true DB races live in the postgres module)
  F  list bucket exclusivity, count/items consistency, no duplicates
  G  graph-backed human-task compatibility — covered by the existing suites
     (test_api phase3/4/5, test_workflow_graph_iteration3 / 3f, tce_phase1-3),
     which must stay green alongside this module.

Everything here drives the real HTTP API through the ASGI app; the DB session
factory is only used for data-invariant assertions (graph rows, audit rows).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.dependencies import (
  get_job_queue_publisher,
  get_notification_queue_publisher,
  get_openai_client,
)
from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.main import create_app
from app.models import (
  Base,
  NotificationMessage,
  TaskLog,
  WorkflowGraphInstance,
  WorkflowHumanTaskLink,
  WorkflowNodeInstance,
)
from tests.test_api import FakeRouterOpenAIClient, InMemoryQueuePublisher

TEST_JWT_SECRET = "test-secret-key-with-32-bytes-minimum!!"
PASSWORD = "StrongPassword123!"


@dataclass(slots=True)
class E2EUser:
  user_id: str
  email: str
  headers: dict[str, str]


@dataclass(slots=True)
class E2EEnv:
  client: AsyncClient
  session_factory: async_sessionmaker[AsyncSession]
  queue_publisher: InMemoryQueuePublisher
  admin: E2EUser
  lead: E2EUser  # "L2": tech department manager, org publish rights via managed scope
  worker_a: E2EUser  # "L4": plain tech employee
  worker_b: E2EUser  # second plain tech employee
  sales_demo: E2EUser  # employee in another department ("demo.success")
  tech_department_id: str
  sales_department_id: str


@pytest_asyncio.fixture
async def e2e(tmp_path: Path) -> AsyncIterator[E2EEnv]:
  settings = Settings(
    postgres_dsn="sqlite+aiosqlite:///:memory:",
    storage_base_path=str(tmp_path / ".storage"),
    storage_bucket="filum-e2e",
    jwt_secret_key=TEST_JWT_SECRET,
    frontend_app_url="https://app.example.com",
    openai_api_key="test-openai-key",
    web_push_public_key="test-public-key",
    web_push_private_key="test-private-key",
    web_push_subject="mailto:test@example.com",
    task_center_v2_enabled=True,
    workflow_standalone_manual_tasks_enabled=True,
  )
  engine = create_async_engine(
    settings.postgres_dsn,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
  )
  session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
  async with engine.begin() as connection:
    await connection.run_sync(Base.metadata.create_all)

  application = create_app()
  application.state.error_tracking_session_factory = session_factory
  fake_openai_client = FakeRouterOpenAIClient()
  queue_publisher = InMemoryQueuePublisher(
    session_factory=session_factory,
    settings=settings,
    openai_client=fake_openai_client,
  )

  async def override_get_db_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
      yield session

  application.dependency_overrides[get_db_session] = override_get_db_session
  application.dependency_overrides[get_settings] = lambda: settings
  application.dependency_overrides[get_notification_queue_publisher] = lambda: queue_publisher
  application.dependency_overrides[get_job_queue_publisher] = lambda: queue_publisher
  application.dependency_overrides[get_openai_client] = lambda: fake_openai_client

  transport = ASGITransport(app=application)
  async with AsyncClient(transport=transport, base_url="http://testserver") as client:
    env = await _seed_org(client, session_factory, queue_publisher)
    yield env

  application.dependency_overrides.clear()
  await engine.dispose()


async def _login(client: AsyncClient, email: str) -> dict[str, str]:
  response = await client.post(
    "/api/v1/auth/login",
    json={"email": email, "password": PASSWORD},
  )
  assert response.status_code == 200, response.text
  return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _create_employee(client: AsyncClient, admin_headers: dict[str, str], email: str) -> str:
  response = await client.post(
    "/api/v1/users",
    headers=admin_headers,
    json={"email": email, "password": PASSWORD, "role": "employee", "status": "active"},
  )
  assert response.status_code == 201, response.text
  return response.json()["id"]


async def _seed_org(
  client: AsyncClient,
  session_factory: async_sessionmaker[AsyncSession],
  queue_publisher: InMemoryQueuePublisher,
) -> E2EEnv:
  bootstrap = await client.post(
    "/api/v1/auth/bootstrap-admin",
    json={
      "email": "e2e-admin@example.com",
      "password": PASSWORD,
      "real_name": "管理员",
      "employee_no": "EMP-E2E-ROOT",
    },
  )
  assert bootstrap.status_code == 201, bootstrap.text
  admin_id = bootstrap.json()["id"]
  admin_headers = await _login(client, "e2e-admin@example.com")

  lead_id = await _create_employee(client, admin_headers, "e2e-lead@example.com")
  worker_a_id = await _create_employee(client, admin_headers, "e2e-worker-a@example.com")
  worker_b_id = await _create_employee(client, admin_headers, "e2e-worker-b@example.com")
  sales_demo_id = await _create_employee(client, admin_headers, "demo.success@example.com")

  tech_response = await client.post(
    "/api/v1/departments",
    headers=admin_headers,
    json={"name": "技术部", "code": "e2e-tech", "manager_id": lead_id},
  )
  assert tech_response.status_code == 201, tech_response.text
  tech_department_id = tech_response.json()["id"]
  sales_response = await client.post(
    "/api/v1/departments",
    headers=admin_headers,
    json={"name": "销售部", "code": "e2e-sales"},
  )
  assert sales_response.status_code == 201, sales_response.text
  sales_department_id = sales_response.json()["id"]

  for user_id, employee_no, real_name, department_id in (
    (lead_id, "EMP-E2E-L2", "技术负责人", tech_department_id),
    (worker_a_id, "EMP-E2E-A", "技术员工甲", tech_department_id),
    (worker_b_id, "EMP-E2E-B", "技术员工乙", tech_department_id),
    (sales_demo_id, "EMP-E2E-DEMO", "销售演示账号", sales_department_id),
  ):
    profile_response = await client.post(
      "/api/v1/profiles",
      headers=admin_headers,
      json={
        "user_id": user_id,
        "employee_no": employee_no,
        "real_name": real_name,
        "department_id": department_id,
      },
    )
    assert profile_response.status_code == 201, profile_response.text

  return E2EEnv(
    client=client,
    session_factory=session_factory,
    queue_publisher=queue_publisher,
    admin=E2EUser(admin_id, "e2e-admin@example.com", admin_headers),
    lead=E2EUser(lead_id, "e2e-lead@example.com", await _login(client, "e2e-lead@example.com")),
    worker_a=E2EUser(
      worker_a_id, "e2e-worker-a@example.com", await _login(client, "e2e-worker-a@example.com")
    ),
    worker_b=E2EUser(
      worker_b_id, "e2e-worker-b@example.com", await _login(client, "e2e-worker-b@example.com")
    ),
    sales_demo=E2EUser(
      sales_demo_id, "demo.success@example.com", await _login(client, "demo.success@example.com")
    ),
    tech_department_id=tech_department_id,
    sales_department_id=sales_department_id,
  )


async def _create_task(
  env: E2EEnv,
  *,
  creator: E2EUser,
  assignee: E2EUser,
  title: str | None = None,
  watcher_user_ids: list[str] | None = None,
) -> dict:
  response = await env.client.post(
    "/api/v1/tasks",
    headers=creator.headers,
    json={
      "title": title or f"E2E 任务 {uuid4().hex[:8]}",
      "assignee_id": assignee.user_id,
      "watcher_user_ids": watcher_user_ids or [],
    },
  )
  assert response.status_code == 201, response.text
  return response.json()


async def _inbox(env: E2EEnv, user: E2EUser, *, limit: int = 50, cursor: str | None = None) -> dict:
  params: dict[str, object] = {"limit": limit}
  if cursor is not None:
    params["cursor"] = cursor
  response = await env.client.get("/api/v1/task-center/inbox", headers=user.headers, params=params)
  assert response.status_code == 200, response.text
  return response.json()


async def _tracking(env: E2EEnv, user: E2EUser, *, limit: int = 50) -> dict:
  response = await env.client.get(
    "/api/v1/task-center/tracking", headers=user.headers, params={"limit": limit}
  )
  assert response.status_code == 200, response.text
  return response.json()


async def _history(env: E2EEnv, user: E2EUser, *, limit: int = 50) -> dict:
  response = await env.client.get(
    "/api/v1/task-center/history", headers=user.headers, params={"limit": limit}
  )
  assert response.status_code == 200, response.text
  return response.json()


def _find(items: list[dict], task_id: str) -> dict | None:
  return next((item for item in items if item["task_id"] == task_id), None)


def _actions(entry: dict) -> set[str]:
  return {option["action"] for option in entry.get("available_actions", [])}


async def _start_work(env: E2EEnv, user: E2EUser, task_id: str) -> dict:
  response = await env.client.patch(
    f"/api/v1/tasks/{task_id}/status", headers=user.headers, json={"status": "doing"}
  )
  assert response.status_code == 200, response.text
  return response.json()


async def _submit(env: E2EEnv, user: E2EUser, task_id: str, summary: str = "交付说明") -> dict:
  response = await env.client.post(
    f"/api/v1/tasks/{task_id}/deliverable", headers=user.headers, json={"summary": summary}
  )
  assert response.status_code == 200, response.text
  return response.json()


async def _review(env: E2EEnv, user: E2EUser, task_id: str, action: str, comment: str | None = None) -> dict:
  response = await env.client.post(
    f"/api/v1/tasks/{task_id}/review",
    headers=user.headers,
    json={"action": action, "comment": comment},
  )
  assert response.status_code == 200, response.text
  return response.json()


async def _assert_no_graph_rows(env: E2EEnv, task_id: str) -> None:
  async with env.session_factory() as session:
    link = await session.scalar(
      select(WorkflowHumanTaskLink).where(WorkflowHumanTaskLink.task_id == UUID(task_id))
    )
    assert link is None
    assert (await session.scalar(select(func.count()).select_from(WorkflowGraphInstance))) == 0
    assert (await session.scalar(select(func.count()).select_from(WorkflowNodeInstance))) == 0


async def _count_delegate_logs(env: E2EEnv, task_id: str) -> int:
  async with env.session_factory() as session:
    logs = list(await session.scalars(select(TaskLog).where(TaskLog.task_id == UUID(task_id))))
  return sum(1 for log in logs if (log.detail or {}).get("action") == "delegated")


async def _count_assignment_notifications(env: E2EEnv, task_id: str, recipient_id: str) -> int:
  async with env.session_factory() as session:
    return int(
      await session.scalar(
        select(func.count())
        .select_from(NotificationMessage)
        .where(
          NotificationMessage.source_id == UUID(task_id),
          NotificationMessage.message_type == "task_assigned",
          NotificationMessage.recipient_user_id == UUID(recipient_id),
        )
      )
      or 0
    )


# ---------------------------------------------------------------------------
# Scenario A: direct assignment full lifecycle closure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_a_direct_lifecycle_closure(e2e: E2EEnv) -> None:
  env = e2e
  task = await _create_task(env, creator=env.lead, assignee=env.worker_a)
  task_id = task["id"]
  assert task["execution_mode"] == "standalone"
  assert task["assignment_mode"] == "direct"

  # Creator tracks, assignee acts.
  lead_tracking = await _tracking(env, env.lead)
  assert _find(lead_tracking["items"], task_id) is not None
  worker_inbox_entry = _find((await _inbox(env, env.worker_a))["items"], task_id)
  assert worker_inbox_entry is not None
  assert worker_inbox_entry["requires_action"] is True
  assert worker_inbox_entry["current_action_owner_id"] == env.worker_a.user_id
  assert _actions(worker_inbox_entry) == {"start_work", "delegate_assignment"}

  await _start_work(env, env.worker_a, task_id)
  submitted = await _submit(env, env.worker_a, task_id)
  assert submitted["status"] == "review"

  # Assignee is no longer the action owner; the creator's inbox gains the
  # review entry (the P0 REVIEW closure fix).
  assert submitted["current_action_owner_id"] == env.lead.user_id
  assert _find((await _inbox(env, env.worker_a))["items"], task_id) is None
  lead_review_entry = _find((await _inbox(env, env.lead))["items"], task_id)
  assert lead_review_entry is not None
  assert lead_review_entry["requires_action"] is True
  assert lead_review_entry["action_type"] == "review_deliverable"
  assert _actions(lead_review_entry) == {"approve_deliverable", "return_for_rework"}

  approved = await _review(env, env.lead, task_id, "approve", comment="验收通过")
  assert approved["status"] == "done"

  # Both parties see the task in history; it left both inboxes.
  assert _find((await _history(env, env.lead))["items"], task_id) is not None
  assert _find((await _history(env, env.worker_a))["items"], task_id) is not None
  assert _find((await _inbox(env, env.lead))["items"], task_id) is None

  # Data invariant: the standalone lifecycle completed without materialising
  # any graph instance, node instance or human-task link.
  await _assert_no_graph_rows(env, task_id)


# ---------------------------------------------------------------------------
# Scenario B: return-for-rework cycle, audit history preserved
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_b_rework_cycle_preserves_history(e2e: E2EEnv) -> None:
  env = e2e
  task = await _create_task(env, creator=env.lead, assignee=env.worker_a)
  task_id = task["id"]

  await _start_work(env, env.worker_a, task_id)
  await _submit(env, env.worker_a, task_id, summary="第一版交付")
  returned = await _review(env, env.lead, task_id, "return_for_rework", comment="需要修改")
  assert returned["status"] == "doing"

  # The assignee regains the action after rework and can resubmit.
  rework_entry = _find((await _inbox(env, env.worker_a))["items"], task_id)
  assert rework_entry is not None
  assert rework_entry["requires_action"] is True
  assert rework_entry["current_action_owner_id"] == env.worker_a.user_id
  assert "submit_deliverable" in _actions(rework_entry)

  await _submit(env, env.worker_a, task_id, summary="第二版交付")
  approved = await _review(env, env.lead, task_id, "approve")
  assert approved["status"] == "done"

  # Audit history is append-only: both submissions and the rework decision
  # remain visible in the activity log.
  activity_response = await env.client.get(
    f"/api/v1/tasks/{task_id}/activity", headers=env.lead.headers
  )
  assert activity_response.status_code == 200
  log_details = [
    entry["log"]["detail"]
    for entry in activity_response.json()
    if entry["entry_type"] == "log" and entry["log"] is not None
  ]
  submit_summaries = [
    detail.get("summary") for detail in log_details if detail.get("action") == "submit_deliverable"
  ]
  assert submit_summaries == ["第一版交付", "第二版交付"]
  assert any(detail.get("action") == "return_for_rework" for detail in log_details)
  assert any(detail.get("action") == "approve_completion" for detail in log_details)


# ---------------------------------------------------------------------------
# Scenario C: delegation at TODO / DOING, forbidden at REVIEW, replay-safe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_c_delegate_in_todo(e2e: E2EEnv) -> None:
  env = e2e
  task = await _create_task(env, creator=env.lead, assignee=env.worker_a)
  task_id = task["id"]

  delegate_response = await env.client.post(
    f"/api/v1/tasks/{task_id}/delegate",
    headers=env.worker_a.headers,
    json={"assignee_id": env.worker_b.user_id, "reason": "工作交接"},
  )
  assert delegate_response.status_code == 200, delegate_response.text
  assert delegate_response.json()["assignee_id"] == env.worker_b.user_id

  # Old handler out of the inbox, new handler in with correct actions.
  assert _find((await _inbox(env, env.worker_a))["items"], task_id) is None
  new_entry = _find((await _inbox(env, env.worker_b))["items"], task_id)
  assert new_entry is not None
  assert _actions(new_entry) == {"start_work", "delegate_assignment"}

  # The previous handler's commands are now rejected. After the transfer the
  # old handler has no relation to the task at all, so the visibility layer
  # answers 404 (anti-enumeration) rather than 403 — either is a rejection.
  stale_start = await env.client.patch(
    f"/api/v1/tasks/{task_id}/status", headers=env.worker_a.headers, json={"status": "doing"}
  )
  assert stale_start.status_code in {403, 404}
  stale_submit = await env.client.post(
    f"/api/v1/tasks/{task_id}/deliverable",
    headers=env.worker_a.headers,
    json={"summary": "越权提交"},
  )
  assert stale_submit.status_code in {403, 404}

  # Replaying the same delegate command must not produce a second transfer.
  replay = await env.client.post(
    f"/api/v1/tasks/{task_id}/delegate",
    headers=env.worker_a.headers,
    json={"assignee_id": env.worker_b.user_id, "reason": "工作交接"},
  )
  assert replay.status_code in {403, 404, 409}
  assert await _count_delegate_logs(env, task_id) == 1
  # Exactly one audit entry and one assignment notification for the transfer.
  assert await _count_assignment_notifications(env, task_id, env.worker_b.user_id) == 1


@pytest.mark.asyncio
async def test_scenario_c_delegate_in_doing(e2e: E2EEnv) -> None:
  env = e2e
  task = await _create_task(env, creator=env.lead, assignee=env.worker_a)
  task_id = task["id"]
  await _start_work(env, env.worker_a, task_id)

  delegate_response = await env.client.post(
    f"/api/v1/tasks/{task_id}/delegate",
    headers=env.worker_a.headers,
    json={"assignee_id": env.worker_b.user_id, "reason": "临时休假"},
  )
  assert delegate_response.status_code == 200, delegate_response.text

  # The task stays in DOING; the new handler can submit directly.
  entry = _find((await _inbox(env, env.worker_b))["items"], task_id)
  assert entry is not None
  assert entry["status"] == "doing"
  assert "submit_deliverable" in _actions(entry)
  submitted = await _submit(env, env.worker_b, task_id)
  assert submitted["status"] == "review"

  # No graph runtime rows were touched by the standalone delegate.
  await _assert_no_graph_rows(env, task_id)


@pytest.mark.asyncio
async def test_scenario_c_delegate_forbidden_in_review_stable_error(e2e: E2EEnv) -> None:
  env = e2e
  task = await _create_task(env, creator=env.lead, assignee=env.worker_a)
  task_id = task["id"]
  await _start_work(env, env.worker_a, task_id)
  await _submit(env, env.worker_a, task_id)

  response = await env.client.post(
    f"/api/v1/tasks/{task_id}/delegate",
    headers=env.worker_a.headers,
    json={"assignee_id": env.worker_b.user_id, "reason": "验收阶段转办"},
  )
  # Stable business error, not a generic failure: REVIEW is the creator's
  # acceptance step and is not delegable by product decision.
  assert response.status_code == 409
  assert "只有待处理或进行中的任务才能转办" in response.json()["detail"]


@pytest.mark.asyncio
async def test_scenario_c_admin_override_delegate_is_audited(e2e: E2EEnv) -> None:
  env = e2e
  task = await _create_task(env, creator=env.lead, assignee=env.worker_a)
  task_id = task["id"]

  response = await env.client.post(
    f"/api/v1/tasks/{task_id}/delegate",
    headers=env.admin.headers,
    json={"assignee_id": env.worker_b.user_id, "reason": "管理调度"},
  )
  assert response.status_code == 200, response.text

  async with env.session_factory() as session:
    logs = list(await session.scalars(select(TaskLog).where(TaskLog.task_id == UUID(task_id))))
  delegate_details = [
    (log.detail or {}) for log in logs if (log.detail or {}).get("action") == "delegated"
  ]
  assert len(delegate_details) == 1
  detail = delegate_details[0]
  assert detail["delegated_by_admin"] is True
  assert detail["reason"] == "管理调度"
  assert detail["previous_assignee_id"] == env.worker_a.user_id
  assert detail["assignee_id"] == env.worker_b.user_id


# ---------------------------------------------------------------------------
# Scenario D: candidate discovery consistent with command authorization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_d_candidates_match_authorization(e2e: E2EEnv) -> None:
  env = e2e

  # A plain employee cannot query the organization scope...
  denied = await env.client.get(
    "/api/v1/tasks/assignee-candidates",
    headers=env.worker_a.headers,
    params={"scope": "organization"},
  )
  assert denied.status_code == 403

  # ...and forging a cross-department assignee is rejected by the command too.
  forged = await env.client.post(
    "/api/v1/tasks",
    headers=env.worker_a.headers,
    json={"title": "伪造跨部门指派", "assignee_id": env.sales_demo.user_id},
  )
  assert forged.status_code == 403

  # The department lead's managed scope only returns the technical line.
  managed = await env.client.get(
    "/api/v1/tasks/assignee-candidates", headers=env.lead.headers, params={"scope": "managed"}
  )
  assert managed.status_code == 200
  managed_ids = {item["user_id"] for item in managed.json()}
  assert env.worker_a.user_id in managed_ids
  assert env.sales_demo.user_id not in managed_ids

  # Organization scope with search finds the cross-department account.
  org = await env.client.get(
    "/api/v1/tasks/assignee-candidates",
    headers=env.lead.headers,
    params={"scope": "organization", "q": "demo"},
  )
  assert org.status_code == 200
  org_ids = {item["user_id"] for item in org.json()}
  assert org_ids == {env.sales_demo.user_id}

  # And the lead can actually create the cross-department task (C1.5).
  task = await _create_task(env, creator=env.lead, assignee=env.sales_demo)
  entry = _find((await _inbox(env, env.sales_demo))["items"], task["id"])
  assert entry is not None
  assert entry["requires_action"] is True


@pytest.mark.asyncio
async def test_scenario_d_delegate_candidates_and_command_guards(e2e: E2EEnv) -> None:
  env = e2e
  task = await _create_task(env, creator=env.lead, assignee=env.worker_a)
  task_id = task["id"]

  # A bystander (not assignee, no admin override) can neither list candidates
  # nor delegate — candidate discovery matches command authorization. An
  # unrelated user gets 404 from the visibility layer (anti-enumeration).
  bystander_candidates = await env.client.get(
    f"/api/v1/tasks/{task_id}/delegate-candidates", headers=env.worker_b.headers
  )
  assert bystander_candidates.status_code in {403, 404}
  bystander_delegate = await env.client.post(
    f"/api/v1/tasks/{task_id}/delegate",
    headers=env.worker_b.headers,
    json={"assignee_id": env.worker_b.user_id, "reason": "越权转办"},
  )
  assert bystander_delegate.status_code in {403, 404}

  # The assignee's candidate list excludes the current handler and only
  # contains active users.
  candidates = await env.client.get(
    f"/api/v1/tasks/{task_id}/delegate-candidates", headers=env.worker_a.headers
  )
  assert candidates.status_code == 200
  candidate_ids = {item["user_id"] for item in candidates.json()}
  assert env.worker_a.user_id not in candidate_ids
  assert env.worker_b.user_id in candidate_ids

  # Delegating to a suspended account is rejected even if the id is forged.
  suspend = await env.client.patch(
    f"/api/v1/users/{env.worker_b.user_id}",
    headers=env.admin.headers,
    json={"status": "suspended"},
  )
  assert suspend.status_code == 200, suspend.text
  to_suspended = await env.client.post(
    f"/api/v1/tasks/{task_id}/delegate",
    headers=env.worker_a.headers,
    json={"assignee_id": env.worker_b.user_id, "reason": "转给停用账号"},
  )
  assert to_suspended.status_code in {403, 409}
  detail_response = await env.client.get(f"/api/v1/tasks/{task_id}", headers=env.worker_a.headers)
  assert detail_response.json()["assignee_id"] == env.worker_a.user_id


# ---------------------------------------------------------------------------
# Scenario E: conflicting command semantics (API level; DB races in postgres suite)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_e_second_delegate_after_transfer_conflicts(e2e: E2EEnv) -> None:
  env = e2e
  task = await _create_task(env, creator=env.lead, assignee=env.worker_a)
  task_id = task["id"]

  # Assignee and admin race to delegate; whoever lands second must fail and
  # exactly one transfer may be recorded.
  first = await env.client.post(
    f"/api/v1/tasks/{task_id}/delegate",
    headers=env.worker_a.headers,
    json={"assignee_id": env.worker_b.user_id, "reason": "先到"},
  )
  assert first.status_code == 200
  second = await env.client.post(
    f"/api/v1/tasks/{task_id}/delegate",
    headers=env.admin.headers,
    json={"assignee_id": env.worker_b.user_id, "reason": "后到"},
  )
  assert second.status_code == 409
  assert await _count_delegate_logs(env, task_id) == 1

  detail = await env.client.get(f"/api/v1/tasks/{task_id}", headers=env.admin.headers)
  assert detail.json()["assignee_id"] == env.worker_b.user_id


@pytest.mark.asyncio
async def test_scenario_e_delegate_then_stale_submit_rejected(e2e: E2EEnv) -> None:
  env = e2e
  task = await _create_task(env, creator=env.lead, assignee=env.worker_a)
  task_id = task["id"]
  await _start_work(env, env.worker_a, task_id)

  delegate_response = await env.client.post(
    f"/api/v1/tasks/{task_id}/delegate",
    headers=env.worker_a.headers,
    json={"assignee_id": env.worker_b.user_id, "reason": "交接"},
  )
  assert delegate_response.status_code == 200

  # A submit racing with (landing after) the delegate must be rejected and the
  # task state stays consistent for the new handler. The old handler has lost
  # visibility of the task entirely, hence 404 instead of 403.
  stale_submit = await env.client.post(
    f"/api/v1/tasks/{task_id}/deliverable",
    headers=env.worker_a.headers,
    json={"summary": "旧办理人迟到的提交"},
  )
  assert stale_submit.status_code in {403, 404}
  detail = await env.client.get(f"/api/v1/tasks/{task_id}", headers=env.worker_b.headers)
  body = detail.json()
  assert body["status"] == "doing"
  assert body["assignee_id"] == env.worker_b.user_id


# ---------------------------------------------------------------------------
# Scenario F: bucket exclusivity, pagination consistency, no duplicates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_f_review_creator_not_duplicated_across_buckets(e2e: E2EEnv) -> None:
  env = e2e
  task = await _create_task(env, creator=env.lead, assignee=env.worker_a)
  task_id = task["id"]
  await _start_work(env, env.worker_a, task_id)
  await _submit(env, env.worker_a, task_id)

  inbox_items = (await _inbox(env, env.lead))["items"]
  tracking_items = (await _tracking(env, env.lead))["items"]
  assert _find(inbox_items, task_id) is not None
  assert _find(tracking_items, task_id) is None

  # Entries are unique within each bucket.
  inbox_ids = [item["task_id"] for item in inbox_items]
  assert len(inbox_ids) == len(set(inbox_ids))


@pytest.mark.asyncio
async def test_scenario_f_multi_relation_users_appear_once(e2e: E2EEnv) -> None:
  env = e2e

  # Creator == assignee: one inbox entry only.
  self_task = await _create_task(env, creator=env.lead, assignee=env.lead)
  inbox_items = (await _inbox(env, env.lead))["items"]
  assert len([item for item in inbox_items if item["task_id"] == self_task["id"]]) == 1

  # Creator who is also an explicit watcher: one tracking entry only.
  watched = await _create_task(
    env, creator=env.lead, assignee=env.worker_a, watcher_user_ids=[env.lead.user_id]
  )
  tracking_items = (await _tracking(env, env.lead))["items"]
  assert len([item for item in tracking_items if item["task_id"] == watched["id"]]) == 1

  # Admin (creator + management + watcher) still sees a single entry.
  admin_task = await _create_task(
    env, creator=env.admin, assignee=env.worker_a, watcher_user_ids=[env.admin.user_id]
  )
  admin_tracking = (await _tracking(env, env.admin))["items"]
  assert len([item for item in admin_tracking if item["task_id"] == admin_task["id"]]) == 1


@pytest.mark.asyncio
async def test_scenario_f_inbox_pagination_no_duplicates(e2e: E2EEnv) -> None:
  env = e2e
  created_ids = {
    (await _create_task(env, creator=env.lead, assignee=env.worker_a))["id"] for _ in range(3)
  }

  collected: list[str] = []
  cursor: str | None = None
  for _ in range(10):
    page = await _inbox(env, env.worker_a, limit=1, cursor=cursor)
    collected.extend(item["task_id"] for item in page["items"])
    if not page["pagination"]["has_more"]:
      break
    cursor = page["pagination"]["next_cursor"]

  assert len(collected) == len(set(collected))
  assert created_ids.issubset(set(collected))


# ---------------------------------------------------------------------------
# Backend invariant: assignment_mode source constraint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handshake_assignment_mode_rejected_with_stable_error(e2e: E2EEnv) -> None:
  env = e2e
  response = await env.client.post(
    "/api/v1/tasks",
    headers=env.lead.headers,
    json={
      "title": "请求未实现的握手模式",
      "assignee_id": env.worker_a.user_id,
      "assignment_mode": "handshake",
    },
  )
  assert response.status_code == 409
  assert "unsupported_assignment_mode" in response.json()["detail"]

  # Explicit "direct" is accepted and persisted.
  accepted = await env.client.post(
    "/api/v1/tasks",
    headers=env.lead.headers,
    json={
      "title": "显式 direct 模式",
      "assignee_id": env.worker_a.user_id,
      "assignment_mode": "direct",
    },
  )
  assert accepted.status_code == 201
  assert accepted.json()["assignment_mode"] == "direct"
