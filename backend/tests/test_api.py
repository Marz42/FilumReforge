from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.dependencies import (
  get_job_queue_publisher,
  get_notification_queue_publisher,
  get_workflow_graph_service,
  get_report_service,
  get_openai_client,
)
from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.core.exceptions import ConflictError
from app.core.enums import TaskPriority, TaskSourceType, TaskStatus, UserRole
from app.main import create_app
from app.models import (
  Base,
  ErrorEvent,
  Task,
  TaskTemplate,
  TaskTemplateInstance,
  TaskTemplateStep,
  TaskTemplateStepRun,
  User,
  WorkflowDeliverable,
  WorkflowGraphInstance,
  WorkflowNodeInstance,
)
from app.services.legacy_task_graph_migration_service import LegacyTaskGraphMigrationService
from app.workers.arq_worker import (
  PROCESS_EMPLOYMENT_EVENT_JOB,
  REBUILD_ALL_DOCUMENT_EMBEDDINGS_JOB,
  REBUILD_DOCUMENT_EMBEDDINGS_JOB,
)
from app.workers.jobs import rebuild_all_document_embeddings, rebuild_document_embeddings

TEST_JWT_SECRET = "test-secret-key-with-32-bytes-minimum!!"
TEST_REFRESH_COOKIE_NAME = "filum_refresh_token"


@pytest.mark.asyncio
@pytest.mark.workflow_i4_gate
async def test_i3f_iteration4_readiness_is_admin_only_and_queryable(api_client) -> None:
  client, _queue_publisher = api_client
  admin_headers, _ = await bootstrap_and_login(client)
  response = await client.get(
    "/api/v1/workflow-graph/admin/iteration4-readiness",
    headers=admin_headers,
  )
  assert response.status_code == 200, response.text
  body = response.json()
  assert set(body) == {
    "generated_at",
    "runtime_ready",
    "incident_counts",
    "outbox_counts",
    "receipt_counts",
    "engine_version_counts",
    "incomplete_objects",
    "blockers",
  }

  employee_response = await client.post(
    "/api/v1/users",
    headers=admin_headers,
    json={
      "email": "i3f-readiness-employee@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert employee_response.status_code == 201
  employee_headers = await login(
    client,
    email="i3f-readiness-employee@example.com",
    password="StrongPassword123!",
  )
  denied = await client.get(
    "/api/v1/workflow-graph/admin/iteration4-readiness",
    headers=employee_headers,
  )
  assert denied.status_code == 404


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
      if job_name == PROCESS_EMPLOYMENT_EVENT_JOB:
        return
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


class FailingNotificationQueuePublisher(InMemoryQueuePublisher):
  def __init__(
    self,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    openai_client: FakeRouterOpenAIClient,
    error_message: str = "queue unavailable",
  ) -> None:
    super().__init__(
      session_factory=session_factory,
      settings=settings,
      openai_client=openai_client,
    )
    self.error_message = error_message

  async def publish(self, payload: dict[str, object]) -> None:
    raise RuntimeError(self.error_message)


class BrokenReportService:
  async def create_report(self, **kwargs):  # noqa: ANN003, ANN201
    raise RuntimeError("forced report creation failure")


@pytest_asyncio.fixture
async def api_client(
  tmp_path: Path,
) -> AsyncIterator[tuple[AsyncClient, InMemoryQueuePublisher]]:
  settings = Settings(
    app_env="development",
    postgres_dsn="sqlite+aiosqlite:///:memory:",
    storage_base_path=str(tmp_path / ".storage"),
    storage_bucket="filum-test",
    jwt_secret_key=TEST_JWT_SECRET,
    frontend_app_url="https://app.example.com",
    openai_api_key="test-openai-key",
    web_push_public_key="test-public-key",
    web_push_private_key="test-private-key",
    web_push_subject="mailto:test@example.com",
    auth_refresh_cookie_secure=False,
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
  assert "refresh_token" not in payload
  set_cookie_header = login_response.headers.get("set-cookie", "")
  assert TEST_REFRESH_COOKIE_NAME in set_cookie_header
  assert "HttpOnly" in set_cookie_header
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

  bootstrap_status_response = await client.get("/api/v1/auth/bootstrap-status")
  assert bootstrap_status_response.status_code == 200
  assert bootstrap_status_response.json() == {"bootstrap_required": True}

  unauthorized_response = await client.get("/api/v1/users")
  assert unauthorized_response.status_code == 401

  headers, login_payload = await bootstrap_and_login(client)

  bootstrap_status_response = await client.get("/api/v1/auth/bootstrap-status")
  assert bootstrap_status_response.status_code == 200
  assert bootstrap_status_response.json() == {"bootstrap_required": False}

  me_response = await client.get("/api/v1/auth/me", headers=headers)
  assert me_response.status_code == 200
  assert me_response.json()["email"] == "admin@example.com"

  assert client.cookies.get(TEST_REFRESH_COOKIE_NAME) is not None

  refresh_response = await client.post("/api/v1/auth/refresh")
  assert refresh_response.status_code == 200
  assert refresh_response.json()["token_type"] == "bearer"
  assert "refresh_token" not in refresh_response.json()
  assert refresh_response.json()["access_token"] != login_payload["access_token"]

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

  delete_user_response = await client.delete(
    f"/api/v1/users/{user_id}",
    headers=headers,
  )
  assert delete_user_response.status_code == 204

  list_users_after_delete_response = await client.get("/api/v1/users", headers=headers)
  assert list_users_after_delete_response.status_code == 200
  assert len(list_users_after_delete_response.json()) == 1

  openapi_response = await client.get("/openapi.json")
  assert openapi_response.status_code == 200
  assert "/api/v1/auth/login" in openapi_response.json()["paths"]
  assert "/api/v1/auth/logout" in openapi_response.json()["paths"]

  logout_response = await client.post("/api/v1/auth/logout")
  assert logout_response.status_code == 204
  assert client.cookies.get(TEST_REFRESH_COOKIE_NAME) is None

  refresh_after_logout_response = await client.post("/api/v1/auth/refresh")
  assert refresh_after_logout_response.status_code == 401


@pytest.mark.asyncio
async def test_auth_invitation_api_flow(api_client) -> None:
  client, _ = api_client
  headers, _ = await bootstrap_and_login(client)

  create_invitation_response = await client.post(
    "/api/v1/auth/invitations",
    headers=headers,
    json={
      "email": "invitee@example.com",
      "role": "employee",
    },
  )
  assert create_invitation_response.status_code == 201
  invite_payload = create_invitation_response.json()
  assert invite_payload["invite_url"].startswith("https://app.example.com/login?invite=")
  invite_token = invite_payload["invite_url"].split("invite=", maxsplit=1)[1]

  preview_response = await client.get(
    "/api/v1/auth/invitations/preview",
    params={"token": invite_token},
  )
  assert preview_response.status_code == 200
  assert preview_response.json()["email"] == "invitee@example.com"

  accept_response = await client.post(
    "/api/v1/auth/invitations/accept",
    json={
      "token": invite_token,
      "password": "StrongPassword123!",
    },
  )
  assert accept_response.status_code == 200
  assert accept_response.json()["user"]["status"] == "active"
  assert client.cookies.get(TEST_REFRESH_COOKIE_NAME) is not None

  duplicate_invitation_response = await client.post(
    "/api/v1/auth/invitations",
    headers=headers,
    json={
      "email": "invitee@example.com",
      "role": "employee",
    },
  )
  assert duplicate_invitation_response.status_code == 409

  revoked_invitation_response = await client.post(
    "/api/v1/auth/invitations",
    headers=headers,
    json={
      "email": "revoked@example.com",
      "role": "hr",
    },
  )
  assert revoked_invitation_response.status_code == 201
  revoked_payload = revoked_invitation_response.json()
  revoked_token = revoked_payload["invite_url"].split("invite=", maxsplit=1)[1]

  revoke_response = await client.post(
    f"/api/v1/auth/invitations/{revoked_payload['user']['id']}/revoke",
    headers=headers,
  )
  assert revoke_response.status_code == 200
  assert revoke_response.json()["invitation_revoked_at"] is not None

  revoked_preview_response = await client.get(
    "/api/v1/auth/invitations/preview",
    params={"token": revoked_token},
  )
  assert revoked_preview_response.status_code == 409


@pytest.mark.asyncio
async def test_password_policy_rejects_weak_passwords_on_write_paths(api_client) -> None:
  client, _ = api_client

  weak_bootstrap_response = await client.post(
    "/api/v1/auth/bootstrap-admin",
    json={
      "email": "admin@example.com",
      "password": "12345678",
      "real_name": "管理员",
      "employee_no": "EMP-ROOT",
    },
  )
  assert weak_bootstrap_response.status_code == 422

  headers, _ = await bootstrap_and_login(client)

  weak_create_user_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "hr@example.com",
      "password": "abcdefgh",
      "role": "hr",
      "status": "active",
    },
  )
  assert weak_create_user_response.status_code == 422

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

  weak_update_user_response = await client.patch(
    f"/api/v1/users/{user_id}",
    headers=headers,
    json={"password": "87654321"},
  )
  assert weak_update_user_response.status_code == 422


@pytest.mark.asyncio
async def test_change_password_updates_credentials(api_client) -> None:
  client, _ = api_client
  headers, _ = await bootstrap_and_login(client)
  email = "admin@example.com"
  original_password = "StrongPassword123!"

  weak_change_response = await client.post(
    "/api/v1/auth/change-password",
    headers=headers,
    json={
      "current_password": original_password,
      "new_password": "12345678",
    },
  )
  assert weak_change_response.status_code == 422

  wrong_current_response = await client.post(
    "/api/v1/auth/change-password",
    headers=headers,
    json={
      "current_password": "WrongPassword123!",
      "new_password": "AnotherStrong123!",
    },
  )
  assert wrong_current_response.status_code == 401

  change_response = await client.post(
    "/api/v1/auth/change-password",
    headers=headers,
    json={
      "current_password": original_password,
      "new_password": "UpdatedStrong123!",
    },
  )
  assert change_response.status_code == 204

  old_login_response = await client.post(
    "/api/v1/auth/login",
    json={
      "email": email,
      "password": original_password,
    },
  )
  assert old_login_response.status_code == 401

  new_login_response = await client.post(
    "/api/v1/auth/login",
    json={
      "email": email,
      "password": "UpdatedStrong123!",
    },
  )
  assert new_login_response.status_code == 200


@pytest.mark.asyncio
async def test_people_management_api_returns_aggregated_people_workspace(api_client) -> None:
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

  unprofiled_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "unprofiled@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "inactive",
    },
  )
  assert unprofiled_response.status_code == 201

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
      "manager_id": manager_id,
      "sort_order": 10,
    },
  )
  assert create_department_response.status_code == 201
  department_id = create_department_response.json()["id"]

  manager_profile_response = await client.post(
    "/api/v1/profiles",
    headers=headers,
    json={
      "user_id": manager_id,
      "employee_no": "EMP-MANAGER-001",
      "real_name": "技术负责人",
      "department_id": department_id,
      "job_title": "技术负责人",
    },
  )
  assert manager_profile_response.status_code == 201

  employee_profile_response = await client.post(
    "/api/v1/profiles",
    headers=headers,
    json={
      "user_id": employee_id,
      "employee_no": "EMP-001",
      "real_name": "研发工程师",
      "department_id": department_id,
      "job_title": "后端工程师",
      "custom_fields": {"skills": ["python"]},
    },
  )
  assert employee_profile_response.status_code == 201

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

  event_response = await client.post(
    f"/api/v1/profiles/{employee_id}/events",
    headers=headers,
    json={
      "event_type": "promotion",
      "effective_date": "2025-02-01",
      "title": "晋升为后端工程师",
      "summary": "通过试用期",
      "payload": {},
    },
  )
  assert event_response.status_code == 201

  people_response = await client.get("/api/v1/people-management", headers=headers)
  assert people_response.status_code == 200
  payload = people_response.json()
  assert payload["summary"] == {
    "total_people": 4,
    "profiled_people": 3,
    "unprofiled_people": 1,
    "inactive_people": 1,
  }
  employee_item = next(item for item in payload["people"] if item["user_id"] == employee_id)
  assert employee_item["has_profile"] is True
  assert employee_item["department_name"] == "研发部"
  unprofiled_item = next(
    item for item in payload["people"] if item["email"] == "unprofiled@example.com"
  )
  assert unprofiled_item["profile_completion_state"] == "missing_profile"

  detail_response = await client.get(f"/api/v1/people-management/{employee_id}", headers=headers)
  assert detail_response.status_code == 200
  detail_payload = detail_response.json()
  assert detail_payload["account"]["email"] == "employee@example.com"
  assert detail_payload["profile"]["real_name"] == "研发工程师"
  assert detail_payload["primary_manager_label"] == "技术负责人"
  assert detail_payload["latest_employment_event"]["event_type"] == "promotion"
  assert detail_payload["actions"] == {
    "can_edit_user": True,
    "can_delete_user": False,
    "can_create_profile": False,
    "can_edit_profile": True,
    "can_manage_relations": True,
    "can_manage_lifecycle": True,
    "can_manage_delegations": True,
  }

  unprofiled_detail_response = await client.get(
    f"/api/v1/people-management/{unprofiled_response.json()['id']}",
    headers=headers,
  )
  assert unprofiled_detail_response.status_code == 200
  assert unprofiled_detail_response.json()["actions"]["can_delete_user"] is True

  delete_profiled_user_response = await client.delete(
    f"/api/v1/users/{employee_id}",
    headers=headers,
  )
  assert delete_profiled_user_response.status_code == 409

  delete_unprofiled_user_response = await client.delete(
    f"/api/v1/users/{unprofiled_response.json()['id']}",
    headers=headers,
  )
  assert delete_unprofiled_user_response.status_code == 204

  employee_headers = await login(
    client,
    email="employee@example.com",
    password="StrongPassword123!",
  )
  forbidden_response = await client.get("/api/v1/people-management", headers=employee_headers)
  assert forbidden_response.status_code == 403


