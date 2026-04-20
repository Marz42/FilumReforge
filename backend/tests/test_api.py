from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
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
from app.models import Base
from app.workers.arq_worker import (
  REBUILD_ALL_DOCUMENT_EMBEDDINGS_JOB,
  REBUILD_DOCUMENT_EMBEDDINGS_JOB,
)
from app.workers.jobs import rebuild_all_document_embeddings, rebuild_document_embeddings

TEST_JWT_SECRET = "test-secret-key-with-32-bytes-minimum!!"


class FakeRouterOpenAIClient:
  def __init__(self) -> None:
    self.chat_calls = 0

  async def create_embeddings(self, *, inputs, model=None):  # noqa: ANN001
    embeddings: list[list[float]] = []
    for raw_text in inputs:
      text = str(raw_text).lower()
      embeddings.append(
        [
          float(text.count("入职") + text.count("onboarding")),
          float(text.count("采购") + text.count("purchase")),
          float(text.count("审批") + text.count("approval")),
        ]
      )
    return embeddings

  async def create_chat_completion(self, **kwargs):  # noqa: ANN001
    self.chat_calls += 1
    if self.chat_calls == 1:
      return SimpleNamespace(
        choices=[
          SimpleNamespace(
            message=SimpleNamespace(
              content=None,
              tool_calls=[
                SimpleNamespace(
                  id="tool-call-1",
                  function=SimpleNamespace(
                    name="search_documents",
                    arguments='{"query":"入职流程","limit":3}',
                  ),
                )
              ],
            )
          )
        ]
      )

    return SimpleNamespace(
      choices=[
        SimpleNamespace(
          message=SimpleNamespace(
            content="根据知识库，入职流程需要先提交材料，再开通账号。",
            tool_calls=[],
          )
        )
      ]
    )


class InMemoryQueuePublisher:
  def __init__(
    self,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    openai_client: FakeRouterOpenAIClient,
  ) -> None:
    self.payloads: list[dict[str, object]] = []
    self.jobs: list[tuple[str, tuple[object, ...]]] = []
    self._session_factory = session_factory
    self._settings = settings
    self._openai_client = openai_client

  async def publish(self, payload: dict[str, object]) -> None:
    self.payloads.append(payload)

  async def enqueue(self, job_name: str, *args: object) -> None:
    self.jobs.append((job_name, args))
    async with self._session_factory() as session:
      if job_name == REBUILD_DOCUMENT_EMBEDDINGS_JOB:
        await rebuild_document_embeddings(
          session=session,
          document_id=str(args[0]),
          settings=self._settings,
          openai_client=self._openai_client,
        )
        return
      if job_name == REBUILD_ALL_DOCUMENT_EMBEDDINGS_JOB:
        await rebuild_all_document_embeddings(
          session=session,
          settings=self._settings,
          openai_client=self._openai_client,
        )
        return
    raise AssertionError(f"unexpected job: {job_name}")


