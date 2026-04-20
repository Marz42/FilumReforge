from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.enums import PositionAssignmentType, ReportingLineType, UserRole, UserStatus
from app.core.exceptions import ConflictError
from app.models import Department, Position, Profile, ProfilePosition, ReportingLine, User
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.organization_relation_service import OrganizationRelationService
from app.services.profile_field_policy_service import ProfileFieldPolicyService
from app.services.profile_service import ProfileService
from app.services.user_service import UserService

ROOT_PARENT = "__root__"


@dataclass(frozen=True, slots=True)
class SampleDepartmentSpec:
  code: str
  name: str
  parent_code: str | None
  sort_order: int
  manager_email: str | None = None


@dataclass(frozen=True, slots=True)
class SamplePositionSpec:
  code: str
  name: str
  level: str


@dataclass(frozen=True, slots=True)
class SampleUserSpec:
  email: str
  real_name: str
  employee_no: str
  role: UserRole
  status: UserStatus
  department_code: str
  job_title: str
  position_code: str
  phone: str
  hire_date: date
  manager_email: str | None = None
  dotted_manager_email: str | None = None
  custom_fields: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class SeededAccount:
  email: str
  real_name: str
  role: UserRole
  status: UserStatus
  department_code: str
  job_title: str
  password: str


@dataclass(frozen=True, slots=True)
class SampleDataSeedResult:
  admin_email: str
  admin_bootstrapped: bool
  default_password: str
  departments: tuple[str, ...]
  accounts: tuple[SeededAccount, ...]