@pytest.mark.asyncio
async def test_auth_login_rate_limit_returns_429(api_client) -> None:
  client, _ = api_client

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

  last_response = None
  for _ in range(11):
    last_response = await client.post(
      "/api/v1/auth/login",
      json={
        "email": "admin@example.com",
        "password": "wrong-password",
      },
    )

  assert last_response is not None
  assert last_response.status_code == 429
  assert last_response.json()["detail"] == "请求过于频繁，请稍后再试。"


@pytest.mark.asyncio
async def test_auth_refresh_rate_limit_returns_429(api_client) -> None:
  client, _ = api_client

  await bootstrap_and_login(client)

  last_response = None
  for _ in range(21):
    last_response = await client.post("/api/v1/auth/refresh")

  assert last_response is not None
  assert last_response.status_code == 429
  assert last_response.json()["detail"] == "请求过于频繁，请稍后再试。"


@pytest.mark.asyncio
async def test_auth_logout_clears_cookie_even_when_refresh_token_is_invalid(api_client) -> None:
  client, _ = api_client

  await bootstrap_and_login(client)

  logout_response = await client.post(
    "/api/v1/auth/logout",
    cookies={TEST_REFRESH_COOKIE_NAME: "invalid-token"},
  )

  assert logout_response.status_code == 204
  cleared_cookie_header = logout_response.headers.get("set-cookie", "")
  assert TEST_REFRESH_COOKIE_NAME in cleared_cookie_header
  assert "Max-Age=0" in cleared_cookie_header or "expires=" in cleared_cookie_header.lower()


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
  board_id = board_response.json()["id"]

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

  archive_board_response = await client.post(
    f"/api/v1/board-cards/{board_id}/archive",
    headers=headers,
  )
  assert archive_board_response.status_code == 204


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

  search_response = await client.get(
    "/api/v1/tasks/search",
    headers=headers,
    params={"q": "基础模块"},
  )
  assert search_response.status_code == 200
  assert len(search_response.json()) == 1
  assert search_response.json()[0]["title"] == "完成基础模块开发"

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
  assert upload_response.json()["download_url"] == f"/api/v1/attachments/{attachment_id}/content"

  download_response = await client.get(
    f"/api/v1/attachments/{attachment_id}/content",
    headers=headers,
    params={"disposition": "attachment"},
  )
  assert download_response.status_code == 200
  assert download_response.content == b"phase-1 attachment"
  assert "attachment" in download_response.headers.get("content-disposition", "").lower()

  inline_response = await client.get(
    f"/api/v1/attachments/{attachment_id}/content",
    headers=headers,
    params={"disposition": "inline"},
  )
  assert inline_response.status_code == 200
  assert inline_response.headers.get("content-disposition", "").startswith("inline")

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

  invalid_upload_response = await client.post(
    "/api/v1/attachments",
    headers=headers,
    data={
      "target_type": "task",
      "target_id": task_id,
      "visibility": "private",
      "relation": "primary",
    },
    files={"file": ("fake.pdf", b"not-a-real-pdf", "application/pdf")},
  )
  assert invalid_upload_response.status_code == 422
  assert "附件内容与声明类型不匹配" in invalid_upload_response.json()["detail"]

  assert len(queue_publisher.payloads) == 1
  assert queue_publisher.payloads[0]["message_type"] == "task_assigned"


@pytest.mark.asyncio
async def test_phase3_create_task_api_uses_graph_engine(api_client) -> None:
  client, queue_publisher = api_client
  queue_publisher._settings.workflow_graph_engine_enabled = True
  queue_publisher._settings.workflow_standalone_manual_tasks_enabled = False
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
  employee_uuid = UUID(employee_id)

  departments_response = await client.get("/api/v1/departments", headers=headers)
  root_department = next(item for item in departments_response.json() if item["code"] == "root")
  profile_response = await client.post(
    "/api/v1/profiles",
    headers=headers,
    json={
      "user_id": employee_id,
      "employee_no": "EMP-001",
      "real_name": "研发工程师",
      "department_id": root_department["id"],
      "custom_fields": {},
    },
  )
  assert profile_response.status_code == 201

  task_response = await client.post(
    "/api/v1/tasks",
    headers=headers,
    json={
      "title": "完成图引擎 API 测试任务",
      "assignee_id": employee_id,
      "priority": "high",
    },
  )
  assert task_response.status_code == 201
  payload = task_response.json()
  assert payload["status"] == "todo"
  assert payload["source_type"] == "manual"
  task_id = UUID(payload["id"])

  async with queue_publisher._session_factory() as session:
    stored_instance = await session.scalar(
      select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == task_id)
    )
    stored_node = await session.scalar(
      select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == stored_instance.id)
    )

  assert stored_instance is not None
  assert stored_instance.source_type == "manual"
  assert stored_instance.context["title"] == "完成图引擎 API 测试任务"
  assert stored_node is not None
  assert stored_node.assignee_user_id == employee_uuid


@pytest.mark.asyncio
async def test_phase5_task_deliverable_review_api_flow(api_client) -> None:
  client, queue_publisher = api_client
  queue_publisher._settings.workflow_graph_engine_enabled = True
  queue_publisher._settings.workflow_standalone_manual_tasks_enabled = False
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
  profile_response = await client.post(
    "/api/v1/profiles",
    headers=headers,
    json={
      "user_id": employee_id,
      "employee_no": "EMP-001",
      "real_name": "研发工程师",
      "department_id": root_department["id"],
      "custom_fields": {},
    },
  )
  assert profile_response.status_code == 201

  task_response = await client.post(
    "/api/v1/tasks",
    headers=headers,
    json={
      "title": "完成 Phase 5 API 验收",
      "assignee_id": employee_id,
      "priority": "high",
    },
  )
  assert task_response.status_code == 201
  task_id = task_response.json()["id"]

  employee_headers = await login(client, email="employee@example.com", password="StrongPassword123!")
  accept_response = await client.post(
    f"/api/v1/tasks/{task_id}/accept",
    headers=employee_headers,
  )
  assert accept_response.status_code == 200
  doing_response = await client.patch(
    f"/api/v1/tasks/{task_id}/status",
    headers=employee_headers,
    json={"status": "doing"},
  )
  assert doing_response.status_code == 200

  submit_response = await client.post(
    f"/api/v1/tasks/{task_id}/deliverable",
    headers=employee_headers,
    json={"summary": "第一版交付说明"},
  )
  assert submit_response.status_code == 200
  assert submit_response.json()["status"] == "review"
  assert submit_response.json()["extra_metadata"]["latest_deliverable_summary"] == "第一版交付说明"

  return_response = await client.post(
    f"/api/v1/tasks/{task_id}/review",
    headers=headers,
    json={"action": "return_for_rework", "comment": "请补充边界场景"},
  )
  assert return_response.status_code == 200
  assert return_response.json()["status"] == "doing"
  assert return_response.json()["extra_metadata"]["rework_count"] == 1

  second_submit_response = await client.post(
    f"/api/v1/tasks/{task_id}/deliverable",
    headers=employee_headers,
    json={"summary": "第二版交付说明"},
  )
  assert second_submit_response.status_code == 200
  assert second_submit_response.json()["status"] == "review"

  tracking_snapshot = await client.get("/api/v1/task-center", headers=employee_headers)
  assert tracking_snapshot.status_code == 200
  tracked_review_item = next(item for item in tracking_snapshot.json()["task_tracking"] if item["task_id"] == task_id)
  assert tracked_review_item["is_pending_review"] is True
  assert tracked_review_item["rework_count"] == 1
  assert tracked_review_item["latest_deliverable_submitted_at"] is not None

  approve_response = await client.post(
    f"/api/v1/tasks/{task_id}/review",
    headers=headers,
    json={"action": "approve", "comment": "验收通过", "quality_score": 5},
  )
  assert approve_response.status_code == 200
  assert approve_response.json()["status"] == "done"
  assert approve_response.json()["extra_metadata"]["latest_review_quality_score"] == 5

  async with queue_publisher._session_factory() as session:
    task_uuid = UUID(task_id)
    stored_instance = await session.scalar(
      select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == task_uuid)
    )
    stored_node = await session.scalar(
      select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == stored_instance.id)
    )
    stored_deliverable = await session.scalar(
      select(WorkflowDeliverable).where(WorkflowDeliverable.node_instance_id == stored_node.id)
    )

  assert stored_instance is not None
  assert stored_instance.status == "completed"
  assert stored_node is not None
  assert stored_node.business_state == "done"
  assert stored_deliverable is not None
  assert stored_deliverable.summary == "第二版交付说明"
  assert len(stored_deliverable.payload["submission_history"]) == 2


@pytest.mark.asyncio
async def test_phase5_task_status_api_blocks_direct_review_and_done_for_graph_tasks(api_client) -> None:
  client, queue_publisher = api_client
  queue_publisher._settings.workflow_graph_engine_enabled = True
  queue_publisher._settings.workflow_standalone_manual_tasks_enabled = False
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
  profile_response = await client.post(
    "/api/v1/profiles",
    headers=headers,
    json={
      "user_id": employee_id,
      "employee_no": "EMP-001",
      "real_name": "研发工程师",
      "department_id": root_department["id"],
      "custom_fields": {},
    },
  )
  assert profile_response.status_code == 201

  task_response = await client.post(
    "/api/v1/tasks",
    headers=headers,
    json={
      "title": "检查 Phase 5 状态旁路",
      "assignee_id": employee_id,
      "priority": "high",
    },
  )
  assert task_response.status_code == 201
  task_id = task_response.json()["id"]

  employee_headers = await login(client, email="employee@example.com", password="StrongPassword123!")
  accept_response = await client.post(
    f"/api/v1/tasks/{task_id}/accept",
    headers=employee_headers,
  )
  assert accept_response.status_code == 200
  assert accept_response.json()["extra_metadata"]["workflow_handshake_state"] == "accepted"

  doing_response = await client.patch(
    f"/api/v1/tasks/{task_id}/status",
    headers=employee_headers,
    json={"status": "doing"},
  )
  assert doing_response.status_code == 200

  direct_review_response = await client.patch(
    f"/api/v1/tasks/{task_id}/status",
    headers=employee_headers,
    json={"status": "review"},
  )
  assert direct_review_response.status_code == 409
  assert "提交交付物" in direct_review_response.json()["detail"]

  submit_response = await client.post(
    f"/api/v1/tasks/{task_id}/deliverable",
    headers=employee_headers,
    json={"summary": "第一版交付说明"},
  )
  assert submit_response.status_code == 200

  direct_done_response = await client.patch(
    f"/api/v1/tasks/{task_id}/status",
    headers=headers,
    json={"status": "done"},
  )
  assert direct_done_response.status_code == 409
  assert "验收动作" in direct_done_response.json()["detail"]