@pytest_asyncio.fixture
async def api_client(
  tmp_path: Path,
) -> AsyncIterator[tuple[AsyncClient, InMemoryQueuePublisher]]:
  settings = Settings(
    postgres_dsn="sqlite+aiosqlite:///:memory:",
    storage_base_path=str(tmp_path / ".storage"),
    storage_bucket="filum-test",
    jwt_secret_key=TEST_JWT_SECRET,
    openai_api_key="test-openai-key",
    web_push_private_key="test-private-key",
    web_push_subject="mailto:test@example.com",
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
  fake_openai_client = FakeRouterOpenAIClient()
  queue_publisher = InMemoryQueuePublisher(
    session_factory=session_factory,
    settings=settings,
    openai_client=fake_openai_client,
  )

  async def override_get_db_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
      yield session

  def override_get_settings() -> Settings:
    return settings

  def override_get_notification_queue_publisher() -> InMemoryQueuePublisher:
    return queue_publisher

  def override_get_job_queue_publisher() -> InMemoryQueuePublisher:
    return queue_publisher

  def override_get_openai_client() -> FakeRouterOpenAIClient:
    return fake_openai_client

  application.dependency_overrides[get_db_session] = override_get_db_session
  application.dependency_overrides[get_settings] = override_get_settings
  application.dependency_overrides[get_notification_queue_publisher] = (
    override_get_notification_queue_publisher
  )
  application.dependency_overrides[get_job_queue_publisher] = override_get_job_queue_publisher
  application.dependency_overrides[get_openai_client] = override_get_openai_client

  transport = ASGITransport(app=application)
  async with AsyncClient(transport=transport, base_url="http://testserver") as client:
    yield client, queue_publisher

  application.dependency_overrides.clear()
  await engine.dispose()


async def bootstrap_and_login(client: AsyncClient) -> tuple[dict[str, str], dict[str, object]]:
  bootstrap_response = await client.post(
    "/api/v1/auth/bootstrap-admin",
    json={
      "email": "admin@example.com",
      "password": "StrongPassword123!",
      "real_name": "管理员",
      "employee_no": "EMP-ROOT",
    },
  )
  assert bootstrap_response.status_code == 201

  login_response = await client.post(
    "/api/v1/auth/login",
    json={
      "email": "admin@example.com",
      "password": "StrongPassword123!",
    },
  )
  assert login_response.status_code == 200
  payload = login_response.json()
  headers = {"Authorization": f"Bearer {payload['access_token']}"}
  return headers, payload


async def login(client: AsyncClient, *, email: str, password: str) -> dict[str, str]:
  response = await client.post(
    "/api/v1/auth/login",
    json={
      "email": email,
      "password": password,
    },
  )
  assert response.status_code == 200
  payload = response.json()
  return {"Authorization": f"Bearer {payload['access_token']}"}


@pytest.mark.asyncio
async def test_auth_and_users_api_flow(api_client) -> None:
  client, _ = api_client

  unauthorized_response = await client.get("/api/v1/users")
  assert unauthorized_response.status_code == 401

  headers, login_payload = await bootstrap_and_login(client)

  me_response = await client.get("/api/v1/auth/me", headers=headers)
  assert me_response.status_code == 200
  assert me_response.json()["email"] == "admin@example.com"

  refresh_response = await client.post(
    "/api/v1/auth/refresh",
    json={"refresh_token": login_payload["refresh_token"]},
  )
  assert refresh_response.status_code == 200
  assert refresh_response.json()["token_type"] == "bearer"

  create_user_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "hr@example.com",
      "password": "StrongPassword123!",
      "role": "hr",
      "status": "active",
    },
  )
  assert create_user_response.status_code == 201
  user_id = create_user_response.json()["id"]

  list_users_response = await client.get("/api/v1/users", headers=headers)
  assert list_users_response.status_code == 200
  assert len(list_users_response.json()) == 2

  update_user_response = await client.patch(
    f"/api/v1/users/{user_id}",
    headers=headers,
    json={"status": "suspended"},
  )
  assert update_user_response.status_code == 200
  assert update_user_response.json()["status"] == "suspended"

  openapi_response = await client.get("/openapi.json")
  assert openapi_response.status_code == 200
  assert "/api/v1/auth/login" in openapi_response.json()["paths"]


@pytest.mark.asyncio
async def test_overview_api_supports_board_cards_and_announcements(api_client) -> None:
  client, _ = api_client
  headers, _ = await bootstrap_and_login(client)

  me_response = await client.get("/api/v1/auth/me", headers=headers)
  assert me_response.status_code == 200
  admin_user_id = me_response.json()["id"]

  department_response = await client.post(
    "/api/v1/departments",
    headers=headers,
    json={
      "name": "财务行政部",
      "code": "finance-admin",
      "capabilities": ["publish_announcement"],
    },
  )
  assert department_response.status_code == 201
  department_id = department_response.json()["id"]

  board_response = await client.post(
    "/api/v1/board-cards",
    headers=headers,
    json={
      "scope_department_id": None,
      "title": "公司值班提醒",
      "content_md": "请查看本周值班安排。",
    },
  )
  assert board_response.status_code == 201
  assert board_response.json()["scope_label"] == "公司"

  announcement_response = await client.post(
    "/api/v1/announcements",
    headers=headers,
    json={
      "publisher_department_id": department_id,
      "title": "办公区维护通知",
      "content_md": "今晚进行网络维护。",
    },
  )
  assert announcement_response.status_code == 201
  announcement_id = announcement_response.json()["id"]

  task_response = await client.post(
    "/api/v1/tasks",
    headers=headers,
    json={
      "title": "补齐总览首页",
      "assignee_id": admin_user_id,
      "priority": "high",
    },
  )
  assert task_response.status_code == 201

  overview_response = await client.get("/api/v1/overview", headers=headers)
  assert overview_response.status_code == 200
  payload = overview_response.json()
  assert len(payload["board_cards"]) == 1
  assert len(payload["announcements"]) == 1
  assert len(payload["task_inbox"]) == 1
  assert payload["permissions"]["can_publish_board"] is True
  assert payload["permissions"]["can_publish_announcement"] is True

  withdraw_response = await client.post(
    f"/api/v1/announcements/{announcement_id}/withdraw",
    headers=headers,
  )
  assert withdraw_response.status_code == 204