class SampleDataService:
  def __init__(self, session: AsyncSession, settings: Settings) -> None:
    self._session = session
    self._settings = settings
    self._auth_service = AuthService(session, settings)
    self._user_service = UserService(session)
    self._department_service = DepartmentService(session)
    self._profile_service = ProfileService(session)
    self._organization_relation_service = OrganizationRelationService(session)
    self._field_policy_service = ProfileFieldPolicyService(session)

  async def seed_manual_test_workspace(
    self,
    *,
    default_password: str,
    bootstrap_admin_email: str = "admin@example.com",
    bootstrap_admin_real_name: str = "系统管理员",
    bootstrap_admin_employee_no: str = "EMP-ROOT",
  ) -> SampleDataSeedResult:
    admin, admin_bootstrapped = await self._ensure_admin(
      email=bootstrap_admin_email,
      password=default_password,
      real_name=bootstrap_admin_real_name,
      employee_no=bootstrap_admin_employee_no,
    )
    root_department = await self._get_root_department(admin_user_id=admin.id)

    department_specs = self._build_department_specs()
    position_specs = self._build_position_specs()
    user_specs = self._build_user_specs()

    departments = await self._upsert_departments(actor=admin, root_department=root_department, specs=department_specs)
    users = await self._upsert_users(actor=admin, specs=user_specs, default_password=default_password)
    await self._upsert_profiles(actor=admin, users=users, departments=departments, specs=user_specs)
    await self._sync_department_managers(actor=admin, users=users, departments=departments, specs=department_specs)
    positions = await self._upsert_positions(actor=admin, specs=position_specs)
    await self._upsert_position_assignments(actor=admin, users=users, departments=departments, positions=positions, specs=user_specs)
    await self._upsert_reporting_lines(actor=admin, users=users, departments=departments, specs=user_specs)

    accounts = tuple(
      SeededAccount(
        email=spec.email,
        real_name=spec.real_name,
        role=spec.role,
        status=spec.status,
        department_code=spec.department_code,
        job_title=spec.job_title,
        password=default_password,
      )
      for spec in user_specs
    )
    return SampleDataSeedResult(
      admin_email=admin.email,
      admin_bootstrapped=admin_bootstrapped,
      default_password=default_password,
      departments=tuple(spec.code for spec in department_specs),
      accounts=accounts,
    )

  @staticmethod
  def _build_department_specs() -> tuple[SampleDepartmentSpec, ...]:
    return (
      SampleDepartmentSpec(
        code="people-ops",
        name="人力运营中心",
        parent_code=ROOT_PARENT,
        sort_order=10,
        manager_email="demo.hr@example.com",
      ),
      SampleDepartmentSpec(
        code="tech-center",
        name="技术中心",
        parent_code=ROOT_PARENT,
        sort_order=20,
        manager_email="demo.tech.director@example.com",
      ),
      SampleDepartmentSpec(
        code="platform-team",
        name="平台研发组",
        parent_code="tech-center",
        sort_order=21,
        manager_email="demo.platform.lead@example.com",
      ),
      SampleDepartmentSpec(
        code="customer-success",
        name="客户成功部",
        parent_code=ROOT_PARENT,
        sort_order=30,
        manager_email="demo.success@example.com",
      ),
      SampleDepartmentSpec(
        code="finance-admin",
        name="财务行政部",
        parent_code=ROOT_PARENT,
        sort_order=40,
        manager_email="demo.finance@example.com",
      ),
    )

  @staticmethod
  def _build_position_specs() -> tuple[SamplePositionSpec, ...]:
    return (
      SamplePositionSpec(code="hr-director", name="HR 负责人", level="M2"),
      SamplePositionSpec(code="hrbp", name="HRBP", level="P4"),
      SamplePositionSpec(code="tech-director", name="技术总监", level="M3"),
      SamplePositionSpec(code="platform-lead", name="平台研发负责人", level="M2"),
      SamplePositionSpec(code="software-engineer", name="后端工程师", level="P5"),
      SamplePositionSpec(code="customer-success-manager", name="客户成功经理", level="M2"),
      SamplePositionSpec(code="finance-manager", name="财务行政经理", level="M2"),
    )

  @staticmethod
  def _build_user_specs() -> tuple[SampleUserSpec, ...]:
    return (
      SampleUserSpec(
        email="demo.hr@example.com",
        real_name="林语",
        employee_no="DEMO-001",
        role=UserRole.HR,
        status=UserStatus.ACTIVE,
        department_code="people-ops",
        job_title="HR 负责人",
        position_code="hr-director",
        phone="13800000001",
        hire_date=date(2024, 1, 8),
        custom_fields={"skills": ["招聘", "绩效"], "location": "上海"},
      ),
      SampleUserSpec(
        email="demo.hrbp@example.com",
        real_name="周宁",
        employee_no="DEMO-002",
        role=UserRole.HR,
        status=UserStatus.ACTIVE,
        department_code="people-ops",
        job_title="HRBP",
        position_code="hrbp",
        phone="13800000002",
        hire_date=date(2024, 3, 11),
        manager_email="demo.hr@example.com",
        custom_fields={"skills": ["员工关系", "入离调转"], "location": "上海"},
      ),
      SampleUserSpec(
        email="demo.tech.director@example.com",
        real_name="高原",
        employee_no="DEMO-003",
        role=UserRole.EMPLOYEE,
        status=UserStatus.ACTIVE,
        department_code="tech-center",
        job_title="技术总监",
        position_code="tech-director",
        phone="13800000003",
        hire_date=date(2023, 11, 1),
        custom_fields={"skills": ["架构治理", "交付管理"], "location": "北京"},
      ),
      SampleUserSpec(
        email="demo.platform.lead@example.com",
        real_name="方舟",
        employee_no="DEMO-004",
        role=UserRole.EMPLOYEE,
        status=UserStatus.ACTIVE,
        department_code="platform-team",
        job_title="平台研发负责人",
        position_code="platform-lead",
        phone="13800000004",
        hire_date=date(2024, 2, 15),
        manager_email="demo.tech.director@example.com",
        custom_fields={"skills": ["平台治理", "技术规划"], "location": "北京"},
      ),
      SampleUserSpec(
        email="demo.engineer.a@example.com",
        real_name="顾晨",
        employee_no="DEMO-005",
        role=UserRole.EMPLOYEE,
        status=UserStatus.ACTIVE,
        department_code="platform-team",
        job_title="后端工程师",
        position_code="software-engineer",
        phone="13800000005",
        hire_date=date(2024, 5, 20),
        manager_email="demo.platform.lead@example.com",
        dotted_manager_email="demo.tech.director@example.com",
        custom_fields={"skills": ["Python", "FastAPI"], "location": "杭州"},
      ),
      SampleUserSpec(
        email="demo.engineer.b@example.com",
        real_name="沈墨",
        employee_no="DEMO-006",
        role=UserRole.EMPLOYEE,
        status=UserStatus.ACTIVE,
        department_code="platform-team",
        job_title="后端工程师",
        position_code="software-engineer",
        phone="13800000006",
        hire_date=date(2024, 6, 3),
        manager_email="demo.platform.lead@example.com",
        custom_fields={"skills": ["PostgreSQL", "Redis"], "location": "杭州"},
      ),
      SampleUserSpec(
        email="demo.success@example.com",
        real_name="何清",
        employee_no="DEMO-007",
        role=UserRole.EMPLOYEE,
        status=UserStatus.ACTIVE,
        department_code="customer-success",
        job_title="客户成功经理",
        position_code="customer-success-manager",
        phone="13800000007",
        hire_date=date(2024, 4, 18),
        custom_fields={"skills": ["客户交付", "SOP"], "location": "深圳"},
      ),
      SampleUserSpec(
        email="demo.finance@example.com",
        real_name="唐婧",
        employee_no="DEMO-008",
        role=UserRole.EMPLOYEE,
        status=UserStatus.ACTIVE,
        department_code="finance-admin",
        job_title="财务行政经理",
        position_code="finance-manager",
        phone="13800000008",
        hire_date=date(2024, 1, 22),
        custom_fields={"skills": ["财务分析", "行政采购"], "location": "深圳"},
      ),
      SampleUserSpec(
        email="demo.former@example.com",
        real_name="离职测试员工",
        employee_no="DEMO-009",
        role=UserRole.EMPLOYEE,
        status=UserStatus.OFFBOARDED,
        department_code="customer-success",
        job_title="后端工程师",
        position_code="software-engineer",
        phone="13800000009",
        hire_date=date(2023, 8, 14),
        manager_email="demo.success@example.com",
        custom_fields={"skills": ["历史数据"], "location": "深圳"},
      ),
    )

  async def _ensure_admin(
    self,
    *,
    email: str,
    password: str,
    real_name: str,
    employee_no: str,
  ) -> tuple[User, bool]:
    admin = await self._session.scalar(
      select(User).where(User.role == UserRole.ADMIN).order_by(User.created_at.asc())
    )
    if admin is not None:
      return admin, False

    existing_users = await self._session.scalar(select(func.count()).select_from(User))
    if existing_users:
      raise ConflictError("当前库存在用户数据但没有管理员，无法自动生成测试工作台数据。")

    admin = await self._auth_service.bootstrap_admin(
      email=email,
      password=password,
      real_name=real_name,
      employee_no=employee_no,
    )
    return admin, True

  async def _get_root_department(self, *, admin_user_id) -> Department:  # noqa: ANN001
    admin_profile = await self._session.get(Profile, admin_user_id)
    if admin_profile is None or admin_profile.department_id is None:
      raise ConflictError("管理员缺少档案或所属部门，无法生成测试组织结构。")

    root_department = await self._session.get(Department, admin_profile.department_id)
    if root_department is None:
      raise ConflictError("管理员根部门不存在，无法生成测试组织结构。")
    return root_department

  async def _upsert_departments(
    self,
    *,
    actor: User,
    root_department: Department,
    specs: tuple[SampleDepartmentSpec, ...],
  ) -> dict[str, Department]:
    departments: dict[str, Department] = {root_department.code: root_department}

    for spec in specs:
      parent_id = root_department.id if spec.parent_code == ROOT_PARENT else departments[spec.parent_code].id
      existing = await self._session.scalar(select(Department).where(Department.code == spec.code))
      if existing is None:
        department = await self._department_service.create_department(
          actor=actor,
          name=spec.name,
          code=spec.code,
          parent_id=parent_id,
          sort_order=spec.sort_order,
        )
      else:
        department = await self._department_service.update_department(
          actor=actor,
          department_id=existing.id,
          name=spec.name,
          code=spec.code,
          parent_id=parent_id,
          sort_order=spec.sort_order,
          is_active=True,
        )
      departments[spec.code] = department
    return departments

  async def _upsert_users(
    self,
    *,
    actor: User,
    specs: tuple[SampleUserSpec, ...],
    default_password: str,
  ) -> dict[str, User]:
    users: dict[str, User] = {}
    for spec in specs:
      existing = await self._session.scalar(select(User).where(User.email == spec.email))
      if existing is None:
        user = await self._user_service.create_user(
          actor=actor,
          email=spec.email,
          password=default_password,
          role=spec.role,
          status=spec.status,
        )
      else:
        user = await self._user_service.update_user(
          actor=actor,
          user_id=existing.id,
          password=default_password,
          role=spec.role,
          status=spec.status,
        )
      users[spec.email] = user
    return users

  async def _upsert_profiles(
    self,
    *,
    actor: User,
    users: dict[str, User],
    departments: dict[str, Department],
    specs: tuple[SampleUserSpec, ...],
  ) -> None:
    await self._field_policy_service.ensure_default_definitions()
    for spec in specs:
      user = users[spec.email]
      department = departments[spec.department_code]
      existing = await self._session.get(Profile, user.id)
      if existing is None:
        await self._profile_service.create_profile(
          actor=actor,
          user_id=user.id,
          employee_no=spec.employee_no,
          real_name=spec.real_name,
          department_id=department.id,
          job_title=spec.job_title,
          phone=spec.phone,
          hire_date=spec.hire_date,
          custom_fields=dict(spec.custom_fields or {}),
        )
        continue

      existing.employee_no = spec.employee_no
      existing.real_name = spec.real_name
      existing.department_id = department.id
      existing.job_title = spec.job_title
      existing.phone = spec.phone
      existing.hire_date = spec.hire_date
      existing.custom_fields = dict(spec.custom_fields or {})
      await self._field_policy_service.ensure_custom_field_definitions(existing.custom_fields)
      await self._session.commit()
      await self._session.refresh(existing)

  async def _sync_department_managers(
    self,
    *,
    actor: User,
    users: dict[str, User],
    departments: dict[str, Department],
    specs: tuple[SampleDepartmentSpec, ...],
  ) -> None:
    for spec in specs:
      if spec.manager_email is None:
        continue
      department = departments[spec.code]
      manager = users[spec.manager_email]
      if department.manager_id == manager.id:
        continue
      await self._department_service.update_department(
        actor=actor,
        department_id=department.id,
        manager_id=manager.id,
      )

  async def _upsert_positions(
    self,
    *,
    actor: User,
    specs: tuple[SamplePositionSpec, ...],
  ) -> dict[str, Position]:
    positions: dict[str, Position] = {}
    for spec in specs:
      existing = await self._session.scalar(select(Position).where(Position.code == spec.code))
      if existing is None:
        position = await self._organization_relation_service.create_position(
          actor=actor,
          code=spec.code,
          name=spec.name,
          level=spec.level,
          extra_metadata={"seeded": True},
        )
      else:
        existing.name = spec.name
        existing.level = spec.level
        existing.is_active = True
        existing.extra_metadata = {"seeded": True}
        await self._session.commit()
        await self._session.refresh(existing)
        position = existing
      positions[spec.code] = position
    return positions

  async def _upsert_position_assignments(
    self,
    *,
    actor: User,
    users: dict[str, User],
    departments: dict[str, Department],
    positions: dict[str, Position],
    specs: tuple[SampleUserSpec, ...],
  ) -> None:
    for spec in specs:
      user = users[spec.email]
      department = departments[spec.department_code]
      position = positions[spec.position_code]
      existing = await self._session.scalar(
        select(ProfilePosition).where(
          ProfilePosition.user_id == user.id,
          ProfilePosition.position_id == position.id,
          ProfilePosition.department_id == department.id,
          ProfilePosition.starts_at == spec.hire_date,
        )
      )
      if existing is not None:
        continue
      await self._organization_relation_service.assign_position(
        actor=actor,
        user_id=user.id,
        position_id=position.id,
        department_id=department.id,
        assignment_type=PositionAssignmentType.PRIMARY,
        is_primary=True,
        starts_at=spec.hire_date,
      )

  async def _upsert_reporting_lines(
    self,
    *,
    actor: User,
    users: dict[str, User],
    departments: dict[str, Department],
    specs: tuple[SampleUserSpec, ...],
  ) -> None:
    for spec in specs:
      if spec.manager_email is not None:
        await self._ensure_reporting_line(
          actor=actor,
          user_id=users[spec.email].id,
          manager_user_id=users[spec.manager_email].id,
          line_type=ReportingLineType.SOLID,
          department_id=departments[spec.department_code].id,
          is_primary=True,
          starts_at=spec.hire_date,
        )
      if spec.dotted_manager_email is not None:
        await self._ensure_reporting_line(
          actor=actor,
          user_id=users[spec.email].id,
          manager_user_id=users[spec.dotted_manager_email].id,
          line_type=ReportingLineType.DOTTED,
          department_id=departments[spec.department_code].id,
          is_primary=False,
          starts_at=spec.hire_date,
        )

  async def _ensure_reporting_line(
    self,
    *,
    actor: User,
    user_id,
    manager_user_id,
    line_type: ReportingLineType,
    department_id,
    is_primary: bool,
    starts_at: date,
  ) -> None:
    existing = await self._session.scalar(
      select(ReportingLine).where(
        ReportingLine.user_id == user_id,
        ReportingLine.manager_user_id == manager_user_id,
        ReportingLine.line_type == line_type,
        ReportingLine.department_id == department_id,
        ReportingLine.starts_at == starts_at,
      )
    )
    if existing is not None:
      return
    await self._organization_relation_service.create_reporting_line(
      actor=actor,
      user_id=user_id,
      manager_user_id=manager_user_id,
      line_type=line_type,
      department_id=department_id,
      is_primary=is_primary,
      starts_at=starts_at,
    )