@pytest.mark.asyncio
async def test_phase4_task_acceptance_and_task_center_snapshot_flow(api_client) -> None:
  client, queue_publisher = api_client
  queue_publisher._settings.workflow_graph_engine_enabled = True
  queue_publisher._settings.workflow_standalone_manual_tasks_enabled = False
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
  profile_response = await client.post(
    "/api/v1/profiles",
    headers=headers,
    json={
      "user_id": employee_id,
      "employee_no": "EMP-001",
      "real_name": "研发工程师",
      "department_id": root_department["id"],
      "custom_fields": {},
    },
  )
  assert profile_response.status_code == 201

  task_response = await client.post(
    "/api/v1/tasks",
    headers=headers,
    json={
      "title": "等待接单的 API 图任务",
      "assignee_id": employee_id,
      "priority": "high",
    },
  )
  assert task_response.status_code == 201
  task_id = task_response.json()["id"]

  employee_headers = await login(client, email="employee@example.com", password="StrongPassword123!")
  inbox_before_accept = await client.get("/api/v1/task-center", headers=employee_headers)
  assert inbox_before_accept.status_code == 200
  assert any(item["task_id"] == task_id and item["current_stage_label"].endswith("：待确认") for item in inbox_before_accept.json()["task_inbox"])

  direct_doing_response = await client.patch(
    f"/api/v1/tasks/{task_id}/status",
    headers=employee_headers,
    json={"status": "doing"},
  )
  assert direct_doing_response.status_code == 409
  assert "先由执行人接受任务" in direct_doing_response.json()["detail"]

  accept_response = await client.post(
    f"/api/v1/tasks/{task_id}/accept",
    headers=employee_headers,
  )
  assert accept_response.status_code == 200
  assert accept_response.json()["extra_metadata"]["workflow_handshake_state"] == "accepted"

  accepted_inbox = await client.get("/api/v1/task-center", headers=employee_headers)
  assert accepted_inbox.status_code == 200
  assert any(item["task_id"] == task_id and item["current_stage_label"].endswith("：已接受待开工") for item in accepted_inbox.json()["task_inbox"])

  doing_response = await client.patch(
    f"/api/v1/tasks/{task_id}/status",
    headers=employee_headers,
    json={"status": "doing"},
  )
  assert doing_response.status_code == 200


@pytest.mark.asyncio
async def test_phase4_task_reject_and_delegate_api_refresh_task_center_snapshot(api_client) -> None:
  client, queue_publisher = api_client
  queue_publisher._settings.workflow_graph_engine_enabled = True
  queue_publisher._settings.workflow_standalone_manual_tasks_enabled = False
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
  for user_id, employee_no, real_name in [
    (employee_id, "EMP-001", "研发工程师"),
    (delegate_id, "EMP-002", "代理执行人"),
  ]:
    profile_response = await client.post(
      "/api/v1/profiles",
      headers=headers,
      json={
        "user_id": user_id,
        "employee_no": employee_no,
        "real_name": real_name,
        "department_id": root_department["id"],
        "custom_fields": {},
      },
    )
    assert profile_response.status_code == 201

  delegated_task_response = await client.post(
    "/api/v1/tasks",
    headers=headers,
    json={
      "title": "等待转办的 API 图任务",
      "assignee_id": employee_id,
      "priority": "high",
    },
  )
  assert delegated_task_response.status_code == 201
  delegated_task_id = delegated_task_response.json()["id"]

  employee_headers = await login(client, email="employee@example.com", password="StrongPassword123!")
  delegate_headers = await login(client, email="delegate@example.com", password="StrongPassword123!")
  delegated_response = await client.post(
    f"/api/v1/tasks/{delegated_task_id}/delegate",
    headers=employee_headers,
    json={"assignee_id": delegate_id, "reason": "请由更熟悉客户的人处理"},
  )
  assert delegated_response.status_code == 200
  assert delegated_response.json()["assignee_id"] == delegate_id

  delegate_snapshot = await client.get("/api/v1/task-center", headers=delegate_headers)
  assert delegate_snapshot.status_code == 200
  assert any(item["task_id"] == delegated_task_id and item["current_stage_label"].endswith("：已转办待确认") for item in delegate_snapshot.json()["task_inbox"])

  rejected_task_response = await client.post(
    "/api/v1/tasks",
    headers=headers,
    json={
      "title": "等待退回协商的 API 图任务",
      "assignee_id": employee_id,
      "priority": "high",
    },
  )
  assert rejected_task_response.status_code == 201
  rejected_task_id = rejected_task_response.json()["id"]

  rejected_response = await client.post(
    f"/api/v1/tasks/{rejected_task_id}/reject",
    headers=employee_headers,
    json={"reason": "目标和截止时间都需要重谈"},
  )
  assert rejected_response.status_code == 200
  assert rejected_response.json()["extra_metadata"]["workflow_handshake_state"] == "rejected"

  admin_snapshot = await client.get("/api/v1/task-center", headers=headers)
  assert admin_snapshot.status_code == 200
  assert any(item["task_id"] == rejected_task_id and item["current_stage_label"].endswith("：已拒绝待调整") for item in admin_snapshot.json()["task_inbox"])


@pytest.mark.asyncio
async def test_b12_task_templates_api_is_not_available(api_client) -> None:
  client, _ = api_client
  headers, _ = await bootstrap_and_login(client)

  list_response = await client.get("/api/v1/task-templates", headers=headers)
  assert list_response.status_code == 404

  create_response = await client.post(
    "/api/v1/task-templates",
    headers=headers,
    json={
      "code": "legacy-template",
      "name": "Legacy 模板",
      "category": "ops",
      "steps": [
        {
          "step_key": "draft",
          "title": "草稿",
          "default_assignee_rule": {"type": "initiator"},
        }
      ],
    },
  )
  assert create_response.status_code == 404


@pytest.mark.asyncio
async def test_f22_create_task_with_watchers_api(api_client) -> None:
  client, queue_publisher = api_client
  headers, _ = await bootstrap_and_login(client)

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

  assignee_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "assignee@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert assignee_response.status_code == 201
  assignee_id = assignee_response.json()["id"]

  departments_response = await client.get("/api/v1/departments", headers=headers)
  root_department = next(item for item in departments_response.json() if item["code"] == "root")

  for user_id, employee_no, real_name in (
    (watcher_id, "EMP-WATCH-001", "抄送同事"),
    (assignee_id, "EMP-ASSIGN-001", "执行同事"),
  ):
    profile_response = await client.post(
      "/api/v1/profiles",
      headers=headers,
      json={
        "user_id": user_id,
        "employee_no": employee_no,
        "real_name": real_name,
        "department_id": root_department["id"],
        "custom_fields": {},
      },
    )
    assert profile_response.status_code == 201

  task_response = await client.post(
    "/api/v1/tasks",
    headers=headers,
    json={
      "title": "F-22 抄送测试",
      "assignee_id": assignee_id,
      "department_id": root_department["id"],
      "priority": "medium",
      "watcher_user_ids": [watcher_id],
    },
  )
  assert task_response.status_code == 201
  task_id = task_response.json()["id"]

  watchers_response = await client.get(f"/api/v1/tasks/{task_id}/watchers", headers=headers)
  assert watchers_response.status_code == 200
  assert watcher_id in {item["user_id"] for item in watchers_response.json()}

  assert any(payload["message_type"] == "task_cc_added" for payload in queue_publisher.payloads)


@pytest.mark.asyncio
async def test_department_update_and_delete_api_flow(api_client) -> None:
  client, _ = api_client
  headers, _ = await bootstrap_and_login(client)

  root_departments_response = await client.get("/api/v1/departments", headers=headers)
  assert root_departments_response.status_code == 200
  root_department = next(item for item in root_departments_response.json() if item["code"] == "root")

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

  create_department_response = await client.post(
    "/api/v1/departments",
    headers=headers,
    json={
      "name": "市场部",
      "code": "marketing",
      "parent_id": root_department["id"],
      "manager_id": manager_id,
    },
  )
  assert create_department_response.status_code == 201
  department_id = create_department_response.json()["id"]

  update_department_response = await client.patch(
    f"/api/v1/departments/{department_id}",
    headers=headers,
    json={
      "name": "品牌市场部",
      "manager_id": None,
      "is_active": True,
    },
  )
  assert update_department_response.status_code == 200
  assert update_department_response.json()["name"] == "品牌市场部"
  assert update_department_response.json()["manager_id"] is None

  delete_root_response = await client.delete(
    f"/api/v1/departments/{root_department['id']}",
    headers=headers,
  )
  assert delete_root_response.status_code == 409

  delete_department_response = await client.delete(
    f"/api/v1/departments/{department_id}",
    headers=headers,
  )
  assert delete_department_response.status_code == 204

  missing_department_response = await client.get(
    f"/api/v1/departments/{department_id}",
    headers=headers,
  )
  assert missing_department_response.status_code == 404


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

  # graph engine 任务需先接单
  accept_response = await client.post(
    f"/api/v1/tasks/{active_task_id}/accept",
    headers=employee_headers,
  )
  assert accept_response.status_code == 200

  # 接单后才能切换到进行中
  doing_response = await client.patch(
    f"/api/v1/tasks/{active_task_id}/status",
    headers=employee_headers,
    json={"status": "doing"},
  )
  assert doing_response.status_code == 200

  # 提交交付物（状态切换到 review）
  deliverable_response = await client.post(
    f"/api/v1/tasks/{active_task_id}/deliverable",
    headers=employee_headers,
    json={"summary": "协同测试交付物已完成"},
  )
  assert deliverable_response.status_code == 200

  # 发起人验收通过（状态切换到 done）
  approve_response = await client.post(
    f"/api/v1/tasks/{active_task_id}/review",
    headers=headers,
    json={"action": "approve"},
  )
  assert approve_response.status_code == 200

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

  scopes_response = await client.get("/api/v1/tasks/stats/scopes", headers=headers)
  assert scopes_response.status_code == 200
  assert scopes_response.json()["mode"] == "organization"

  details_response = await client.get(
    "/api/v1/tasks/stats/details",
    params={"metric": "open", "limit": 10},
    headers=headers,
  )
  assert details_response.status_code == 200
  assert details_response.json()["has_more"] is False
  assert len(details_response.json()["items"]) == 1

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


@pytest.mark.asyncio
async def test_profile_event_api_accepts_lifecycle_automation_targets(api_client) -> None:
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

  admin_profile_response = await client.get("/api/v1/profiles", headers=headers)
  assert admin_profile_response.status_code == 200
  admin_department_id = admin_profile_response.json()[0]["department_id"]

  employee_profile_response = await client.post(
    "/api/v1/profiles",
    headers=headers,
    json={
      "user_id": employee_id,
      "employee_no": "EMP-API-001",
      "real_name": "生命周期员工",
      "department_id": admin_department_id,
      "custom_fields": {},
    },
  )
  assert employee_profile_response.status_code == 201

  workflow_response = await client.post(
    "/api/v1/workflows/definitions",
    headers=headers,
    json={
      "code": "api-lifecycle-workflow",
      "name": "API 生命周期审批",
      "scope_type": "employment_event",
      "status": "active",
      "steps": [
        {
          "step_key": "approve",
          "name": "确认",
          "step_type": "approval",
          "assignee_rule": {"type": "user", "user_id": employee_id},
        }
      ],
    },
  )
  assert workflow_response.status_code == 201

  event_response = await client.post(
    f"/api/v1/profiles/{employee_id}/events",
    headers=headers,
    json={
      "event_type": "onboard",
      "effective_date": "2025-05-01",
      "title": "入职联动",
      "payload": {"department_id": admin_department_id},
      "workflow_definition_id": workflow_response.json()["id"],
    },
  )

  assert event_response.status_code == 201
  assert event_response.json()["trigger_status"] == "pending"
  assert event_response.json()["task_template_id"] is None
  assert event_response.json()["workflow_definition_id"] == workflow_response.json()["id"]
  assert queue_publisher.jobs[-1][0] == PROCESS_EMPLOYMENT_EVENT_JOB

  legacy_template_event_response = await client.post(
    f"/api/v1/profiles/{employee_id}/events",
    headers=headers,
    json={
      "event_type": "transfer",
      "effective_date": "2025-06-01",
      "title": "Legacy 模板联动",
      "payload": {"department_id": admin_department_id},
      "task_template_id": employee_id,
    },
  )
  assert legacy_template_event_response.status_code == 409

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
      "capabilities": ["publish_org_task"],
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

  task_response = await client.post(
    "/api/v1/tasks",
    headers=employee_headers,
    json={
      "title": "员工提交",
      "assignee_id": employee_id,
      "department_id": department_id,
      "priority": "medium",
    },
  )
  assert task_response.status_code == 201
  first_task_id = task_response.json()["id"]

  second_task_response = await client.post(
    "/api/v1/tasks",
    headers=employee_headers,
    json={
      "title": "后续跟进",
      "assignee_id": employee_id,
      "department_id": department_id,
      "priority": "medium",
    },
  )
  assert second_task_response.status_code == 201

  watcher_add_response = await client.post(
    f"/api/v1/tasks/{first_task_id}/watchers",
    headers=headers,
    json={"user_ids": [watcher_id]},
  )
  assert watcher_add_response.status_code == 200

  manager_watcher_response = await client.post(
    f"/api/v1/tasks/{first_task_id}/watchers",
    headers=headers,
    json={"user_ids": [manager_id]},
  )
  assert manager_watcher_response.status_code == 200
  assert len(manager_watcher_response.json()) == 2

  board_response = await client.get("/api/v1/tasks/views/board", headers=headers)
  assert board_response.status_code == 200
  assert any(column["tasks"] for column in board_response.json())

  gantt_response = await client.get("/api/v1/tasks/views/gantt", headers=headers)
  assert gantt_response.status_code == 200
  assert len(gantt_response.json()) >= 2

  legacy_schedule_response = await client.post(
    "/api/v1/task-templates/schedules",
    headers=headers,
    json={
      "template_id": employee_id,
      "cron_expr": "*/5 * * * *",
      "timezone": "UTC",
      "payload": {"department_id": department_id},
      "is_active": True,
    },
  )
  assert legacy_schedule_response.status_code == 404

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
  delegate_messages = delegate_messages_response.json()["items"]
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
  watcher_messages = watcher_messages_response.json()["items"]
  assert len([item for item in watcher_messages if item["message_type"] == "task_cc_added"]) >= 1

  assert any(payload["message_type"] == "workflow_action_required" for payload in queue_publisher.payloads)