@pytest.mark.asyncio
async def test_department_profile_task_and_attachment_api_flow(api_client) -> None:
  client, queue_publisher = api_client
  headers, _ = await bootstrap_and_login(client)

  employee_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "employee@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert employee_response.status_code == 201
  employee_id = employee_response.json()["id"]

  departments_response = await client.get("/api/v1/departments", headers=headers)
  assert departments_response.status_code == 200
  root_department = next(item for item in departments_response.json() if item["code"] == "root")

  create_department_response = await client.post(
    "/api/v1/departments",
    headers=headers,
    json={
      "name": "研发部",
      "code": "engineering",
      "parent_id": root_department["id"],
      "manager_id": employee_id,
      "sort_order": 10,
    },
  )
  assert create_department_response.status_code == 201
  department_id = create_department_response.json()["id"]

  profile_response = await client.post(
    "/api/v1/profiles",
    headers=headers,
    json={
      "user_id": employee_id,
      "employee_no": "EMP-001",
      "real_name": "研发工程师",
      "department_id": department_id,
      "custom_fields": {"skills": ["python"]},
    },
  )
  assert profile_response.status_code == 201

  task_response = await client.post(
    "/api/v1/tasks",
    headers=headers,
    json={
      "title": "完成基础模块开发",
      "assignee_id": employee_id,
      "priority": "high",
    },
  )
  assert task_response.status_code == 201
  task_id = task_response.json()["id"]
  assert task_response.json()["status"] == "todo"

  tasks_response = await client.get("/api/v1/tasks", headers=headers)
  assert tasks_response.status_code == 200
  assert len(tasks_response.json()) == 1

  tree_response = await client.get("/api/v1/departments/tree", headers=headers)
  assert tree_response.status_code == 200
  root_node = next(item for item in tree_response.json() if item["code"] == "root")
  assert any(child["id"] == department_id for child in root_node["children"])

  upload_response = await client.post(
    "/api/v1/attachments",
    headers=headers,
    data={
      "target_type": "task",
      "target_id": task_id,
      "visibility": "private",
      "relation": "primary",
    },
    files={"file": ("brief.txt", b"phase-1 attachment", "text/plain")},
  )
  assert upload_response.status_code == 201
  attachment_id = upload_response.json()["id"]
  assert upload_response.json()["download_url"] is not None

  list_attachments_response = await client.get(
    "/api/v1/attachments",
    headers=headers,
    params={"target_type": "task", "target_id": task_id},
  )
  assert list_attachments_response.status_code == 200
  assert len(list_attachments_response.json()) == 1

  delete_attachment_response = await client.delete(
    f"/api/v1/attachments/{attachment_id}",
    headers=headers,
  )
  assert delete_attachment_response.status_code == 200
  assert delete_attachment_response.json()["status"] == "deleted"

  assert len(queue_publisher.payloads) == 1
  assert queue_publisher.payloads[0]["message_type"] == "task_assigned"


