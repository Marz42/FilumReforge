from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.enums import ReportingLineType, UserRole, UserStatus
from app.models import Department, Position, Profile, ProfilePosition, ReportingLine, User
from app.services.auth_service import AuthService
from app.services.sample_data_service import SampleDataService
from app.services.user_service import UserService
from tests.test_services import TEST_JWT_SECRET


@pytest.mark.asyncio
async def test_sample_data_service_seeds_idempotent_workspace(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  service = SampleDataService(db_session, settings)

  first_result = await service.seed_manual_test_workspace(default_password="FilumTest123!")
  second_result = await service.seed_manual_test_workspace(default_password="FilumTest123!")

  users = list(await db_session.scalars(select(User).order_by(User.email.asc())))
  departments = list(await db_session.scalars(select(Department).order_by(Department.code.asc())))
  profiles = list(await db_session.scalars(select(Profile).order_by(Profile.employee_no.asc())))
  positions = list(await db_session.scalars(select(Position).order_by(Position.code.asc())))
  assignments = list(await db_session.scalars(select(ProfilePosition)))
  reporting_lines = list(await db_session.scalars(select(ReportingLine)))

  assert first_result.admin_bootstrapped is True
  assert second_result.admin_bootstrapped is False
  assert first_result.admin_email == "admin@example.com"
  assert len(first_result.accounts) == 9
  assert len(users) == 10
  assert len(departments) == 6
  assert len(profiles) == 10
  assert len(positions) == 7
  assert len(assignments) == 9
  assert len(reporting_lines) == 6
  assert {department.code for department in departments} >= {
    "root",
    "people-ops",
    "tech-center",
    "platform-team",
    "customer-success",
    "finance-admin",
  }

  former_user = next(user for user in users if user.email == "demo.former@example.com")
  assert former_user.status == UserStatus.OFFBOARDED
  engineer_a = next(user for user in users if user.email == "demo.engineer.a@example.com")
  engineer_a_profile = await db_session.get(Profile, engineer_a.id)
  assert engineer_a_profile is not None
  assert engineer_a_profile.job_title == "后端工程师"
  dotted_line = next(
    line
    for line in reporting_lines
    if line.user_id == engineer_a.id and line.line_type == ReportingLineType.DOTTED
  )
  assert dotted_line is not None


@pytest.mark.asyncio
async def test_sample_data_service_resets_seeded_passwords(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )
  user_service = UserService(db_session)
  await user_service.create_user(
    actor=admin,
    email="demo.hr@example.com",
    password="OldPassword123!",
    role=UserRole.HR,
  )

  result = await SampleDataService(db_session, settings).seed_manual_test_workspace(
    default_password="FilumTest123!",
  )
  session = await auth_service.authenticate(email="demo.hr@example.com", password="FilumTest123!")

  assert result.admin_bootstrapped is False
  assert session.user.email == "demo.hr@example.com"