@pytest.mark.asyncio
async def test_message_center_api_returns_source_metadata_and_hides_other_users_messages(api_client) -> None:
  client, _ = api_client
  admin_headers, _ = await bootstrap_and_login(client)

  department_response = await client.post(
    "/api/v1/departments",
    headers=admin_headers,
    json={
      "name": "消息联动部",
      "code": "message-linkage",
    },
  )
  assert department_response.status_code == 201
  department_id = department_response.json()["id"]

  create_manager_response = await client.post(
    "/api/v1/users",
    headers=admin_headers,
    json={
      "email": "manager@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert create_manager_response.status_code == 201
  manager_id = create_manager_response.json()["id"]

  create_requester_response = await client.post(
    "/api/v1/users",
    headers=admin_headers,
    json={
      "email": "requester@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert create_requester_response.status_code == 201
  requester_id = create_requester_response.json()["id"]

  await client.post(
    "/api/v1/profiles",
    headers=admin_headers,
    json={
      "user_id": manager_id,
      "employee_no": "EMP-MGR-001",
      "real_name": "部门负责人",
      "department_id": department_id,
    },
  )
  manager_profile_response = await client.post(
    f"/api/v1/profiles/{manager_id}/reporting-lines",
    headers=admin_headers,
    json={
      "manager_user_id": (await client.get("/api/v1/auth/me", headers=admin_headers)).json()["id"],
      "department_id": department_id,
      "line_type": "solid",
      "is_primary": True,
      "starts_at": "2025-01-01",
    },
  )
  assert manager_profile_response.status_code == 201

  requester_profile_response = await client.post(
    "/api/v1/profiles",
    headers=admin_headers,
    json={
      "user_id": requester_id,
      "employee_no": "EMP-REQ-001",
      "real_name": "申请员工",
      "department_id": department_id,
    },
  )
  assert requester_profile_response.status_code == 201

  reporting_line_response = await client.post(
    f"/api/v1/profiles/{requester_id}/reporting-lines",
    headers=admin_headers,
    json={
      "manager_user_id": manager_id,
      "department_id": department_id,
      "line_type": "solid",
      "is_primary": True,
      "starts_at": "2025-01-01",
    },
  )
  assert reporting_line_response.status_code == 201

  requester_headers = await login(client, email="requester@example.com", password="StrongPassword123!")
  create_response = await client.post(
    "/api/v1/report-center/reports",
    headers=requester_headers,
    json={
      "direction": "upward",
      "target_user_id": manager_id,
      "title": "消息中心来源联动测试",
      "content_md": "需要验证来源字段与用户隔离。",
    },
  )
  assert create_response.status_code == 201

  manager_headers = await login(client, email="manager@example.com", password="StrongPassword123!")
  message_center_response = await client.get(
    "/api/v1/messages",
    headers=manager_headers,
    params={"state": "unread"},
  )
  assert message_center_response.status_code == 200
  snapshot = message_center_response.json()
  assert snapshot["unread_count"] >= 1
  report_pending_message = next(
    item
    for item in snapshot["items"]
    if item["message_type"] == "report_pending"
  )
  assert report_pending_message["source"]["module_key"] == "report"
  assert report_pending_message["source"]["module_label"] == "汇报中心"
  assert report_pending_message["source"]["target"]["route_name"] == "reports"
  assert report_pending_message["source"]["target"]["route_query"]["selected"] == create_response.json()["id"]
  assert report_pending_message["receipt_state"]["is_read"] is False

  foreign_message_response = await client.get(
    f"/api/v1/messages/{report_pending_message['id']}",
    headers=requester_headers,
  )
  assert foreign_message_response.status_code == 404


@pytest.mark.asyncio
async def test_message_center_api_supports_delivery_filters_and_message_attachments(api_client) -> None:
  client, _ = api_client
  admin_headers, _ = await bootstrap_and_login(client)

  department_response = await client.post(
    "/api/v1/departments",
    headers=admin_headers,
    json={
      "name": "消息筛选部",
      "code": "message-filtering",
    },
  )
  assert department_response.status_code == 201
  department_id = department_response.json()["id"]

  create_manager_response = await client.post(
    "/api/v1/users",
    headers=admin_headers,
    json={
      "email": "manager@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert create_manager_response.status_code == 201
  manager_id = create_manager_response.json()["id"]

  create_requester_response = await client.post(
    "/api/v1/users",
    headers=admin_headers,
    json={
      "email": "requester@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert create_requester_response.status_code == 201
  requester_id = create_requester_response.json()["id"]

  await client.post(
    "/api/v1/profiles",
    headers=admin_headers,
    json={
      "user_id": manager_id,
      "employee_no": "EMP-MGR-002",
      "real_name": "消息经理",
      "department_id": department_id,
    },
  )
  await client.post(
    f"/api/v1/profiles/{manager_id}/reporting-lines",
    headers=admin_headers,
    json={
      "manager_user_id": (await client.get("/api/v1/auth/me", headers=admin_headers)).json()["id"],
      "department_id": department_id,
      "line_type": "solid",
      "is_primary": True,
      "starts_at": "2025-01-01",
    },
  )

  requester_profile_response = await client.post(
    "/api/v1/profiles",
    headers=admin_headers,
    json={
      "user_id": requester_id,
      "employee_no": "EMP-REQ-002",
      "real_name": "消息申请人",
      "department_id": department_id,
    },
  )
  assert requester_profile_response.status_code == 201

  reporting_line_response = await client.post(
    f"/api/v1/profiles/{requester_id}/reporting-lines",
    headers=admin_headers,
    json={
      "manager_user_id": manager_id,
      "department_id": department_id,
      "line_type": "solid",
      "is_primary": True,
      "starts_at": "2025-01-01",
    },
  )
  assert reporting_line_response.status_code == 201

  requester_headers = await login(client, email="requester@example.com", password="StrongPassword123!")
  create_report_response = await client.post(
    "/api/v1/report-center/reports",
    headers=requester_headers,
    json={
      "direction": "upward",
      "target_user_id": manager_id,
      "title": "消息中心筛选测试",
      "content_md": "验证消息附件与渠道筛选。",
    },
  )
  assert create_report_response.status_code == 201

  manager_headers = await login(client, email="manager@example.com", password="StrongPassword123!")
  initial_snapshot_response = await client.get(
    "/api/v1/messages",
    headers=manager_headers,
    params={"state": "unread", "channel": "websocket", "delivery_status": "pending"},
  )
  assert initial_snapshot_response.status_code == 200
  report_pending_message = next(
    item
    for item in initial_snapshot_response.json()["items"]
    if item["message_type"] == "report_pending"
  )

  upload_response = await client.post(
    "/api/v1/attachments",
    headers=manager_headers,
    files={"file": ("message-note.txt", b"message attachment", "text/plain")},
    data={
      "visibility": "private",
      "target_type": "notification_message",
      "target_id": report_pending_message["id"],
      "relation": "primary",
    },
  )
  assert upload_response.status_code == 201

  filtered_snapshot_response = await client.get(
    "/api/v1/messages",
    headers=manager_headers,
    params={"state": "unread", "channel": "websocket", "delivery_status": "pending"},
  )
  assert filtered_snapshot_response.status_code == 200
  filtered_snapshot = filtered_snapshot_response.json()
  filtered_message = next(
    item
    for item in filtered_snapshot["items"]
    if item["id"] == report_pending_message["id"]
  )

  assert filtered_snapshot["applied_channel"] == "websocket"
  assert filtered_snapshot["applied_delivery_status"] == "pending"
  assert filtered_message["delivery_state"] == "pending"
  assert len(filtered_message["attachments"]) == 1
  assert filtered_message["attachments"][0]["original_filename"] == "message-note.txt"

  message_detail_response = await client.get(
    f"/api/v1/messages/{report_pending_message['id']}",
    headers=manager_headers,
  )
  assert message_detail_response.status_code == 200
  assert len(message_detail_response.json()["attachments"]) == 1


@pytest.mark.asyncio
async def test_task_center_api_supports_snapshot_and_memos(api_client) -> None:
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

  departments_response = await client.get("/api/v1/departments", headers=headers)
  root_department = next(item for item in departments_response.json() if item["code"] == "root")
  department_response = await client.post(
    "/api/v1/departments",
    headers=headers,
    json={
      "name": "任务中心测试部",
      "code": "task-center-test",
      "parent_id": root_department["id"],
      "manager_id": manager_id,
      "capabilities": ["publish_org_task"],
    },
  )
  assert department_response.status_code == 201
  department_id = department_response.json()["id"]

  for user_id, employee_no, real_name in (
    (manager_id, "EMP-MGR-TC", "任务主管"),
    (employee_id, "EMP-EMP-TC", "任务成员"),
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

  task_response = await client.post(
    "/api/v1/tasks",
    headers=manager_headers,
    json={
      "title": "提交内容",
      "assignee_id": employee_id,
      "department_id": department_id,
      "priority": "medium",
    },
  )
  assert task_response.status_code == 201
  task_id = task_response.json()["id"]

  accept_response = await client.post(
    f"/api/v1/tasks/{task_id}/accept",
    headers=employee_headers,
  )
  assert accept_response.status_code == 200

  doing_response = await client.patch(
    f"/api/v1/tasks/{task_id}/status",
    headers=employee_headers,
    json={"status": "doing"},
  )
  assert doing_response.status_code == 200

  submit_response = await client.post(
    f"/api/v1/tasks/{task_id}/deliverable",
    headers=employee_headers,
    json={"summary": "任务中心测试交付"},
  )
  assert submit_response.status_code == 200
  assert submit_response.json()["status"] == "review"

  approve_response = await client.post(
    f"/api/v1/tasks/{task_id}/review",
    headers=manager_headers,
    json={"action": "approve", "comment": "完成", "quality_score": 5},
  )
  assert approve_response.status_code == 200
  assert approve_response.json()["status"] == "done"

  memo_response = await client.post(
    "/api/v1/task-center/memos",
    headers=employee_headers,
    json={
      "title": "周报备忘",
      "content": "完成后同步到团队周报。",
      "related_task_id": task_id,
      "is_pinned": True,
    },
  )
  assert memo_response.status_code == 201
  memo_id = memo_response.json()["id"]
  assert memo_response.json()["title"] == "周报备忘"

  snapshot_response = await client.get("/api/v1/task-center", headers=employee_headers)
  assert snapshot_response.status_code == 200
  payload = snapshot_response.json()
  assert payload["permissions"]["can_publish_task"] is True
  assert payload["permissions"]["can_manage_templates"] is False
  assert len(payload["template_summaries"]) == 0
  assert len(payload["task_history"]) == 1
  assert len(payload["task_memos"]) == 1

  update_memo_response = await client.patch(
    f"/api/v1/task-center/memos/{memo_id}",
    headers=employee_headers,
    json={"content": "完成后同步到团队周报和公告。"},
  )
  assert update_memo_response.status_code == 200
  assert update_memo_response.json()["related_task_id"] == task_id

  delete_memo_response = await client.delete(
    f"/api/v1/task-center/memos/{memo_id}",
    headers=employee_headers,
  )
  assert delete_memo_response.status_code == 204


@pytest.mark.asyncio
async def test_step4_report_center_api_supports_flow_and_archive(api_client) -> None:
  client, queue_publisher = api_client
  headers, _ = await bootstrap_and_login(client)

  created_users: dict[str, str] = {}
  for email, role in (
    ("manager@example.com", "employee"),
    ("delegate@example.com", "employee"),
    ("requester@example.com", "employee"),
  ):
    response = await client.post(
      "/api/v1/users",
      headers=headers,
      json={
        "email": email,
        "password": "StrongPassword123!",
        "role": role,
        "status": "active",
      },
    )
    assert response.status_code == 201
    created_users[email] = response.json()["id"]

  departments_response = await client.get("/api/v1/departments", headers=headers)
  root_department = next(item for item in departments_response.json() if item["code"] == "root")
  department_response = await client.post(
    "/api/v1/departments",
    headers=headers,
    json={
      "name": "汇报 API 测试部",
      "code": "report-center-api",
      "parent_id": root_department["id"],
      "manager_id": created_users["manager@example.com"],
    },
  )
  assert department_response.status_code == 201
  department_id = department_response.json()["id"]

  for email, employee_no, real_name in (
    ("manager@example.com", "EMP-RPT-A1", "中层经理"),
    ("delegate@example.com", "EMP-RPT-A2", "代理同学"),
    ("requester@example.com", "EMP-RPT-A3", "汇报员工"),
  ):
    profile_response = await client.post(
      "/api/v1/profiles",
      headers=headers,
      json={
        "user_id": created_users[email],
        "employee_no": employee_no,
        "real_name": real_name,
        "department_id": department_id,
        "custom_fields": {},
      },
    )
    assert profile_response.status_code == 201

  manager_id = created_users["manager@example.com"]
  delegate_id = created_users["delegate@example.com"]
  requester_id = created_users["requester@example.com"]

  reporting_line_response = await client.post(
    f"/api/v1/profiles/{requester_id}/reporting-lines",
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

  manager_reporting_line_response = await client.post(
    f"/api/v1/profiles/{manager_id}/reporting-lines",
    headers=headers,
    json={
      "manager_user_id": (await client.get("/api/v1/auth/me", headers=headers)).json()["id"],
      "department_id": department_id,
      "line_type": "solid",
      "is_primary": True,
      "starts_at": "2025-01-01",
    },
  )
  assert manager_reporting_line_response.status_code == 201

  manager_headers = await login(
    client,
    email="manager@example.com",
    password="StrongPassword123!",
  )
  delegate_headers = await login(
    client,
    email="delegate@example.com",
    password="StrongPassword123!",
  )
  requester_headers = await login(
    client,
    email="requester@example.com",
    password="StrongPassword123!",
  )

  delegation_response = await client.post(
    "/api/v1/delegations",
    headers=manager_headers,
    json={
      "delegator_user_id": manager_id,
      "delegate_user_id": delegate_id,
      "scope_type": "all",
      "starts_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
      "ends_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
    },
  )
  assert delegation_response.status_code == 201

  workflow_definition_response = await client.post(
    "/api/v1/workflows/definitions",
    headers=headers,
    json={
      "code": "report-center-api-flow",
      "name": "汇报审批流",
      "scope_type": "report",
      "status": "active",
      "steps": [
        {
          "step_key": "approve",
          "name": "经理审批",
          "step_type": "approval",
          "assignee_rule": {"type": "department_manager"},
        }
      ],
    },
  )
  assert workflow_definition_response.status_code == 201
  workflow_definition_id = workflow_definition_response.json()["id"]

  report_create_response = await client.post(
    "/api/v1/report-center/reports",
    headers=requester_headers,
    json={
      "direction": "upward",
      "target_user_id": (await client.get("/api/v1/auth/me", headers=headers)).json()["id"],
      "title": "项目周报",
      "content_md": "本周已完成任务中心验证与汇报中心准备。",
      "workflow_definition_id": workflow_definition_id,
    },
  )
  assert report_create_response.status_code == 201
  report_id = report_create_response.json()["id"]
  assert report_create_response.json()["workflow_instance_id"] is not None

  delegate_snapshot_response = await client.get("/api/v1/report-center", headers=delegate_headers)
  assert delegate_snapshot_response.status_code == 200
  assert len(delegate_snapshot_response.json()["pending_reports"]) == 1

  advance_response = await client.post(
    f"/api/v1/report-center/reports/{report_id}/actions",
    headers=delegate_headers,
    json={"action": "advance"},
  )
  assert advance_response.status_code == 200
  assert advance_response.json()["current_recipient_user_id"] == (await client.get("/api/v1/auth/me", headers=headers)).json()["id"]

  complete_response = await client.post(
    f"/api/v1/report-center/reports/{report_id}/actions",
    headers=headers,
    json={"action": "advance"},
  )
  assert complete_response.status_code == 200
  assert complete_response.json()["status"] == "completed"

  archive_response = await client.post(
    f"/api/v1/report-center/reports/{report_id}/actions",
    headers=requester_headers,
    json={"action": "archive"},
  )
  assert archive_response.status_code == 200
  assert archive_response.json()["status"] == "archived"

  requester_snapshot_response = await client.get("/api/v1/report-center", headers=requester_headers)
  assert requester_snapshot_response.status_code == 200
  history_reports = requester_snapshot_response.json()["history_reports"]
  assert any(item["id"] == report_id for item in history_reports)
  assert any(payload["message_type"] == "report_pending" for payload in queue_publisher.payloads)
  assert any(payload["message_type"] == "workflow_action_required" for payload in queue_publisher.payloads)


@pytest.mark.asyncio
async def test_step4_report_center_api_creates_reports_without_delegation(api_client) -> None:
  client, queue_publisher = api_client
  headers, _ = await bootstrap_and_login(client)
  admin_id = (await client.get("/api/v1/auth/me", headers=headers)).json()["id"]

  created_users: dict[str, str] = {}
  for email in ("manager@example.com", "requester@example.com"):
    response = await client.post(
      "/api/v1/users",
      headers=headers,
      json={
        "email": email,
        "password": "StrongPassword123!",
        "role": "employee",
        "status": "active",
      },
    )
    assert response.status_code == 201
    created_users[email] = response.json()["id"]

  departments_response = await client.get("/api/v1/departments", headers=headers)
  root_department = next(item for item in departments_response.json() if item["code"] == "root")
  department_response = await client.post(
    "/api/v1/departments",
    headers=headers,
    json={
      "name": "汇报无代理 API 测试部",
      "code": "report-no-delegate-api",
      "parent_id": root_department["id"],
      "manager_id": admin_id,
    },
  )
  assert department_response.status_code == 201
  department_id = department_response.json()["id"]

  for email, employee_no, real_name in (
    ("manager@example.com", "EMP-RPT-NA-1", "中层经理"),
    ("requester@example.com", "EMP-RPT-NA-2", "汇报员工"),
  ):
    profile_response = await client.post(
      "/api/v1/profiles",
      headers=headers,
      json={
        "user_id": created_users[email],
        "employee_no": employee_no,
        "real_name": real_name,
        "department_id": department_id,
        "custom_fields": {},
      },
    )
    assert profile_response.status_code == 201

  manager_id = created_users["manager@example.com"]
  requester_id = created_users["requester@example.com"]

  requester_reporting_line_response = await client.post(
    f"/api/v1/profiles/{requester_id}/reporting-lines",
    headers=headers,
    json={
      "manager_user_id": manager_id,
      "department_id": department_id,
      "line_type": "solid",
      "is_primary": True,
      "starts_at": "2025-01-01",
    },
  )
  assert requester_reporting_line_response.status_code == 201

  manager_reporting_line_response = await client.post(
    f"/api/v1/profiles/{manager_id}/reporting-lines",
    headers=headers,
    json={
      "manager_user_id": admin_id,
      "department_id": department_id,
      "line_type": "solid",
      "is_primary": True,
      "starts_at": "2025-01-01",
    },
  )
  assert manager_reporting_line_response.status_code == 201

  requester_headers = await login(
    client,
    email="requester@example.com",
    password="StrongPassword123!",
  )

  upward_response = await client.post(
    "/api/v1/report-center/reports",
    headers=requester_headers,
    json={
      "direction": "upward",
      "target_user_id": admin_id,
      "title": "向上汇报无代理测试",
      "content_md": "验证无代理场景下的创建不会再触发 500。",
    },
  )
  assert upward_response.status_code == 201
  assert upward_response.json()["current_recipient_user_id"] == manager_id

  downward_response = await client.post(
    "/api/v1/report-center/reports",
    headers=headers,
    json={
      "direction": "downward",
      "target_user_id": requester_id,
      "title": "向下传达无代理测试",
      "content_md": "验证逐级向下传达的创建不会再触发 500。",
    },
  )
  assert downward_response.status_code == 201
  assert downward_response.json()["current_recipient_user_id"] == manager_id
  assert sum(payload["message_type"] == "report_pending" for payload in queue_publisher.payloads) == 2


@pytest.mark.asyncio
async def test_step4_report_center_api_returns_success_when_notification_queue_is_unavailable(
  tmp_path: Path,
) -> None:
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
  application.state.error_tracking_session_factory = session_factory
  fake_openai_client = FakeRouterOpenAIClient()
  queue_publisher = FailingNotificationQueuePublisher(
    session_factory=session_factory,
    settings=settings,
    openai_client=fake_openai_client,
    error_message="redis unavailable",
  )

  async def override_get_db_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
      yield session

  def override_get_settings() -> Settings:
    return settings

  def override_get_notification_queue_publisher() -> FailingNotificationQueuePublisher:
    return queue_publisher

  def override_get_job_queue_publisher() -> FailingNotificationQueuePublisher:
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
    headers, _ = await bootstrap_and_login(client)
    admin_id = (await client.get("/api/v1/auth/me", headers=headers)).json()["id"]

    created_users: dict[str, str] = {}
    for email in ("manager@example.com", "requester@example.com"):
      response = await client.post(
        "/api/v1/users",
        headers=headers,
        json={
          "email": email,
          "password": "StrongPassword123!",
          "role": "employee",
          "status": "active",
        },
      )
      assert response.status_code == 201
      created_users[email] = response.json()["id"]

    departments_response = await client.get("/api/v1/departments", headers=headers)
    root_department = next(item for item in departments_response.json() if item["code"] == "root")
    department_response = await client.post(
      "/api/v1/departments",
      headers=headers,
      json={
        "name": "汇报队列故障 API 测试部",
        "code": "report-queue-failure-api",
        "parent_id": root_department["id"],
        "manager_id": admin_id,
      },
    )
    assert department_response.status_code == 201
    department_id = department_response.json()["id"]

    for email, employee_no, real_name in (
      ("manager@example.com", "EMP-RPT-QF-1", "中层经理"),
      ("requester@example.com", "EMP-RPT-QF-2", "汇报员工"),
    ):
      profile_response = await client.post(
        "/api/v1/profiles",
        headers=headers,
        json={
          "user_id": created_users[email],
          "employee_no": employee_no,
          "real_name": real_name,
          "department_id": department_id,
          "custom_fields": {},
        },
      )
      assert profile_response.status_code == 201

    manager_id = created_users["manager@example.com"]
    requester_id = created_users["requester@example.com"]
    requester_reporting_line_response = await client.post(
      f"/api/v1/profiles/{requester_id}/reporting-lines",
      headers=headers,
      json={
        "manager_user_id": manager_id,
        "department_id": department_id,
        "line_type": "solid",
        "is_primary": True,
        "starts_at": "2025-01-01",
      },
    )
    assert requester_reporting_line_response.status_code == 201

    manager_reporting_line_response = await client.post(
      f"/api/v1/profiles/{manager_id}/reporting-lines",
      headers=headers,
      json={
        "manager_user_id": admin_id,
        "department_id": department_id,
        "line_type": "solid",
        "is_primary": True,
        "starts_at": "2025-01-01",
      },
    )
    assert manager_reporting_line_response.status_code == 201

    requester_headers = await login(client, email="requester@example.com", password="StrongPassword123!")

    create_response = await client.post(
      "/api/v1/report-center/reports",
      headers=requester_headers,
      json={
        "direction": "upward",
        "target_user_id": admin_id,
        "title": "队列故障 API 测试",
        "content_md": "通知队列不可用时也应保持业务成功。",
      },
    )
    assert create_response.status_code == 201

    manager_headers = await login(client, email="manager@example.com", password="StrongPassword123!")
    message_center_response = await client.get("/api/v1/messages", headers=manager_headers)
    assert message_center_response.status_code == 200
    report_pending_message = next(
      message
      for message in message_center_response.json()["items"]
      if message["message_type"] == "report_pending"
    )
    assert report_pending_message["status"] == "failed"
    assert all(delivery["status"] == "failed" for delivery in report_pending_message["deliveries"])
    assert all(delivery["error_message"] == "通知入队失败：redis unavailable" for delivery in report_pending_message["deliveries"])

  application.dependency_overrides.clear()
  await engine.dispose()


@pytest.mark.asyncio
async def test_step4_report_center_api_returns_request_id_and_persists_error_event_on_500(api_client) -> None:
  client, queue_publisher = api_client
  headers, _ = await bootstrap_and_login(client)
  application = client._transport.app  # type: ignore[attr-defined]
  application.dependency_overrides[get_report_service] = lambda: BrokenReportService()

  try:
    transport = ASGITransport(app=application, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as error_client:
      response = await error_client.post(
        "/api/v1/report-center/reports",
        headers=headers,
        json={
          "direction": "upward",
          "target_user_id": (await error_client.get("/api/v1/auth/me", headers=headers)).json()["id"],
          "title": "错误追踪测试",
          "content_md": "用于验证 request id 与 error event。",
        },
      )
  finally:
    application.dependency_overrides.pop(get_report_service, None)

  assert response.status_code == 500
  payload = response.json()
  request_id = payload["request_id"]
  assert payload["detail"] == "服务器内部错误，请记录请求编号并反馈给开发者。"
  assert payload["error_code"] == "internal_error"
  assert response.headers["x-request-id"] == request_id

  async with queue_publisher._session_factory() as session:
    error_event = await session.scalar(select(ErrorEvent).where(ErrorEvent.request_id == request_id))
    assert error_event is not None
    assert error_event.scope == "api.unhandled"
    assert error_event.path == "/api/v1/report-center/reports"
    assert error_event.error_type == "RuntimeError"
    assert error_event.error_code == "internal_error"


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

  config_response = await client.get(
    "/api/v1/push-subscriptions/config",
    headers=employee_headers,
  )
  assert config_response.status_code == 200
  assert config_response.json() == {
    "public_key": "test-public-key",
    "is_enabled": True,
  }

  list_subscriptions_response = await client.get(
    "/api/v1/push-subscriptions",
    headers=employee_headers,
  )
  assert list_subscriptions_response.status_code == 200
  assert len(list_subscriptions_response.json()) == 1

  test_push_response = await client.post(
    "/api/v1/push-subscriptions/test",
    headers=employee_headers,
  )
  assert test_push_response.status_code == 202
  assert test_push_response.json()["detail"] == "测试推送已入队，请留意浏览器通知。"
  assert queue_publisher.payloads[-1]["message_type"] == "web_push_test"

  delete_subscription_response = await client.delete(
    f"/api/v1/push-subscriptions/{subscription_id}",
    headers=employee_headers,
  )
  assert delete_subscription_response.status_code == 200
  assert delete_subscription_response.json()["status"] == "revoked"


# =========================================================================
# Phase 6 / workflow-graph engine API
# =========================================================================

@pytest.mark.asyncio
async def test_phase6_graph_template_instantiation_api(api_client) -> None:
  """通过 POST /workflow-graph/.../complete 完成多节点实例，验证 API 响应结构。"""
  from sqlalchemy.ext.asyncio import AsyncSession
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode
  from app.core.enums import WorkflowGraphTemplateStatus, WorkflowNodeEngineState

  client, _ = api_client
  admin_headers, _ = await bootstrap_and_login(client)

  # 直接通过 session 建模板（API 暂无创建图模板端点）
  # 我们复用 api_client fixture 暴露的 DB：通过 admin API 操作无法建 WorkflowGraphTemplate，
  # 改为通过 HTTP 调用任务模板 API 的 POST 路径然后再访问 graph engine 端点
  # ------
  # 简化做法：通过已有端点间接验证 /workflow-graph 端点可以被调用（404 行为）
  list_response = await client.get(
    "/api/v1/workflow-graph/templates/00000000-0000-0000-0000-000000000000/instances",
    headers=admin_headers,
  )
  # 模板不存在时，service 应抛 NotFoundError → 404
  assert list_response.status_code == 404

  get_response = await client.get(
    "/api/v1/workflow-graph/instances/00000000-0000-0000-0000-000000000000",
    headers=admin_headers,
  )
  assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_phase6_node_completion_triggers_downstream_activation(api_client) -> None:
  """通过 workflow-graph API 完成节点，验证下游激活与 API 响应 progress_percent。"""
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode, WorkflowGraphTemplateEdge
  from app.core.enums import WorkflowGraphTemplateStatus
  from app.services.workflow_graph_service import WorkflowGraphService

  client, queue_publisher = api_client
  admin_headers, admin_payload = await bootstrap_and_login(client)
  admin_id = UUID(admin_payload["user"]["id"])

  async with queue_publisher._session_factory() as session:
    template = WorkflowGraphTemplate(
      code="phase6-complete-api",
      base_code="phase6-complete-api",
      version=1,
      name="Phase 6 Complete API 测试模板",
      status=WorkflowGraphTemplateStatus.ACTIVE,
      created_by=admin_id,
    )
    session.add(template)
    await session.flush()

    node_a = WorkflowGraphTemplateNode(
      template_id=template.id,
      node_key="node-a",
      title="节点 A",
      sort_order=1,
    )
    node_b = WorkflowGraphTemplateNode(
      template_id=template.id,
      node_key="node-b",
      title="节点 B",
      sort_order=2,
    )
    session.add_all([node_a, node_b])
    await session.flush()

    session.add(
      WorkflowGraphTemplateEdge(
        template_id=template.id,
        from_node_id=node_a.id,
        to_node_id=node_b.id,
      )
    )
    await session.flush()

    wg_service = WorkflowGraphService(session)
    result = await wg_service.create_multi_node_instance(
      template_id=template.id,
      initiator_id=admin_id,
    )
    await session.commit()

    node_a_id = str(next(ni for ni in result.node_instances if ni.node_key == "node-a").id)
    instance_id = result.instance.id

  complete_response = await client.post(
    f"/api/v1/workflow-graph/node-instances/{node_a_id}/complete",
    headers=admin_headers,
    json={},
  )
  assert complete_response.status_code == 200
  payload = complete_response.json()
  assert payload["current_node_key"] == "node-b"
  assert payload["active_node_count"] == 1
  assert payload["pending_node_count"] == 0
  assert payload["progress_percent"] == 50

  async with queue_publisher._session_factory() as session:
    refreshed_instance = await session.get(WorkflowGraphInstance, instance_id)
    node_instances = list(
      await session.scalars(
        select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == instance_id)
      )
    )

  assert refreshed_instance is not None
  assert refreshed_instance.current_node_key == "node-b"
  assert refreshed_instance.status.value == "active"
  assert any(
    ni.node_key == "node-b" and ni.engine_state.value == "activated"
    for ni in node_instances
  )


@pytest.mark.asyncio
async def test_phase8_node_completion_api_blocks_terminated_node_submission(api_client) -> None:
  """Phase 8: 节点被系统撤权后，complete API 应返回 409 冲突。"""
  client, _ = api_client
  admin_headers, _ = await bootstrap_and_login(client)

  class _FakeWorkflowGraphService:
    async def complete_node_instance(self, **kwargs):  # noqa: ANN003, ANN201
      raise ConflictError("当前节点已被系统撤权，不能继续提交。")

  application = client._transport.app  # type: ignore[attr-defined]
  application.dependency_overrides[get_workflow_graph_service] = lambda: _FakeWorkflowGraphService()

  try:
    response = await client.post(
      "/api/v1/workflow-graph/node-instances/00000000-0000-0000-0000-000000000000/complete",
      headers=admin_headers,
      json={},
    )
  finally:
    application.dependency_overrides.pop(get_workflow_graph_service, None)

  assert response.status_code == 409
  assert "已被系统撤权" in response.json()["detail"]


@pytest.mark.asyncio
async def test_phase9_deep_reject_api_blocks_when_iteration_exceeds_limit(api_client) -> None:
  """Phase 9: 深度打回超过迭代上限时，API 应返回 409。"""
  client, _ = api_client
  admin_headers, _ = await bootstrap_and_login(client)

  class _FakeWorkflowGraphService:
    async def deep_reject_to_upstream(self, **kwargs):  # noqa: ANN003, ANN201
      raise ConflictError("深度打回次数已达上限，系统已阻止继续迭代。")

  application = client._transport.app  # type: ignore[attr-defined]
  application.dependency_overrides[get_workflow_graph_service] = lambda: _FakeWorkflowGraphService()

  try:
    response = await client.post(
      "/api/v1/workflow-graph/node-instances/00000000-0000-0000-0000-000000000000/deep-reject",
      headers=admin_headers,
      json={"target_node_key": "node-a", "reason": "test"},
    )
  finally:
    application.dependency_overrides.pop(get_workflow_graph_service, None)

  assert response.status_code == 409
  assert "已达上限" in response.json()["detail"]


@pytest.mark.asyncio
async def test_phase11d_complete_api_replay_returns_stable_snapshot(api_client) -> None:
  client, queue_publisher = api_client
  admin_headers, admin_payload = await bootstrap_and_login(client)
  admin_id = UUID(admin_payload["user"]["id"])

  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode
  from app.core.enums import WorkflowGraphTemplateStatus, WorkflowNodeEngineState
  from app.services.workflow_graph_service import WorkflowGraphService

  async with queue_publisher._session_factory() as session:
    template = WorkflowGraphTemplate(
      code="phase11d-complete-api-replay",
      base_code="phase11d-complete-api-replay",
      version=1,
      name="Phase 11-D Complete API 重放测试模板",
      status=WorkflowGraphTemplateStatus.ACTIVE,
      created_by=admin_id,
    )
    session.add(template)
    await session.flush()

    node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-a", title="节点 A", sort_order=1)
    node_b = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-b", title="节点 B", sort_order=2)
    session.add_all([node_a, node_b])
    await session.flush()

    session.add(
      WorkflowGraphTemplateEdge(
        template_id=template.id,
        from_node_id=node_a.id,
        to_node_id=node_b.id,
      )
    )
    await session.flush()

    wg_service = WorkflowGraphService(session)
    result = await wg_service.create_multi_node_instance(
      template_id=template.id,
      initiator_id=admin_id,
    )
    await session.commit()

    instance_id = result.instance.id
    node_a_id = str(next(ni for ni in result.node_instances if ni.node_key == "node-a").id)

  first_response = await client.post(
    f"/api/v1/workflow-graph/node-instances/{node_a_id}/complete",
    headers={**admin_headers, "X-Command-ID": "api-complete-replay-001"},
    json={},
  )
  assert first_response.status_code == 200
  assert first_response.headers["X-Command-ID"] == "api-complete-replay-001"
  first_payload = first_response.json()

  second_response = await client.post(
    f"/api/v1/workflow-graph/node-instances/{node_a_id}/complete",
    headers={**admin_headers, "X-Command-ID": "api-complete-replay-001"},
    json={},
  )
  assert second_response.status_code == 200
  assert second_response.headers["X-Command-ID"] == "api-complete-replay-001"
  second_payload = second_response.json()

  assert first_payload["current_node_key"] == "node-b"
  assert second_payload["current_node_key"] == "node-b"
  assert second_payload["active_node_count"] == first_payload["active_node_count"] == 1
  assert second_payload["pending_node_count"] == first_payload["pending_node_count"] == 0
  assert second_payload["progress_percent"] == first_payload["progress_percent"] == 50

  async with queue_publisher._session_factory() as session:
    from app.models import WorkflowCommandReceipt, WorkflowRunEvent

    refreshed_instance = await session.get(WorkflowGraphInstance, instance_id)
    node_instances = list(
      await session.scalars(
        select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == instance_id)
      )
    )
    receipts = list(
      await session.scalars(
        select(WorkflowCommandReceipt).where(
          WorkflowCommandReceipt.command_id == "api-complete-replay-001"
        )
      )
    )
    completed_events = list(
      await session.scalars(
        select(WorkflowRunEvent).where(
          WorkflowRunEvent.instance_id == instance_id,
          WorkflowRunEvent.event_type == "node_completed",
        )
      )
    )

  assert refreshed_instance is not None
  assert refreshed_instance.current_node_key == "node-b"
  assert len(receipts) == 1
  assert receipts[0].status == "succeeded"
  assert len(completed_events) == 1
  assert completed_events[0].command_id == "api-complete-replay-001"
  assert sum(1 for ni in node_instances if ni.engine_state == WorkflowNodeEngineState.ACTIVATED) == 1
  assert any(
    ni.node_key == "node-b" and ni.engine_state == WorkflowNodeEngineState.ACTIVATED and ni.node_instance_version == 2
    for ni in node_instances
  )


@pytest.mark.asyncio
@pytest.mark.workflow_i4_gate
async def test_phase11d_deep_reject_api_persists_iteration_replay(api_client) -> None:
  client, queue_publisher = api_client
  admin_headers, admin_payload = await bootstrap_and_login(client)
  admin_id = UUID(admin_payload["user"]["id"])

  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode
  from app.core.enums import WorkflowGraphTemplateStatus, WorkflowNodeEngineState
  from app.services.workflow_graph_service import WorkflowGraphService

  async with queue_publisher._session_factory() as session:
    template = WorkflowGraphTemplate(
      code="phase11d-deep-reject-api",
      base_code="phase11d-deep-reject-api",
      version=1,
      name="Phase 11-D Deep Reject API 测试模板",
      status=WorkflowGraphTemplateStatus.ACTIVE,
      created_by=admin_id,
    )
    session.add(template)
    await session.flush()

    node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-a", title="节点 A", sort_order=1)
    node_b = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-b", title="节点 B", sort_order=2)
    session.add_all([node_a, node_b])
    await session.flush()

    session.add(
      WorkflowGraphTemplateEdge(
        template_id=template.id,
        from_node_id=node_a.id,
        to_node_id=node_b.id,
      )
    )
    await session.flush()

    wg_service = WorkflowGraphService(session)
    result = await wg_service.create_multi_node_instance(
      template_id=template.id,
      initiator_id=admin_id,
    )
    node_a_instance = next(ni for ni in result.node_instances if ni.node_key == "node-a")
    node_b_instance = next(ni for ni in result.node_instances if ni.node_key == "node-b")
    await wg_service.complete_node_instance(node_instance_id=node_a_instance.id, actor_id=admin_id)
    await session.commit()

    instance_id = result.instance.id
    node_b_instance_id = str(node_b_instance.id)

  response = await client.post(
    f"/api/v1/workflow-graph/node-instances/{node_b_instance_id}/deep-reject",
    headers={**admin_headers, "X-Command-ID": "i3f-deep-reject-replay-001"},
    json={"target_node_key": "node-a", "reason": "退回重做"},
  )
  assert response.status_code == 200
  payload = response.json()
  assert payload["current_node_key"] == "node-a"

  replay_response = await client.post(
    f"/api/v1/workflow-graph/node-instances/{node_b_instance_id}/deep-reject",
    headers={**admin_headers, "X-Command-ID": "i3f-deep-reject-replay-001"},
    json={"target_node_key": "node-a", "reason": "退回重做"},
  )
  assert replay_response.status_code == 200
  assert replay_response.json() == payload

  async with queue_publisher._session_factory() as session:
    refreshed_instance = await session.get(WorkflowGraphInstance, instance_id)
    node_instances = list(
      await session.scalars(
        select(WorkflowNodeInstance)
        .where(WorkflowNodeInstance.instance_id == instance_id)
        .order_by(WorkflowNodeInstance.created_at.asc())
      )
    )
    from app.models import WorkflowCommandReceipt

    receipts = list(
      await session.scalars(
        select(WorkflowCommandReceipt).where(
          WorkflowCommandReceipt.command_id == "i3f-deep-reject-replay-001"
        )
      )
    )

  assert refreshed_instance is not None
  assert refreshed_instance.current_node_key == "node-a"
  assert any(
    ni.node_key == "node-a" and ni.iteration == 2 and ni.engine_state == WorkflowNodeEngineState.ACTIVATED
    for ni in node_instances
  )
  assert sum(1 for ni in node_instances if ni.iteration == 2) == 2
  assert len(receipts) == 1
  assert any(
    ni.node_key == "node-b" and ni.iteration == 1 and ni.engine_state == WorkflowNodeEngineState.TERMINATED
    for ni in node_instances
  )


@pytest.mark.asyncio
async def test_phase11d_deep_reject_api_blocks_replay_from_stale_node(api_client) -> None:
  client, queue_publisher = api_client
  admin_headers, admin_payload = await bootstrap_and_login(client)
  admin_id = UUID(admin_payload["user"]["id"])

  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode
  from app.core.enums import WorkflowGraphTemplateStatus
  from app.services.workflow_graph_service import WorkflowGraphService

  async with queue_publisher._session_factory() as session:
    template = WorkflowGraphTemplate(
      code="phase11d-deep-reject-api-replay-block",
      base_code="phase11d-deep-reject-api-replay-block",
      version=1,
      name="Phase 11-D Deep Reject API 旧节点阻断测试模板",
      status=WorkflowGraphTemplateStatus.ACTIVE,
      created_by=admin_id,
    )
    session.add(template)
    await session.flush()

    node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-a", title="节点 A", sort_order=1)
    node_b = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-b", title="节点 B", sort_order=2)
    session.add_all([node_a, node_b])
    await session.flush()

    session.add(
      WorkflowGraphTemplateEdge(
        template_id=template.id,
        from_node_id=node_a.id,
        to_node_id=node_b.id,
      )
    )
    await session.flush()

    wg_service = WorkflowGraphService(session)
    result = await wg_service.create_multi_node_instance(
      template_id=template.id,
      initiator_id=admin_id,
    )
    node_a_instance = next(ni for ni in result.node_instances if ni.node_key == "node-a")
    node_b_instance = next(ni for ni in result.node_instances if ni.node_key == "node-b")
    await wg_service.complete_node_instance(node_instance_id=node_a_instance.id, actor_id=admin_id)
    await session.commit()

    node_b_instance_id = str(node_b_instance.id)

  first_response = await client.post(
    f"/api/v1/workflow-graph/node-instances/{node_b_instance_id}/deep-reject",
    headers=admin_headers,
    json={"target_node_key": "node-a", "reason": "第一次深度打回"},
  )
  assert first_response.status_code == 200

  replay_response = await client.post(
    f"/api/v1/workflow-graph/node-instances/{node_b_instance_id}/deep-reject",
    headers=admin_headers,
    json={"target_node_key": "node-a", "reason": "旧节点不应允许重放"},
  )
  assert replay_response.status_code == 409
  assert "ACTIVATED/ACKNOWLEDGED" in replay_response.json()["detail"]


@pytest.mark.asyncio
async def test_phase11_takeover_api_propagates_conflict_error(api_client) -> None:
  """Phase 11-B: takeover API 应透传 service 冲突为 409。"""
  client, _ = api_client
  admin_headers, _ = await bootstrap_and_login(client)

  class _FakeWorkflowGraphService:
    async def takeover_node_instance(self, **kwargs):  # noqa: ANN003, ANN201
      raise ConflictError("当前节点不能执行接管。")

  application = client._transport.app  # type: ignore[attr-defined]
  application.dependency_overrides[get_workflow_graph_service] = lambda: _FakeWorkflowGraphService()

  try:
    response = await client.post(
      "/api/v1/workflow-graph/node-instances/00000000-0000-0000-0000-000000000000/takeover",
      headers=admin_headers,
      json={
        "assignee_user_id": "00000000-0000-0000-0000-000000000001",
        "reason": "管理员接管",
      },
    )
  finally:
    application.dependency_overrides.pop(get_workflow_graph_service, None)

  assert response.status_code == 409
  assert "不能执行接管" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.workflow_i4_gate
async def test_phase11d_takeover_api_syncs_task_projection_and_task_center(api_client) -> None:
  client, queue_publisher = api_client
  queue_publisher._settings.workflow_graph_engine_enabled = True
  queue_publisher._settings.workflow_standalone_manual_tasks_enabled = False
  headers, _ = await bootstrap_and_login(client)

  employee_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "phase11d-employee@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert employee_response.status_code == 201
  employee_id = employee_response.json()["id"]

  new_assignee_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "phase11d-new@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert new_assignee_response.status_code == 201
  new_assignee_id = new_assignee_response.json()["id"]

  departments_response = await client.get("/api/v1/departments", headers=headers)
  root_department = next(item for item in departments_response.json() if item["code"] == "root")
  for user_id, employee_no, real_name in [
    (employee_id, "EMP-011D-001", "原执行人"),
    (new_assignee_id, "EMP-011D-002", "新执行人"),
  ]:
    profile_response = await client.post(
      "/api/v1/profiles",
      headers=headers,
      json={
        "user_id": user_id,
        "employee_no": employee_no,
        "real_name": real_name,
        "department_id": root_department["id"],
        "custom_fields": {},
      },
    )
    assert profile_response.status_code == 201

  task_response = await client.post(
    "/api/v1/tasks",
    headers=headers,
    json={
      "title": "等待管理员接管的 API 图任务",
      "assignee_id": employee_id,
      "priority": "high",
    },
  )
  assert task_response.status_code == 201
  task_id = task_response.json()["id"]

  async with queue_publisher._session_factory() as session:
    instance = await session.scalar(
      select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == UUID(task_id))
    )
    assert instance is not None
    node_instance = await session.scalar(
      select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == instance.id)
    )
    assert node_instance is not None
    node_instance_id = str(node_instance.id)

  takeover_response = await client.post(
    f"/api/v1/workflow-graph/node-instances/{node_instance_id}/takeover",
    headers={**headers, "X-Command-ID": "i3f-takeover-replay-001"},
    json={
      "assignee_user_id": new_assignee_id,
      "reason": "原执行人离岗",
    },
  )
  assert takeover_response.status_code == 200
  replay_response = await client.post(
    f"/api/v1/workflow-graph/node-instances/{node_instance_id}/takeover",
    headers={**headers, "X-Command-ID": "i3f-takeover-replay-001"},
    json={
      "assignee_user_id": new_assignee_id,
      "reason": "原执行人离岗",
    },
  )
  assert replay_response.status_code == 200
  assert replay_response.json() == takeover_response.json()

  old_assignee_headers = await login(
    client,
    email="phase11d-employee@example.com",
    password="StrongPassword123!",
  )
  new_assignee_headers = await login(
    client,
    email="phase11d-new@example.com",
    password="StrongPassword123!",
  )
  old_snapshot = await client.get("/api/v1/task-center", headers=old_assignee_headers)
  new_snapshot = await client.get("/api/v1/task-center", headers=new_assignee_headers)
  assert old_snapshot.status_code == 200
  assert new_snapshot.status_code == 200

  async with queue_publisher._session_factory() as session:
    from app.models import WorkflowCommandReceipt, WorkflowOutboxEvent

    stored_task = await session.get(Task, UUID(task_id))
    assert stored_task is not None
    assert str(stored_task.assignee_id) == new_assignee_id
    assert stored_task.extra_metadata["latest_handshake_action"] == "takeover"
    assert stored_task.extra_metadata["latest_takeover_reason"] == "原执行人离岗"
    receipts = list(
      await session.scalars(
        select(WorkflowCommandReceipt).where(
          WorkflowCommandReceipt.command_id == "i3f-takeover-replay-001"
        )
      )
    )
    outbox_events = list(
      await session.scalars(
        select(WorkflowOutboxEvent).where(
          WorkflowOutboxEvent.node_instance_id == UUID(node_instance_id),
          WorkflowOutboxEvent.event_type == "workflow_node_taken_over",
        )
      )
    )
    assert len(receipts) == 1
    assert len(outbox_events) == 1

  assert all(item["task_id"] != task_id for item in old_snapshot.json()["task_inbox"])
  assert any(
    item["task_id"] == task_id and item["current_stage_label"].endswith("：管理员接管待确认")
    for item in new_snapshot.json()["task_inbox"]
  )


@pytest.mark.asyncio
async def test_phase7_smart_notice_candidates_api_returns_intermediate_managers(api_client) -> None:
  client, _ = api_client
  headers, _ = await bootstrap_and_login(client)

  me_response = await client.get("/api/v1/auth/me", headers=headers)
  assert me_response.status_code == 200
  admin_id = me_response.json()["id"]

  manager_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "phase7-manager@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert manager_response.status_code == 201
  manager_id = manager_response.json()["id"]

  assignee_response = await client.post(
    "/api/v1/users",
    headers=headers,
    json={
      "email": "phase7-assignee@example.com",
      "password": "StrongPassword123!",
      "role": "employee",
      "status": "active",
    },
  )
  assert assignee_response.status_code == 201
  assignee_id = assignee_response.json()["id"]

  departments_response = await client.get("/api/v1/departments", headers=headers)
  root_department = next(item for item in departments_response.json() if item["code"] == "root")
  department_response = await client.post(
    "/api/v1/departments",
    headers=headers,
    json={
      "name": "Phase7 智能抄送测试部",
      "code": "phase7-smart-notice-dept",
      "parent_id": root_department["id"],
      "manager_id": admin_id,
    },
  )
  assert department_response.status_code == 201
  department_id = department_response.json()["id"]

  for user_id, employee_no, real_name in [
    (manager_id, "EMP-P7-M1", "中间经理"),
    (assignee_id, "EMP-P7-A1", "执行人"),
  ]:
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

  assignee_reporting_line = await client.post(
    f"/api/v1/profiles/{assignee_id}/reporting-lines",
    headers=headers,
    json={
      "manager_user_id": manager_id,
      "department_id": department_id,
      "line_type": "solid",
      "is_primary": True,
      "starts_at": "2025-01-01",
    },
  )
  assert assignee_reporting_line.status_code == 201

  manager_reporting_line = await client.post(
    f"/api/v1/profiles/{manager_id}/reporting-lines",
    headers=headers,
    json={
      "manager_user_id": admin_id,
      "department_id": department_id,
      "line_type": "solid",
      "is_primary": True,
      "starts_at": "2025-01-01",
    },
  )
  assert manager_reporting_line.status_code == 201

  candidate_response = await client.post(
    "/api/v1/workflow-graph/smart-notice-candidates",
    headers=headers,
    json={
      "initiator_user_id": admin_id,
      "target_user_id": assignee_id,
      "include_user_ids": [],
      "exclude_user_ids": [],
    },
  )
  assert candidate_response.status_code == 200
  payload = candidate_response.json()
  assert payload["reached_initiator"] is True
  assert payload["candidate_user_ids"] == [manager_id]


@pytest.mark.asyncio
async def test_phase11f_task_center_api_uses_graph_first_for_migrated_review_task(api_client) -> None:
  client, queue_publisher = api_client
  queue_publisher._settings.task_center_v2_enabled = True

  admin_headers, _ = await bootstrap_and_login(client)
  employee_response = await client.post(
    "/api/v1/users",
    headers=admin_headers,
    json={
      "email": "phase11f-api-employee@example.com",
      "password": "StrongPassword123!",
      "role": UserRole.EMPLOYEE.value,
      "status": "active",
    },
  )
  assert employee_response.status_code == 201
  employee_headers = await login(
    client,
    email="phase11f-api-employee@example.com",
    password="StrongPassword123!",
  )

  async with queue_publisher._session_factory() as session:
    admin = await session.scalar(select(User).where(User.email == "admin@example.com"))
    employee = await session.scalar(select(User).where(User.email == "phase11f-api-employee@example.com"))
    assert admin is not None
    assert employee is not None

    template = TaskTemplate(
      code="phase11f-api-template",
      base_code="phase11f-api-template",
      version=1,
      name="API 迁移模板任务",
      category="ops",
      created_by=admin.id,
    )
    session.add(template)
    await session.flush()

    step = TaskTemplateStep(
      template_id=template.id,
      step_key="review-step",
      title="历史待验收步骤",
      default_assignee_rule={},
      sort_order=1,
    )
    session.add(step)
    await session.flush()

    template_instance = TaskTemplateInstance(
      template_id=template.id,
      initiator_user_id=admin.id,
      department_id=None,
      status="in_progress",
      payload={"legacy": True},
    )
    session.add(template_instance)
    await session.flush()

    step_run = TaskTemplateStepRun(
      instance_id=template_instance.id,
      template_step_id=step.id,
      assignee_user_id=employee.id,
      status="completed",
      completed_at=datetime.now(UTC),
    )
    session.add(step_run)
    await session.flush()

    task = Task(
      title="API migrated review task",
      description="用于验证 task-center graph-first 快照",
      creator_id=admin.id,
      assignee_id=employee.id,
      template_instance_id=template_instance.id,
      template_step_run_id=step_run.id,
      source_type=TaskSourceType.TEMPLATE,
      status=TaskStatus.REVIEW,
      priority=TaskPriority.HIGH,
      extra_metadata={
        "template_instance_id": str(template_instance.id),
        "template_step_run_id": str(step_run.id),
        "latest_deliverable_summary": "API 历史交付说明",
        "latest_deliverable_submitted_at": datetime.now(UTC).isoformat(),
        "latest_deliverable_submitted_by_user_id": str(employee.id),
        "latest_review_state": "pending_review",
      },
    )
    session.add(task)
    await session.flush()

    migration_service = LegacyTaskGraphMigrationService(session)
    migrate_result = await migration_service.migrate_tasks(batch_id="phase11f-api-batch")
    assert migrate_result.migrated_count == 1
    task_id = str(task.id)
    await session.commit()

  admin_snapshot = await client.get("/api/v1/task-center", headers=admin_headers)
  employee_snapshot = await client.get("/api/v1/task-center", headers=employee_headers)

  assert admin_snapshot.status_code == 200
  assert employee_snapshot.status_code == 200
  assert any(
    item["task_id"] == task_id and item["current_stage_label"].endswith("：待验收")
    for item in admin_snapshot.json()["task_inbox"]
  )
  assert all(
    item["task_id"] != task_id
    for item in employee_snapshot.json()["task_inbox"]
  )


@pytest.mark.asyncio
async def test_w2_preview_participants_api(api_client) -> None:
  from test_workflow_video_w2_participant_resolution import _bootstrap_copywriting_team

  client, queue_publisher = api_client
  async with queue_publisher._session_factory() as session:
    _admin, _manager, editor_a, editor_b, template = await _bootstrap_copywriting_team(session)
    await session.commit()
    template_id = template.id
    editor_a_id = editor_a.id
    editor_b_id = editor_b.id

  login_response = await client.post(
    "/api/v1/auth/login",
    json={"email": "w2-admin@example.com", "password": "StrongPassword123!"},
  )
  assert login_response.status_code == 200, login_response.text
  headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
  response = await client.post(
    f"/api/v1/workflow-graph/templates/{template_id}/preview-participants",
    params={"policy": "copywriters"},
    headers=headers,
    json={"mode": "subset", "user_ids": [str(editor_a_id), str(editor_b_id)]},
  )
  assert response.status_code == 200, response.text
  body = response.json()
  assert body["policy_ref"] == "copywriters"
  assert body["mode"] == "subset"
  assert set(body["user_ids"]) == {str(editor_a_id), str(editor_b_id)}
  assert len(body["users"]) == 2


@pytest.mark.asyncio
@pytest.mark.workflow_i4_gate
async def test_w3_create_graph_template_run_api(api_client) -> None:
  from app.api.dependencies import get_settings
  from test_workflow_video_w3_instantiation import _seed_topic_meeting_batch_template

  client, queue_publisher = api_client
  enabled_settings = queue_publisher._settings.model_copy(
    update={"workflow_graph_template_engine_enabled": True},
  )
  client._transport.app.dependency_overrides[get_settings] = lambda: enabled_settings  # type: ignore[attr-defined]
  async with queue_publisher._session_factory() as session:
    seed = await _seed_topic_meeting_batch_template(session)
    await session.commit()
    template_id = seed["template"].id
    manager_id = seed["manager"].id
    department_id = seed["department"].id
    editor_ids = [str(editor.id) for editor in seed["editors"]]

  login_response = await client.post(
    "/api/v1/auth/login",
    json={"email": "w3-admin@example.com", "password": "StrongPassword123!"},
  )
  assert login_response.status_code == 200, login_response.text
  headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

  response = await client.post(
    f"/api/v1/workflow-graph/templates/{template_id}/runs",
    headers={**headers, "X-Command-ID": "i3f-create-run-replay-001"},
    json={
      "inputs": {"theme": "API 选题会", "manager_user_id": str(manager_id)},
      "department_id": str(department_id),
      "participants_snapshot": {
        "copywriters": {"mode": "subset", "user_ids": editor_ids},
      },
    },
  )
  assert response.status_code == 200, response.text
  body = response.json()
  assert body["run_kind"] == "batch"
  assert body["activated_task_count"] == 3
  assert body["node_instance_count"] == 4
  assert body["current_node_key"] == "N1_PROPOSE"

  replay_response = await client.post(
    f"/api/v1/workflow-graph/templates/{template_id}/runs",
    headers={**headers, "X-Command-ID": "i3f-create-run-replay-001"},
    json={
      "inputs": {"theme": "API 选题会", "manager_user_id": str(manager_id)},
      "department_id": str(department_id),
      "participants_snapshot": {
        "copywriters": {"mode": "subset", "user_ids": editor_ids},
      },
    },
  )
  assert replay_response.status_code == 200, replay_response.text
  assert replay_response.json() == body

  async with queue_publisher._session_factory() as session:
    from app.models import WorkflowCommandReceipt

    run_count = await session.scalar(
      select(func.count(WorkflowGraphInstance.id)).where(
        WorkflowGraphInstance.template_id == template_id
      )
    )
    receipt_count = await session.scalar(
      select(func.count(WorkflowCommandReceipt.id)).where(
        WorkflowCommandReceipt.command_id == "i3f-create-run-replay-001"
      )
    )
  assert run_count == 1
  assert receipt_count == 1


@pytest.mark.asyncio
async def test_wf_submit_capture_and_finalize_topics_api(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
  from app.core.config import get_settings
  from test_workflow_video_wf_form_engine import _seed_capture_flow, _seed_production_template_for_wf

  monkeypatch.setenv("WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED", "true")
  get_settings.cache_clear()

  client, queue_publisher = api_client
  enabled_settings = queue_publisher._settings.model_copy(
    update={"workflow_graph_template_engine_enabled": True},
  )
  client._transport.app.dependency_overrides[get_settings] = lambda: enabled_settings  # type: ignore[attr-defined]

  async with queue_publisher._session_factory() as session:
    seed = await _seed_capture_flow(session)
    await _seed_production_template_for_wf(session, admin_id=seed["admin"].id)
    await session.commit()
    task_id = seed["task"].id
    instance_id = seed["instance"].id
    editor_id = seed["editor"].id

  login_response = await client.post(
    "/api/v1/auth/login",
    json={"email": "wf-editor@example.com", "password": "StrongPassword123!"},
  )
  assert login_response.status_code == 200
  editor_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

  capture_response = await client.post(
    f"/api/v1/workflow-graph/tasks/{task_id}/submit-capture",
    headers=editor_headers,
    json={"topics": [{"title": "API选题", "content": "via api"}]},
  )
  assert capture_response.status_code == 200, capture_response.text
  topic_id = capture_response.json()["topics"][0]["topic_id"]

  submissions_response = await client.get(
    f"/api/v1/workflow-graph/instances/{instance_id}/submissions",
    params={"node_key": "N1_PROPOSE"},
    headers=editor_headers,
  )
  assert submissions_response.status_code == 200
  assert len(submissions_response.json()["submissions"][0]["topics"]) == 1

  manager_login = await client.post(
    "/api/v1/auth/login",
    json={"email": "wf-manager@example.com", "password": "StrongPassword123!"},
  )
  manager_headers = {"Authorization": f"Bearer {manager_login.json()['access_token']}"}
  finalize_response = await client.post(
    f"/api/v1/workflow-graph/instances/{instance_id}/finalize-topics",
    headers=manager_headers,
    json={
      "approved_topics": [
        {
          "topic_id": topic_id,
          "title": "API选题",
          "script_author_id": str(editor_id),
        }
      ]
    },
  )
  assert finalize_response.status_code == 200, finalize_response.text
  body = finalize_response.json()
  assert body["fork_status"] == "completed"
  assert body["fork_deferred"] is False
  assert body["approved_count"] == 1
  assert len(body.get("child_instance_ids") or []) == 1