@pytest.mark.asyncio
async def test_task_collaboration_and_stats_api_flow(api_client) -> None:
  client, queue_publisher = api_client
  headers, _ = await bootstrap_and_login(client)

  employee_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "employee@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert employee_response.status_code == 201
  employee_id = employee_response.json()["id"]

  departments_response = await client.get("/api/v1/departments", headers=headers)
  root_department = next(item for item in departments_response.json() if item["code"] == "root")

  create_department_response = await client.post(
    "/api/v1/departments",
    headers=headers,
    json={
      "name": "协同研发部",
      "code": "collab-engineering",
      "parent_id": root_department["id"],
      "manager_id": employee_id,
      "sort_order": 20,
    },
  )
  assert create_department_response.status_code == 201
  department_id = create_department_response.json()["id"]

  profile_response = await client.post(
    "/api/v1/profiles",
    headers=headers,
    json={
      "user_id": employee_id,
      "employee_no": "EMP-COLLAB-001",
      "real_name": "协同工程师",
      "department_id": department_id,
      "custom_fields": {"skills": ["fastapi"]},
    },
  )
  assert profile_response.status_code == 201

  overdue_task_response = await client.post(
    "/api/v1/tasks",
    headers=headers,
    json={
      "title": "清理逾期任务",
      "assignee_id": employee_id,
      "department_id": department_id,
      "due_date": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
    },
  )
  assert overdue_task_response.status_code == 201

  active_task_response = await client.post(
    "/api/v1/tasks",
    headers=headers,
    json={
      "title": "推进评论流",
      "assignee_id": employee_id,
      "department_id": department_id,
    },
  )
  assert active_task_response.status_code == 201
  active_task_id = active_task_response.json()["id"]

  employee_headers = await login(
    client,
    email="employee@example.com",
    password="StrongPassword123!",
  )
  for next_status in ("doing", "review", "done"):
    status_response = await client.patch(
      f"/api/v1/tasks/{active_task_id}/status",
      headers=employee_headers,
      json={"status": next_status},
    )
    assert status_response.status_code == 200

  comment_response = await client.post(
    f"/api/v1/tasks/{active_task_id}/comments",
    headers=headers,
    data={
      "content": "请补充评审结论。",
      "content_format": "markdown",
      "is_internal": "true",
    },
    files={"files": ("review.md", b"# review", "text/markdown")},
  )
  assert comment_response.status_code == 201
  assert len(comment_response.json()["attachments"]) == 1

  admin_comments_response = await client.get(
    f"/api/v1/tasks/{active_task_id}/comments",
    headers=headers,
  )
  assert admin_comments_response.status_code == 200
  assert len(admin_comments_response.json()) == 1

  employee_comments_response = await client.get(
    f"/api/v1/tasks/{active_task_id}/comments",
    headers=employee_headers,
  )
  assert employee_comments_response.status_code == 200
  assert employee_comments_response.json() == []

  activity_response = await client.get(
    f"/api/v1/tasks/{active_task_id}/activity",
    headers=headers,
  )
  assert activity_response.status_code == 200
  assert any(item["entry_type"] == "comment" for item in activity_response.json())
  assert any(item["entry_type"] == "log" for item in activity_response.json())

  summary_response = await client.get("/api/v1/tasks/stats/summary", headers=headers)
  assert summary_response.status_code == 200
  assert summary_response.json()["total_tasks"] == 2
  assert summary_response.json()["completed_tasks"] == 1
  assert summary_response.json()["overdue_tasks"] == 1
  assert summary_response.json()["tasks_by_status"]["done"] == 1

  workload_response = await client.get("/api/v1/tasks/stats/workload", headers=headers)
  assert workload_response.status_code == 200
  assert len(workload_response.json()) == 1
  assert workload_response.json()[0]["assignee_id"] == employee_id
  assert workload_response.json()[0]["completed_tasks"] == 1

  assert len(queue_publisher.payloads) == 2


