from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.core.config import Settings
from app.core.enums import TaskPriority, TaskSourceType, TaskStatus, UserRole
from app.core.exceptions import AuthorizationError, ConflictError
from app.models import Department, Profile, Task
from app.services.auth_service import AuthService
from app.services.task_service import TaskService
from app.services.user_service import UserService

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


@pytest.mark.asyncio
async def test_s01_period_metrics_permissions_and_details(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth = AuthService(db_session, settings)
  admin = await auth.bootstrap_admin(
    email="s01-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-S01-ADMIN",
  )
  users = UserService(db_session)
  manager = await users.create_user(
    actor=admin,
    email="s01-manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  employee = await users.create_user(
    actor=admin,
    email="s01-employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  outsider = await users.create_user(
    actor=admin,
    email="s01-outsider@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  root = Department(
    name="S01 内容中心",
    code="S01-ROOT",
    manager_id=manager.id,
    sort_order=1,
    is_active=True,
  )
  outside = Department(name="S01 外部部门", code="S01-OUT", sort_order=2, is_active=True)
  db_session.add_all([root, outside])
  await db_session.flush()
  child = Department(
    name="S01 内容一组",
    code="S01-CHILD",
    parent_id=root.id,
    sort_order=1,
    is_active=True,
  )
  db_session.add(child)
  await db_session.flush()
  db_session.add_all(
    [
      Profile(user_id=manager.id, real_name="内容经理", employee_no="EMP-S01-M", department_id=root.id),
      Profile(user_id=employee.id, real_name="内容员工", employee_no="EMP-S01-E", department_id=child.id),
      Profile(user_id=outsider.id, real_name="外部员工", employee_no="EMP-S01-O", department_id=outside.id),
    ]
  )

  def task(
    title: str,
    *,
    status: TaskStatus,
    due_at: datetime | None = None,
    completed_at: datetime | None = None,
    metadata: dict | None = None,
    assignee_id=employee.id,
    department_id=child.id,
  ) -> Task:
    return Task(
      title=title,
      creator_id=manager.id,
      assignee_id=assignee_id,
      department_id=department_id,
      status=status,
      priority=TaskPriority.MEDIUM,
      source_type=TaskSourceType.MANUAL,
      created_at=datetime(2025, 1, 2, 2, tzinfo=UTC),
      due_date=due_at,
      completed_at=completed_at,
      extra_metadata=metadata or {},
    )

  db_session.add_all(
    [
      task(
        "按期完成",
        status=TaskStatus.DONE,
        due_at=datetime(2025, 1, 10, 4, tzinfo=UTC),
        completed_at=datetime(2025, 1, 9, 4, tzinfo=UTC),
      ),
      task(
        "晚完成",
        status=TaskStatus.DONE,
        due_at=datetime(2025, 1, 11, 4, tzinfo=UTC),
        completed_at=datetime(2025, 1, 12, 4, tzinfo=UTC),
      ),
      task("逾期未完成", status=TaskStatus.DOING, due_at=datetime(2025, 1, 5, 4, tzinfo=UTC)),
      task("无截止时间", status=TaskStatus.TODO),
      task("评审中", status=TaskStatus.REVIEW, due_at=datetime(2025, 1, 20, 4, tzinfo=UTC)),
      task(
        "Run 壳任务",
        status=TaskStatus.DONE,
        due_at=datetime(2025, 1, 8, 4, tzinfo=UTC),
        completed_at=datetime(2025, 1, 8, 3, tzinfo=UTC),
        metadata={"workflow_graph_root_task": True},
      ),
      task(
        "管理员归档",
        status=TaskStatus.DONE,
        due_at=datetime(2025, 1, 8, 4, tzinfo=UTC),
        completed_at=datetime(2025, 1, 8, 3, tzinfo=UTC),
        metadata={"admin_archived": True},
      ),
      task(
        "范围外任务",
        status=TaskStatus.TODO,
        assignee_id=outsider.id,
        department_id=outside.id,
      ),
    ]
  )
  await db_session.commit()

  service = TaskService(db_session, settings=settings)
  summary = await service.get_task_stats_summary(
    actor=manager,
    department_id=root.id,
    include_subtree=True,
    start_date=date(2025, 1, 1),
    end_date=date(2025, 1, 31),
  )
  assert summary.created_tasks == 5
  assert summary.period_completed_tasks == 2
  assert summary.due_tasks == 4
  assert summary.matured_due_tasks == 4
  assert summary.on_time_completed_tasks == 1
  assert summary.period_overdue_tasks == 3
  assert summary.on_time_completion_rate == 0.25
  assert summary.current_open_tasks == 3

  workload = await service.get_task_workload(
    actor=manager,
    department_id=root.id,
    include_subtree=True,
    start_date=date(2025, 1, 1),
    end_date=date(2025, 1, 31),
  )
  assert len(workload) == 1
  assert workload[0].assignee_id == employee.id
  assert workload[0].period_overdue_tasks == 3

  details = await service.list_task_stats_details(
    actor=manager,
    metric="overdue",
    department_id=root.id,
    include_subtree=True,
    start_date=date(2025, 1, 1),
    end_date=date(2025, 1, 31),
    limit=2,
  )
  assert len(details.items) == 2
  assert details.has_more is True
  assert details.next_cursor is not None

  employee_summary = await service.get_task_stats_summary(
    actor=employee,
    start_date=date(2025, 1, 1),
    end_date=date(2025, 1, 31),
  )
  assert employee_summary.created_tasks == 5
  with pytest.raises(AuthorizationError, match="仅可查看本人"):
    await service.get_task_stats_summary(actor=employee, department_id=child.id)

  employee_scopes = await service.list_task_stats_scopes(actor=employee)
  manager_scopes = await service.list_task_stats_scopes(actor=manager)
  assert employee_scopes.mode == "personal"
  assert manager_scopes.mode == "organization"
  assert {item.id for item in manager_scopes.departments} == {root.id, child.id}


@pytest.mark.asyncio
async def test_s01_rejects_invalid_period(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  admin = await AuthService(db_session, settings).bootstrap_admin(
    email="s01-period-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-S01-PERIOD",
  )
  service = TaskService(db_session, settings=settings)

  with pytest.raises(ConflictError, match="结束日期"):
    await service.get_task_stats_summary(
      actor=admin,
      start_date=date(2025, 2, 1),
      end_date=date(2025, 1, 31),
    )
  with pytest.raises(ConflictError, match="最长为 366 天"):
    await service.get_task_stats_summary(
      actor=admin,
      start_date=date(2024, 1, 1),
      end_date=date(2025, 1, 1),
    )


@pytest.mark.asyncio
async def test_s01_uses_shanghai_calendar_boundaries_and_ignores_future_deadlines(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  admin = await AuthService(db_session, settings).bootstrap_admin(
    email="s01-timezone-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-S01-TZ",
  )
  db_session.add_all(
    [
      Task(
        title="上海元旦前",
        creator_id=admin.id,
        assignee_id=admin.id,
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        source_type=TaskSourceType.MANUAL,
        created_at=datetime(2026, 12, 31, 15, 59, tzinfo=UTC),
      ),
      Task(
        title="上海元旦后",
        creator_id=admin.id,
        assignee_id=admin.id,
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        source_type=TaskSourceType.MANUAL,
        created_at=datetime(2026, 12, 31, 16, 0, tzinfo=UTC),
        due_date=datetime(2027, 1, 2, 4, tzinfo=UTC),
      ),
    ]
  )
  await db_session.commit()

  summary = await TaskService(db_session, settings=settings).get_task_stats_summary(
    actor=admin,
    start_date=date(2027, 1, 1),
    end_date=date(2027, 1, 31),
  )
  assert summary.created_tasks == 1
  assert summary.due_tasks == 1
  assert summary.matured_due_tasks == 0
  assert summary.on_time_completion_rate == 0.0
