from __future__ import annotations

from datetime import date

import pytest

from app.core.config import Settings
from app.core.enums import PositionAssignmentType, ReportingLineType, UserRole
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.organization_relation_service import OrganizationRelationService
from app.services.position_workbench_service import PositionWorkbenchService
from app.services.profile_service import ProfileService
from app.services.user_service import UserService

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


@pytest.mark.asyncio
async def test_position_workbench_catalog_and_detail_impact(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )
  user_service = UserService(db_session)
  department_service = DepartmentService(db_session)
  profile_service = ProfileService(db_session)
  organization_relation_service = OrganizationRelationService(db_session)
  workbench = PositionWorkbenchService(db_session)

  manager = await user_service.create_user(
    actor=admin,
    email="wb-manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  employee = await user_service.create_user(
    actor=admin,
    email="wb-employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  secondary = await user_service.create_user(
    actor=admin,
    email="wb-secondary@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  department = await department_service.create_department(
    actor=admin,
    name="Workbench",
    code="workbench",
    manager_id=manager.id,
  )

  for user, employee_no, real_name in (
    (manager, "EMP-WB-M", "Manager"),
    (employee, "EMP-WB-1", "Employee"),
    (secondary, "EMP-WB-2", "Secondary"),
  ):
    await profile_service.create_profile(
      actor=admin,
      user_id=user.id,
      employee_no=employee_no,
      real_name=real_name,
      department_id=department.id,
      custom_fields={},
    )

  position = await organization_relation_service.create_position(
    actor=admin,
    code="wb-specialist",
    name="Workbench Specialist",
    level="P3",
  )
  await organization_relation_service.assign_position(
    actor=admin,
    user_id=employee.id,
    position_id=position.id,
    department_id=department.id,
    assignment_type=PositionAssignmentType.PRIMARY,
    is_primary=True,
    starts_at=date(2025, 1, 1),
  )
  await organization_relation_service.assign_position(
    actor=admin,
    user_id=secondary.id,
    position_id=position.id,
    department_id=department.id,
    assignment_type=PositionAssignmentType.PART_TIME,
    is_primary=False,
    starts_at=date(2025, 2, 1),
  )
  await organization_relation_service.create_reporting_line(
    actor=admin,
    user_id=employee.id,
    manager_user_id=manager.id,
    department_id=department.id,
    line_type=ReportingLineType.SOLID,
    is_primary=True,
    starts_at=date(2025, 1, 1),
  )

  catalog = await workbench.get_catalog(actor=admin, as_of=date(2025, 3, 1))
  item = next(row for row in catalog.positions if row.id == position.id)
  assert item.impact.assignee_count == 2
  assert item.impact.primary_count == 1
  assert item.impact.secondary_count == 1
  assert item.impact.department_count == 1
  assert item.impact.active_reporting_line_count == 1

  detail = await workbench.get_detail(actor=admin, position_id=position.id, as_of=date(2025, 3, 1))
  assert len(detail.assignments) == 2
  assert len(detail.reporting_lines) == 1
  assert detail.effective_range.open_ended_assignment_count == 2
  assert detail.effective_range.earliest_starts_at == date(2025, 1, 1)