@pytest.mark.asyncio
async def test_phase3_hr_governance_api_flow(api_client) -> None:
  client, _ = api_client
  headers, _ = await bootstrap_and_login(client)

  manager_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "manager@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert manager_response.status_code == 201
  manager_id = manager_response.json()["id"]

  employee_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "employee@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert employee_response.status_code == 201
  employee_id = employee_response.json()["id"]

  delegate_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "delegate@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert delegate_response.status_code == 201
  delegate_id = delegate_response.json()["id"]

  departments_response = await client.get("/api/v1/departments", headers=headers)
  root_department = next(item for item in departments_response.json() if item["code"] == "root")

  department_response = await client.post(
    "/api/v1/departments",
    headers=headers,
    json={
      "name": "运营部",
      "code": "operations",
      "parent_id": root_department["id"],
      "manager_id": manager_id,
      "sort_order": 30,
    },
  )
  assert department_response.status_code == 201
  department_id = department_response.json()["id"]

  manager_profile_response = await client.post(
    "/api/v1/profiles",
    headers=headers,
    json={
      "user_id": manager_id,
      "employee_no": "EMP-MANAGER-001",
      "real_name": "直属主管",
      "department_id": department_id,
      "custom_fields": {},
    },
  )
  assert manager_profile_response.status_code == 201

  employee_profile_response = await client.post(
    "/api/v1/profiles",
    headers=headers,
    json={
      "user_id": employee_id,
      "employee_no": "EMP-OPS-001",
      "real_name": "运营同学",
      "department_id": department_id,
      "custom_fields": {},
    },
  )
  assert employee_profile_response.status_code == 201

  position_response = await client.post(
    "/api/v1/positions",
    headers=headers,
    json={
      "code": "ops-specialist",
      "name": "运营专员",
      "level": "P4",
      "extra_metadata": {"track": "ops"},
      "is_active": True,
    },
  )
  assert position_response.status_code == 201
  position_id = position_response.json()["id"]

  assign_position_response = await client.post(
    f"/api/v1/profiles/{employee_id}/positions",
    headers=headers,
    json={
      "position_id": position_id,
      "department_id": department_id,
      "assignment_type": "primary",
      "is_primary": True,
      "starts_at": "2025-01-01",
    },
  )
  assert assign_position_response.status_code == 201

  reporting_line_response = await client.post(
    f"/api/v1/profiles/{employee_id}/reporting-lines",
    headers=headers,
    json={
      "manager_user_id": manager_id,
      "department_id": department_id,
      "line_type": "solid",
      "is_primary": True,
      "starts_at": "2025-01-01",
    },
  )
  assert reporting_line_response.status_code == 201

  update_profile_response = await client.patch(
    f"/api/v1/profiles/{employee_id}",
    headers=headers,
    json={
      "custom_fields": {
        "salary": 28000,
        "performance": "A",
        "hobby": "摄影",
      }
    },
  )
  assert update_profile_response.status_code == 200

  manager_headers = await login(
    client,
    email="manager@example.com",
    password="StrongPassword123!",
  )
  manager_view_response = await client.get(f"/api/v1/profiles/{employee_id}", headers=manager_headers)
  assert manager_view_response.status_code == 200
  manager_payload = manager_view_response.json()
  assert manager_payload["custom_fields"]["performance"] == "A"
  assert "salary" not in manager_payload["custom_fields"]

  delegation_response = await client.post(
    "/api/v1/delegations",
    headers=manager_headers,
    json={
      "delegator_user_id": manager_id,
      "delegate_user_id": delegate_id,
      "scope_type": "data_access",
      "starts_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
      "ends_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
    },
  )
  assert delegation_response.status_code == 201
  delegation_id = delegation_response.json()["id"]

  delegate_headers = await login(
    client,
    email="delegate@example.com",
    password="StrongPassword123!",
  )
  delegate_view_response = await client.get(f"/api/v1/profiles/{employee_id}", headers=delegate_headers)
  assert delegate_view_response.status_code == 200
  delegate_payload = delegate_view_response.json()
  assert delegate_payload["custom_fields"]["performance"] == "A"
  assert "salary" not in delegate_payload["custom_fields"]

  event_response = await client.post(
    f"/api/v1/profiles/{employee_id}/events",
    headers=headers,
    json={
      "event_type": "promotion",
      "effective_date": "2025-02-01",
      "title": "晋升为运营负责人",
      "payload": {
        "position_id": position_id,
        "department_id": department_id,
        "manager_user_id": manager_id,
        "job_title": "运营负责人",
        "assignment_type": "primary",
        "is_primary": True,
      },
    },
  )
  assert event_response.status_code == 201
  assert event_response.json()["event_type"] == "promotion"

  field_definitions_response = await client.get("/api/v1/profile-field-definitions", headers=headers)
  assert field_definitions_response.status_code == 200
  definitions_payload = field_definitions_response.json()
  assert any(item["field_key"] == "salary" for item in definitions_payload)
  salary_definition = next(item for item in definitions_payload if item["field_key"] == "salary")

  permissions_response = await client.get(
    f"/api/v1/profile-field-definitions/{salary_definition['id']}/permissions",
    headers=headers,
  )
  assert permissions_response.status_code == 200
  assert len(permissions_response.json()) >= 1

  delegation_update_response = await client.patch(
    f"/api/v1/delegations/{delegation_id}",
    headers=manager_headers,
    json={"status": "revoked"},
  )
  assert delegation_update_response.status_code == 200
  assert delegation_update_response.json()["status"] == "revoked"


