from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_notification_queue_publisher
from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.main import create_app
from app.models import Base

TEST_JWT_SECRET = "test-secret-key-with-32-bytes-minimum!!"


class InMemoryQueuePublisher:
  def __init__(self) -> None:
    self.payloads: list[dict[str, object]] = []

  async def publish(self, payload: dict[str, object]) -> None:
    self.payloads.append(payload)


@pytest_asyncio.fixture
async def api_client(
  tmp_path: Path,
) -> AsyncIterator[tuple[AsyncClient, InMemoryQueuePublisher]]:
  settings = Settings(
    postgres_dsn="sqlite+aiosqlite:///:memory:",
    storage_base_path=str(tmp_path / ".storage"),
    storage_bucket="filum-test",
    jwt_secret_key=TEST_JWT_SECRET,
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
  queue_publisher = InMemoryQueuePublisher()

  async def override_get_db_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
      yield session

  def override_get_settings() -> Settings:
    return settings

  def override_get_notification_queue_publisher() -> InMemoryQueuePublisher:
    return queue_publisher

  application.dependency_overrides[get_db_session] = override_get_db_session
  application.dependency_overrides[get_settings] = override_get_settings
  application.dependency_overrides[get_notification_queue_publisher] = (
    override_get_notification_queue_publisher
  )

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