@pytest.mark.asyncio
async def test_phase4_workflow_messaging_api_flow(api_client) -> None:
  client, queue_publisher = api_client
  headers, _ = await bootstrap_and_login(client)

  manager_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "manager@example.com",
      "password": "StrongPassword123!",
      "role": "hr",
      "status": "active",
    },
  )
  assert manager_response.status_code == 201
  manager_id = manager_response.json()["id"]

  employee_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "employee@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert employee_response.status_code == 201
  employee_id = employee_response.json()["id"]

  watcher_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "watcher@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert watcher_response.status_code == 201
  watcher_id = watcher_response.json()["id"]

  delegate_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "delegate@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert delegate_response.status_code == 201
  delegate_id = delegate_response.json()["id"]

  departments_response = await client.get("/api/v1/departments", headers=headers)
  root_department = next(item for item in departments_response.json() if item["code"] == "root")

  department_response = await client.post(
    "/api/v1/departments",
    headers=headers,
    json={
      "name": "流程推进部",
      "code": "phase4-workflow",
      "parent_id": root_department["id"],
      "manager_id": manager_id,
      "sort_order": 40,
    },
  )
  assert department_response.status_code == 201
  department_id = department_response.json()["id"]

  for user_id, employee_no, real_name in (
    (manager_id, "EMP-MGR-004", "流程经理"),
    (employee_id, "EMP-EMP-004", "流程员工"),
  ):
    profile_response = await client.post(
      "/api/v1/profiles",
      headers=headers,
      json={
        "user_id": user_id,
        "employee_no": employee_no,
        "real_name": real_name,
        "department_id": department_id,
        "custom_fields": {},
      },
    )
    assert profile_response.status_code == 201

  manager_headers = await login(
    client,
    email="manager@example.com",
    password="StrongPassword123!",
  )
  employee_headers = await login(
    client,
    email="employee@example.com",
    password="StrongPassword123!",
  )
  delegate_headers = await login(
    client,
    email="delegate@example.com",
    password="StrongPassword123!",
  )
  watcher_headers = await login(
    client,
    email="watcher@example.com",
    password="StrongPassword123!",
  )

  delegation_response = await client.post(
    "/api/v1/delegations",
    headers=manager_headers,
    json={
      "delegator_user_id": manager_id,
      "delegate_user_id": delegate_id,
      "scope_type": "approval",
      "scope_department_id": department_id,
      "starts_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
      "ends_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
    },
  )
  assert delegation_response.status_code == 201

  template_response = await client.post(
    "/api/v1/task-templates",
    headers=headers,
    json={
      "code": "api-phase4-template",
      "name": "API 模板",
      "category": "ops",
      "steps": [
        {
          "step_key": "draft",
          "title": "员工提交",
          "default_assignee_rule": {"type": "initiator"},
        },
        {
          "step_key": "review",
          "title": "经理复核",
          "default_assignee_rule": {"type": "department_manager"},
          "depends_on_step_keys": ["draft"],
        },
      ],
    },
  )
  assert template_response.status_code == 201
  template_id = template_response.json()["id"]

  instantiate_response = await client.post(
    f"/api/v1/task-templates/{template_id}/instantiate",
    headers=employee_headers,
    json={
      "watcher_user_ids": [watcher_id],
      "payload": {"department_id": department_id},
    },
  )
  assert instantiate_response.status_code == 200
  instantiated_tasks = instantiate_response.json()["tasks"]
  assert len(instantiated_tasks) == 2
  first_task_id = instantiated_tasks[0]["id"]

  watcher_add_response = await client.post(
    f"/api/v1/tasks/{first_task_id}/watchers",
    headers=headers,
    json={"user_ids": [manager_id]},
  )
  assert watcher_add_response.status_code == 200
  assert len(watcher_add_response.json()) == 2

  board_response = await client.get("/api/v1/tasks/views/board", headers=headers)
  assert board_response.status_code == 200
  assert any(column["tasks"] for column in board_response.json())

  gantt_response = await client.get("/api/v1/tasks/views/gantt", headers=headers)
  assert gantt_response.status_code == 200
  assert len(gantt_response.json()) == 2

  schedule_response = await client.post(
    "/api/v1/task-templates/schedules",
    headers=headers,
    json={
      "template_id": template_id,
      "cron_expr": "*/5 * * * *",
      "timezone": "UTC",
      "payload": {"department_id": department_id},
      "is_active": True,
    },
  )
  assert schedule_response.status_code == 201

  schedules_response = await client.get("/api/v1/task-templates/schedules/list", headers=headers)
  assert schedules_response.status_code == 200
  assert len(schedules_response.json()) == 1

  workflow_definition_response = await client.post(
    "/api/v1/workflows/definitions",
    headers=headers,
    json={
      "code": "api-workflow",
      "name": "API 审批",
      "scope_type": "ops",
      "status": "active",
      "steps": [
        {
          "step_key": "draft",
          "name": "发起申请",
          "step_type": "task",
          "assignee_rule": {"type": "initiator"},
        },
        {
          "step_key": "approve",
          "name": "经理审批",
          "step_type": "approval",
          "assignee_rule": {"type": "department_manager"},
        },
      ],
    },
  )
  assert workflow_definition_response.status_code == 201
  workflow_definition_id = workflow_definition_response.json()["id"]

  workflow_instance_response = await client.post(
    "/api/v1/workflows/instances/start",
    headers=employee_headers,
    json={
      "definition_id": workflow_definition_id,
      "source_type": "ops_request",
      "payload": {"department_id": department_id},
    },
  )
  assert workflow_instance_response.status_code == 201
  draft_step_run = next(
    item
    for item in workflow_instance_response.json()["step_runs"]
    if item["step"]["step_key"] == "draft" and item["status"] == "pending"
  )

  approve_draft_response = await client.post(
    f"/api/v1/workflows/step-runs/{draft_step_run['id']}/actions",
    headers=employee_headers,
    json={"action": "approve"},
  )
  assert approve_draft_response.status_code == 200

  delegate_pending_response = await client.get(
    "/api/v1/workflows/step-runs/pending",
    headers=delegate_headers,
  )
  assert delegate_pending_response.status_code == 200
  delegate_step_run = next(
    item for item in delegate_pending_response.json() if item["step"]["step_key"] == "approve"
  )
  assert delegate_step_run["delegated_from_user_id"] == manager_id

  approve_response = await client.post(
    f"/api/v1/workflows/step-runs/{delegate_step_run['id']}/actions",
    headers=delegate_headers,
    json={"action": "approve"},
  )
  assert approve_response.status_code == 200
  assert approve_response.json()["status"] == "approved"

  delegate_messages_response = await client.get("/api/v1/messages", headers=delegate_headers)
  assert delegate_messages_response.status_code == 200
  delegate_messages = delegate_messages_response.json()
  workflow_message = next(
    item for item in delegate_messages if item["message_type"] == "workflow_action_required"
  )

  receipt_response = await client.post(
    f"/api/v1/messages/{workflow_message['id']}/receipts",
    headers=delegate_headers,
    json={"receipt_type": "read"},
  )
  assert receipt_response.status_code == 201
  assert receipt_response.json()["receipt_type"] == "read"

  watcher_messages_response = await client.get("/api/v1/messages", headers=watcher_headers)
  assert watcher_messages_response.status_code == 200
  assert len([item for item in watcher_messages_response.json() if item["message_type"] == "task_cc_added"]) == 2

  assert any(payload["message_type"] == "workflow_action_required" for payload in queue_publisher.payloads)


@pytest.mark.asyncio
async def test_phase5_knowledge_ai_push_api_flow(api_client) -> None:
  client, queue_publisher = api_client
  headers, _ = await bootstrap_and_login(client)

  employee_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "employee@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert employee_response.status_code == 201
  employee_headers = await login(
    client,
    email="employee@example.com",
    password="StrongPassword123!",
  )

  create_document_response = await client.post(
    "/api/v1/documents",
    headers=headers,
    json={
      "title": "员工入职 SOP",
      "slug": "employee-onboarding-sop",
      "category": "sop",
      "content_md": "入职流程需要先提交材料，再开通账号。",
      "status": "draft",
    },
  )
  assert create_document_response.status_code == 201
  document_id = create_document_response.json()["id"]
  assert queue_publisher.jobs[0][0] == REBUILD_DOCUMENT_EMBEDDINGS_JOB

  upload_attachment_response = await client.post(
    "/api/v1/attachments",
    headers=headers,
    data={
      "target_type": "document",
      "target_id": document_id,
      "visibility": "internal",
      "relation": "reference",
    },
    files={"file": ("onboarding.md", b"# onboarding", "text/markdown")},
  )
  assert upload_attachment_response.status_code == 201

  publish_document_response = await client.post(
    f"/api/v1/documents/{document_id}/publish",
    headers=headers,
  )
  assert publish_document_response.status_code == 200
  assert publish_document_response.json()["status"] == "published"
  assert len(queue_publisher.jobs) == 2

  read_document_response = await client.get(
    f"/api/v1/documents/{document_id}",
    headers=headers,
  )
  assert read_document_response.status_code == 200
  assert len(read_document_response.json()["attachments"]) == 1

  list_documents_response = await client.get("/api/v1/documents", headers=employee_headers)
  assert list_documents_response.status_code == 200
  assert len(list_documents_response.json()) == 1
  assert list_documents_response.json()[0]["status"] == "published"

  forbidden_create_response = await client.post(
    "/api/v1/documents",
    headers=employee_headers,
    json={
      "title": "员工手册",
      "category": "policy",
      "content_md": "员工无权创建",
    },
  )
  assert forbidden_create_response.status_code == 403

  search_response = await client.get(
    "/api/v1/documents/search",
    headers=employee_headers,
    params={"query": "入职流程"},
  )
  assert search_response.status_code == 200
  assert search_response.json()["items"][0]["slug"] == "employee-onboarding-sop"

  knowledge_query_response = await client.post(
    "/api/v1/knowledge/query",
    headers=employee_headers,
    json={"query": "入职流程"},
  )
  assert knowledge_query_response.status_code == 200
  assert "先提交材料" in knowledge_query_response.json()["context"]

  slash_command_response = await client.post(
    "/api/v1/ai/router",
    headers=headers,
    json={"text": "/profile"},
  )
  assert slash_command_response.status_code == 200
  assert "档案摘要" in slash_command_response.json()["reply_text"]

  mention_command_response = await client.post(
    "/api/v1/ai/router",
    headers=employee_headers,
    json={"text": "@系统 入职流程是什么？"},
  )
  assert mention_command_response.status_code == 200
  assert "先提交材料" in mention_command_response.json()["reply_text"]
  assert mention_command_response.json()["knowledge_hits"][0]["slug"] == "employee-onboarding-sop"

  create_subscription_response = await client.post(
    "/api/v1/push-subscriptions",
    headers=employee_headers,
    json={
      "endpoint": "https://push.example.com/subscriptions/api-test",
      "p256dh_key": "p256dh",
      "auth_key": "auth",
      "user_agent": "Mozilla/5.0",
    },
  )
  assert create_subscription_response.status_code == 201
  subscription_id = create_subscription_response.json()["id"]

  list_subscriptions_response = await client.get(
    "/api/v1/push-subscriptions",
    headers=employee_headers,
  )
  assert list_subscriptions_response.status_code == 200
  assert len(list_subscriptions_response.json()) == 1

  delete_subscription_response = await client.delete(
    f"/api/v1/push-subscriptions/{subscription_id}",
    headers=employee_headers,
  )
  assert delete_subscription_response.status_code == 200
  assert delete_subscription_response.json()["status"] == "revoked"
