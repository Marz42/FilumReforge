from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.enums import (
  AttachmentStatus,
  AttachmentTargetType,
  CommentFormat,
  DEFAULT_USER_NOTIFICATION_CHANNELS,
  DepartmentCapability,
  DelegationScopeType,
  DocumentCategory,
  DocumentStatus,
  EmploymentEventType,
  ReportDirection,
  ReportRouteStatus,
  ReportStatus,
  NotificationChannel,
  NotificationDeliveryStatus,
  NotificationMessageStatus,
  NotificationReceiptType,
  TaskPriority,
  TaskSourceType,
  PushSubscriptionStatus,
  PositionAssignmentType,
  ReportingLineType,
  TaskActionType,
  TaskStatus,
  UserRole,
  UserStatus,
  WorkflowGraphInstanceStatus,
  WorkflowDefinitionStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
  WorkflowInstanceStatus,
)
from app.core.exceptions import AppValidationError, AuthenticationError, AuthorizationError, ConflictError, NotFoundError
from app.models import (
  Attachment,
  AttachmentLink,
  Department,
  NotificationDelivery,
  NotificationMessage as NotificationMessageModel,
  Task,
  TaskDependency,
  WorkflowDeliverable,
  TaskLog,
  TaskTemplate,
  TaskTemplateStep,
  TaskTemplateInstance,
  TaskTemplateStepRun,
  User,
  WorkflowGraphInstance,
  WorkflowHumanTaskLink,
  WorkflowInstance,
  WorkflowNodeInstance,
)
from app.models import Announcement, BoardCard
from app.integrations.storage.local import LocalStorageAdapter
from app.services.announcement_service import AnnouncementService
from app.services.attachment_service import AttachmentService
from app.services.auth_service import AuthService
from app.services.board_service import BoardService
from app.services.browser_push_service import BrowserPushService
from app.services.delegation_service import DelegationService
from app.services.department_service import DepartmentService
from app.services.document_service import DocumentService
from app.services.hr_lifecycle_service import HRLifecycleService, PROCESS_EMPLOYMENT_EVENT_JOB
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.legacy_task_graph_migration_service import LegacyTaskGraphMigrationService
from app.services.llm_router_service import LLMRouterService
from app.services.message_center_service import MessageCenterService
from app.services.notification_service import NotificationService
from app.services.notification_source import build_task_source_payload
from app.services.object_storage_service import ObjectStorageService
from app.services.organization_relation_service import OrganizationRelationService
from app.services.people_management_service import PeopleManagementService
from app.services.profile_service import ProfileService
from app.services.report_center_service import ReportCenterService
from app.services.report_service import ReportService
from app.services.sample_data_service import SampleDataService
from app.schemas.messages import NotificationMessage
from app.services.task_automation_service import TaskAutomationService
from app.services.task_memo_service import TaskMemoService
from app.services.task_service import CommentAttachmentInput, TaskService
from app.services.task_template_service import TaskTemplateService
from app.services.tool_registry_service import ToolRegistryService
from app.services.user_service import UserService
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_engine_service import WorkflowEngineService

LEGACY_E_REMOVED = pytest.mark.skip(reason="B-12: Legacy E task template runtime removed")


class InMemoryQueuePublisher:
  def __init__(self) -> None:
    self.payloads: list[dict[str, str]] = []
    self.jobs: list[tuple[str, tuple[object, ...]]] = []

  async def publish(self, payload):  # noqa: ANN001
    self.payloads.append(payload)

  async def enqueue(self, job_name: str, *args: object) -> None:
    self.jobs.append((job_name, args))


class FailingQueuePublisher:
  def __init__(self, error_message: str = "queue unavailable") -> None:
    self.error_message = error_message

  async def publish(self, payload):  # noqa: ANN001
    raise RuntimeError(self.error_message)


class FakeOpenAIClient:
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


class FakeRouterOpenAIClient(FakeOpenAIClient):
  def __init__(self) -> None:
    self.chat_calls = 0

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


TEST_JWT_SECRET = "test-secret-key-with-32-bytes-minimum!!"


async def _create_legacy_template_backed_task(*, db_session, admin: User, assignee: User) -> Task:
  template = TaskTemplate(
    code="legacy-template",
    base_code="legacy-template",
    version=1,
    name="旧模板任务",
    category="ops",
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  step = TaskTemplateStep(
    template_id=template.id,
    step_key="step-1",
    title="历史步骤",
    default_assignee_rule={},
    sort_order=1,
  )
  db_session.add(step)
  await db_session.flush()

  template_instance = TaskTemplateInstance(
    template_id=template.id,
    initiator_user_id=admin.id,
    department_id=None,
    status="in_progress",
    payload={"legacy": True},
  )
  db_session.add(template_instance)
  await db_session.flush()

  step_run = TaskTemplateStepRun(
    instance_id=template_instance.id,
    template_step_id=step.id,
    assignee_user_id=assignee.id,
    status="completed",
    completed_at=datetime.now(UTC),
  )
  db_session.add(step_run)
  await db_session.flush()

  task = Task(
    title="旧模板步骤任务",
    description="历史模板运行态任务",
    creator_id=admin.id,
    assignee_id=assignee.id,
    template_instance_id=template_instance.id,
    template_step_run_id=step_run.id,
    source_type=TaskSourceType.TEMPLATE,
    status=TaskStatus.REVIEW,
    priority=TaskPriority.HIGH,
    extra_metadata={
      "template_instance_id": str(template_instance.id),
      "template_step_run_id": str(step_run.id),
      "latest_deliverable_summary": "历史交付说明",
      "latest_deliverable_attachment_ids": [],
      "latest_deliverable_submitted_at": datetime.now(UTC).isoformat(),
      "latest_deliverable_submitted_by_user_id": str(assignee.id),
      "latest_review_state": "pending_review",
    },
  )
  db_session.add(task)
  await db_session.flush()
  return task


@pytest.mark.asyncio
async def test_auth_service_bootstrap_login_and_refresh(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET, storage_base_path="./.storage-test")
  auth_service = AuthService(db_session, settings)

  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )
  session = await auth_service.authenticate(email="admin@example.com", password="StrongPassword123!")
  refreshed = await auth_service.refresh(refresh_token=session.refresh_token)
  revoked = await auth_service.revoke_refresh_token(refresh_token=refreshed.refresh_token)
  access_user = await auth_service.get_user_from_access_token(session.access_token)

  assert admin.role == UserRole.ADMIN
  assert session.token_type == "bearer"
  assert refreshed.access_token != session.access_token
  assert revoked is True
  assert access_user.id == admin.id
  with pytest.raises(AuthenticationError):
    await auth_service.refresh(refresh_token=refreshed.refresh_token)


@pytest.mark.asyncio
async def test_auth_service_invitation_flow_create_accept_and_revoke(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET, frontend_app_url="https://app.example.com")
  auth_service = AuthService(db_session, settings)

  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  invitation = await auth_service.create_invitation(
    actor=admin,
    email="invited@example.com",
    role=UserRole.EMPLOYEE,
  )
  invitation_token = invitation.invite_url.split("invite=", maxsplit=1)[1]
  preview_user = await auth_service.get_invitation_preview(token=invitation_token)

  assert invitation.user.status == UserStatus.INACTIVE
  assert preview_user.email == "invited@example.com"

  accepted_session = await auth_service.accept_invitation(
    token=invitation_token,
    password="StrongPassword123!",
  )
  second_invitation = await auth_service.create_invitation(
    actor=admin,
    email="another-invite@example.com",
    role=UserRole.HR,
  )
  second_token = second_invitation.invite_url.split("invite=", maxsplit=1)[1]
  revoked_user = await auth_service.revoke_invitation(actor=admin, user_id=second_invitation.user.id)

  assert invitation.invite_url.startswith("https://app.example.com/login?invite=")
  assert accepted_session.user.status == UserStatus.ACTIVE
  assert accepted_session.user.invitation_accepted_at is not None
  assert accepted_session.user.invitation_token_hash is None
  assert revoked_user.invitation_revoked_at is not None
  with pytest.raises(ConflictError, match="已被撤销"):
    await auth_service.get_invitation_preview(token=second_token)


@pytest.mark.asyncio
async def test_department_profile_and_user_services(db_session) -> None:
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

  hr_user = await user_service.create_user(
    actor=admin,
    email="hr@example.com",
    password="StrongPassword123!",
    role=UserRole.HR,
  )
  department = await department_service.create_department(
    actor=admin,
    name="人事部",
    code="hr-dept",
    manager_id=hr_user.id,
  )
  profile = await profile_service.create_profile(
    actor=admin,
    user_id=hr_user.id,
    employee_no="EMP-HR-001",
    real_name="人事专员",
    department_id=department.id,
    custom_fields={"skills": ["recruiting"]},
  )

  users = await user_service.list_users(actor=admin)
  departments = await department_service.list_departments(actor=admin)
  profiles = await profile_service.list_profiles(actor=admin)

  assert hr_user in users
  assert department in departments
  assert profile in profiles
  assert profile.custom_fields["skills"] == ["recruiting"]


@pytest.mark.asyncio
async def test_user_service_allows_delete_only_for_unprofiled_accounts(db_session) -> None:
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

  department = await department_service.create_department(
    actor=admin,
    name="测试部门",
    code="test-delete-department",
  )

  deletable_user = await user_service.create_user(
    actor=admin,
    email="pending-delete@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
    status=UserStatus.INACTIVE,
  )
  profiled_user = await user_service.create_user(
    actor=admin,
    email="profiled-delete@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
    status=UserStatus.ACTIVE,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=profiled_user.id,
    employee_no="EMP-DELETE-001",
    real_name="不可删除账号",
    department_id=department.id,
    custom_fields={},
  )

  await user_service.delete_user(actor=admin, user_id=deletable_user.id)

  deleted_user = await db_session.get(User, deletable_user.id)
  assert deleted_user is None

  with pytest.raises(ConflictError, match="已建档"):
    await user_service.delete_user(actor=admin, user_id=profiled_user.id)


@pytest.mark.asyncio
async def test_department_service_supports_clearing_manager_and_deleting_empty_leaf(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )
  department_service = DepartmentService(db_session)
  user_service = UserService(db_session)

  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  department = await department_service.create_department(
    actor=admin,
    name="研发部",
    code="engineering",
    manager_id=manager.id,
  )

  updated_department = await department_service.update_department(
    actor=admin,
    department_id=department.id,
    fields_set={"manager_id", "name"},
    manager_id=None,
    name="产品研发部",
  )

  assert updated_department.manager_id is None
  assert updated_department.name == "产品研发部"

  await department_service.delete_department(actor=admin, department_id=department.id)
  deleted_department = await db_session.get(Department, department.id)

  assert deleted_department is None


@pytest.mark.asyncio
async def test_department_service_rejects_invalid_parent_cycles_and_non_empty_delete(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )
  department_service = DepartmentService(db_session)
  profile_service = ProfileService(db_session)
  user_service = UserService(db_session)

  root_department = await db_session.scalar(select(Department).where(Department.code == "root"))
  assert root_department is not None

  parent_department = await department_service.create_department(
    actor=admin,
    name="一级部门",
    code="level-one",
    parent_id=root_department.id,
  )
  child_department = await department_service.create_department(
    actor=admin,
    name="二级部门",
    code="level-two",
    parent_id=parent_department.id,
  )

  with pytest.raises(ConflictError, match="自己的下级部门"):
    await department_service.update_department(
      actor=admin,
      department_id=parent_department.id,
      fields_set={"parent_id"},
      parent_id=child_department.id,
    )

  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-001",
    real_name="研发工程师",
    department_id=child_department.id,
  )

  with pytest.raises(ConflictError, match="关联档案"):
    await department_service.delete_department(actor=admin, department_id=child_department.id)

  with pytest.raises(ConflictError, match="根节点"):
    await department_service.delete_department(actor=admin, department_id=root_department.id)


@pytest.mark.asyncio
async def test_people_management_service_aggregates_accounts_and_profiles(db_session) -> None:
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
  lifecycle_service = HRLifecycleService(db_session)
  people_management_service = PeopleManagementService(db_session)

  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  pending_user = await user_service.create_user(
    actor=admin,
    email="pending@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
    status=UserStatus.INACTIVE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="研发部",
    code="engineering",
    manager_id=manager.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=manager.id,
    employee_no="EMP-MANAGER-001",
    real_name="技术负责人",
    department_id=department.id,
    job_title="技术负责人",
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-001",
    real_name="研发工程师",
    department_id=department.id,
    job_title="后端工程师",
  )
  await organization_relation_service.create_reporting_line(
    actor=admin,
    user_id=employee.id,
    manager_user_id=manager.id,
    line_type=ReportingLineType.SOLID,
    department_id=department.id,
    is_primary=True,
    starts_at=date(2025, 1, 1),
  )
  await lifecycle_service.create_event(
    actor=admin,
    user_id=employee.id,
    event_type=EmploymentEventType.PROMOTION,
    effective_date=date(2025, 2, 1),
    title="晋升为后端工程师",
    summary="完成试用期",
    payload={},
  )

  snapshot = await people_management_service.list_people(actor=admin)

  assert snapshot.summary == {
    "total_people": 4,
    "profiled_people": 3,
    "unprofiled_people": 1,
    "inactive_people": 1,
  }
  employee_item = next(item for item in snapshot.people if item["user_id"] == employee.id)
  assert employee_item["has_profile"] is True
  assert employee_item["department_name"] == "研发部"
  pending_item = next(item for item in snapshot.people if item["email"] == "pending@example.com")
  assert pending_item["profile_completion_state"] == "missing_profile"

  detail = await people_management_service.get_person_detail(actor=admin, user_id=employee.id)

  assert detail.summary["real_name"] == "研发工程师"
  assert detail.actions["can_edit_user"] is True
  assert detail.actions["can_delete_user"] is False
  assert detail.actions["can_create_profile"] is False
  assert detail.primary_manager_label == "技术负责人"
  assert detail.latest_employment_event is not None
  assert detail.latest_employment_event.event_type == EmploymentEventType.PROMOTION

  pending_detail = await people_management_service.get_person_detail(actor=admin, user_id=pending_user.id)
  assert pending_detail.actions["can_delete_user"] is True


@pytest.mark.asyncio
async def test_attachment_service_upload_and_soft_delete(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  with TemporaryDirectory() as tmp_dir:
    storage_service = ObjectStorageService(
      LocalStorageAdapter(base_path=tmp_dir, bucket="filum-test")
    )
    attachment_service = AttachmentService(db_session, storage_service)

    attachment = await attachment_service.upload_attachment(
      actor=admin,
      filename="spec.pdf",
      content_type="application/pdf",
      content=b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
      target_type=AttachmentTargetType.TASK,
      target_id=admin.id,
    )
    deleted = await attachment_service.delete_attachment(actor=admin, attachment_id=attachment.id)

    file_path = Path(tmp_dir) / "filum-test" / attachment.object_key
    assert attachment.original_filename == "spec.pdf"
    assert deleted.status == AttachmentStatus.DELETED
    assert not file_path.exists()


@pytest.mark.asyncio
async def test_attachment_service_rejects_mismatched_binary_content(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  with TemporaryDirectory() as tmp_dir:
    storage_service = ObjectStorageService(
      LocalStorageAdapter(base_path=tmp_dir, bucket="filum-test")
    )
    attachment_service = AttachmentService(db_session, storage_service)

    with pytest.raises(AppValidationError):
      await attachment_service.upload_attachment(
        actor=admin,
        filename="fake.pdf",
        content_type="application/pdf",
        content=b"not-a-real-pdf",
      )


def _minimal_xlsx_bytes() -> bytes:
  import io
  import zipfile

  buf = io.BytesIO()
  with zipfile.ZipFile(buf, "w") as zf:
    zf.writestr(
      "[Content_Types].xml",
      b'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      b'<Default Extension="xml" ContentType="application/xml"/></Types>',
    )
    zf.writestr("_rels/.rels", b"")
    zf.writestr(
      "xl/workbook.xml",
      b'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>',
    )
  return buf.getvalue()


def _minimal_docx_bytes() -> bytes:
  import io
  import zipfile

  buf = io.BytesIO()
  with zipfile.ZipFile(buf, "w") as zf:
    zf.writestr(
      "[Content_Types].xml",
      b'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      b'<Default Extension="xml" ContentType="application/xml"/></Types>',
    )
    zf.writestr("_rels/.rels", b"")
    zf.writestr(
      "word/document.xml",
      b'<document xmlns="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>',
    )
  return buf.getvalue()


@pytest.mark.asyncio
async def test_attachment_service_accepts_xlsx_docx_wav_mp3(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  with TemporaryDirectory() as tmp_dir:
    storage_service = ObjectStorageService(
      LocalStorageAdapter(base_path=tmp_dir, bucket="filum-test")
    )
    attachment_service = AttachmentService(db_session, storage_service)

    xlsx = await attachment_service.upload_attachment(
      actor=admin,
      filename="t.xlsx",
      content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      content=_minimal_xlsx_bytes(),
    )
    assert 'spreadsheetml' in xlsx.mime_type

    docx = await attachment_service.upload_attachment(
      actor=admin,
      filename="t.docx",
      content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      content=_minimal_docx_bytes(),
    )
    assert "wordprocessingml" in docx.mime_type

    wav = await attachment_service.upload_attachment(
      actor=admin,
      filename="t.wav",
      content_type="audio/wav",
      content=b"RIFF" + (4).to_bytes(4, "little") + b"WAVE",
    )
    assert wav.mime_type == "audio/wav"

    mp3 = await attachment_service.upload_attachment(
      actor=admin,
      filename="t.mp3",
      content_type="audio/mpeg",
      content=b"\xff\xfb\x90\x00" + b"\x00" * 64,
    )
    assert mp3.mime_type == "audio/mpeg"


@pytest.mark.asyncio
async def test_attachment_service_infers_generic_mime_from_safe_extensions(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="mime-inference@example.com",
    password="StrongPassword123!",
    real_name="MIME 测试管理员",
    employee_no="EMP-MIME",
  )

  with TemporaryDirectory() as tmp_dir:
    storage_service = ObjectStorageService(
      LocalStorageAdapter(base_path=tmp_dir, bucket="filum-test")
    )
    attachment_service = AttachmentService(db_session, storage_service)

    markdown = await attachment_service.upload_attachment(
      actor=admin,
      filename="requirements.md",
      content_type="application/octet-stream",
      content="# Requirements\n".encode(),
    )
    assert markdown.mime_type == "text/markdown"

    docx = await attachment_service.upload_attachment(
      actor=admin,
      filename="proposal.docx",
      content_type="",
      content=_minimal_docx_bytes(),
    )
    assert docx.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    with pytest.raises(AppValidationError, match="不支持的附件类型"):
      await attachment_service.upload_attachment(
        actor=admin,
        filename="payload.bin",
        content_type="application/octet-stream",
        content=b"opaque",
      )


@pytest.mark.asyncio
async def test_attachment_service_rejects_oversized_text(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  with TemporaryDirectory() as tmp_dir:
    storage_service = ObjectStorageService(
      LocalStorageAdapter(base_path=tmp_dir, bucket="filum-test")
    )
    attachment_service = AttachmentService(db_session, storage_service)
    big = b"a" * (10 * 1024 * 1024 + 1)
    with pytest.raises(AppValidationError, match="10MB"):
      await attachment_service.upload_attachment(
        actor=admin,
        filename="big.txt",
        content_type="text/plain",
        content=big,
      )


@pytest.mark.asyncio
async def test_task_service_creates_task_and_enqueues_notification(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  notification_queue = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, notification_queue)
  task_service = TaskService(db_session, notification_service)
  push_service = BrowserPushService(db_session)

  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  admin_profile = await profile_service.get_profile(actor=admin, user_id=admin.id)
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-001",
    real_name="普通员工",
    department_id=admin_profile.department_id,
  )
  await push_service.upsert_subscription(
    actor=employee,
    endpoint="https://push.example.com/subscriptions/task-assigned",
    p256dh_key="p256dh",
    auth_key="auth",
    user_agent="Mozilla/5.0",
  )

  task = await task_service.create_task(
    actor=admin,
    title="完成档案初始化",
    assignee_id=employee.id,
  )
  tasks_for_employee = await task_service.list_tasks(actor=employee)
  task_logs = list(
    await db_session.scalars(select(TaskLog).where(TaskLog.task_id == task.id).order_by(TaskLog.created_at.asc()))
  )
  assignment_message = await db_session.scalar(
    select(NotificationMessageModel).where(
      NotificationMessageModel.source_type == "task",
      NotificationMessageModel.source_id == task.id,
      NotificationMessageModel.message_type == "task_assigned",
      NotificationMessageModel.recipient_user_id == employee.id,
    )
  )
  assert assignment_message is not None
  deliveries = list(
    await db_session.scalars(
      select(NotificationDelivery)
      .where(NotificationDelivery.message_id == assignment_message.id)
      .order_by(NotificationDelivery.created_at.asc())
    )
  )

  assert task in tasks_for_employee
  assert len(notification_queue.payloads) == 1
  assert notification_queue.payloads[0]["message_type"] == "task_assigned"
  assert [log.action_type for log in task_logs] == [TaskActionType.CREATED, TaskActionType.ASSIGNED]
  assert {delivery.channel for delivery in deliveries} == set(DEFAULT_USER_NOTIFICATION_CHANNELS)


@pytest.mark.asyncio
async def test_create_task_binds_orphan_attachments(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )
  employee = User(
    email="employee@example.com",
    password_hash="hashed",
    role=UserRole.EMPLOYEE,
    status=UserStatus.ACTIVE,
  )
  db_session.add(employee)
  await db_session.commit()
  await db_session.refresh(employee)

  with TemporaryDirectory() as tmp_dir:
    storage_service = ObjectStorageService(
      LocalStorageAdapter(base_path=tmp_dir, bucket="filum-test")
    )
    attachment_service = AttachmentService(db_session, storage_service)
    task_service = TaskService(db_session)

    draft_attachment = await attachment_service.upload_attachment(
      actor=admin,
      filename="brief.pdf",
      content_type="application/pdf",
      content=b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
    )
    task = await task_service.create_task(
      actor=admin,
      title="带附件任务",
      assignee_id=employee.id,
      attachment_ids=[draft_attachment.id],
    )
    link = await db_session.scalar(
      select(AttachmentLink).where(
        AttachmentLink.attachment_id == draft_attachment.id,
        AttachmentLink.target_type == AttachmentTargetType.TASK,
        AttachmentLink.target_id == task.id,
      )
    )

    assert link is not None


@pytest.mark.asyncio
async def test_phase3_single_node_workflow_creation_projects_task_and_graph_entities(db_session) -> None:
  settings = Settings(
    jwt_secret_key=TEST_JWT_SECRET,
    workflow_graph_engine_enabled=True,
  )
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  notification_queue = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, notification_queue)
  task_service = TaskService(
    db_session,
    notification_service,
    settings=settings,
    workflow_graph_service=WorkflowGraphService(db_session),
  )

  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  admin_profile = await profile_service.get_profile(actor=admin, user_id=admin.id)
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-001",
    real_name="普通员工",
    department_id=admin_profile.department_id,
  )

  dependency = await task_service.create_task(
    actor=admin,
    title="先完成前置校验",
    assignee_id=employee.id,
  )
  task = await task_service.create_task(
    actor=admin,
    title="完成图引擎试点任务",
    assignee_id=employee.id,
    dependency_ids=[dependency.id],
  )

  stored_task = await db_session.get(Task, task.id)
  stored_instance = await db_session.scalar(
    select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == task.id)
  )
  stored_node = await db_session.scalar(
    select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == stored_instance.id)
  )
  stored_dependency = await db_session.scalar(
    select(TaskDependency).where(TaskDependency.task_id == task.id, TaskDependency.depends_on_task_id == dependency.id)
  )
  stored_link = await db_session.scalar(
    select(WorkflowHumanTaskLink).where(WorkflowHumanTaskLink.task_id == task.id)
  )

  assert stored_task is not None
  assert stored_task.extra_metadata["workflow_graph_instance_id"] == str(stored_instance.id)
  assert stored_task.extra_metadata["workflow_node_instance_id"] == str(stored_node.id)
  assert stored_instance is not None
  assert stored_instance.source_type == "manual"
  assert stored_instance.context["title"] == "完成图引擎试点任务"
  assert stored_node is not None
  assert stored_node.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert stored_node.business_state == WorkflowNodeBusinessState.ASSIGNED
  assert stored_node.assignee_user_id == employee.id
  assert stored_node.config["task_id"] == str(task.id)
  assert stored_link is not None
  assert stored_link.instance_id == stored_instance.id
  assert stored_link.node_instance_id == stored_node.id
  assert stored_link.source == "manual_compat"
  assert stored_dependency is not None
  assert len(notification_queue.payloads) == 2


@pytest.mark.asyncio
async def test_phase5_graph_task_supports_deliverable_review_and_rework_cycle(db_session) -> None:
  settings = Settings(
    jwt_secret_key=TEST_JWT_SECRET,
    workflow_graph_engine_enabled=True,
  )
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  notification_service = NotificationService(db_session, InMemoryQueuePublisher())
  task_service = TaskService(
    db_session,
    notification_service,
    settings=settings,
    workflow_graph_service=WorkflowGraphService(db_session),
  )

  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  admin_profile = await profile_service.get_profile(actor=admin, user_id=admin.id)
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-001",
    real_name="普通员工",
    department_id=admin_profile.department_id,
  )

  task = await task_service.create_task(
    actor=admin,
    title="完成交付闭环",
    assignee_id=employee.id,
  )
  await task_service.accept_task_assignment(
    actor=employee,
    task_id=task.id,
  )
  doing_task = await task_service.transition_task_status(
    actor=employee,
    task_id=task.id,
    target_status=TaskStatus.DOING,
  )
  assert doing_task.status == TaskStatus.DOING

  review_task = await task_service.submit_task_deliverable(
    actor=employee,
    task_id=task.id,
    summary="第一版交付说明",
  )
  assert review_task.status == TaskStatus.REVIEW
  assert review_task.extra_metadata["latest_deliverable_summary"] == "第一版交付说明"

  reworked_task = await task_service.review_task_deliverable(
    actor=admin,
    task_id=task.id,
    approve=False,
    comment="请补充风险评估",
  )
  assert reworked_task.status == TaskStatus.DOING
  assert reworked_task.extra_metadata["rework_count"] == 1
  assert reworked_task.extra_metadata["latest_rework_reason"] == "请补充风险评估"

  second_review_task = await task_service.submit_task_deliverable(
    actor=employee,
    task_id=task.id,
    summary="第二版交付说明",
  )
  assert second_review_task.status == TaskStatus.REVIEW
  tracking_before_approve = (await task_service.list_task_tracking(actor=employee)).items
  approved_task = await task_service.review_task_deliverable(
    actor=admin,
    task_id=task.id,
    approve=True,
    comment="验收通过",
    quality_score=5,
  )

  stored_instance = await db_session.scalar(
    select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == task.id)
  )
  stored_node = await db_session.scalar(
    select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == stored_instance.id)
  )
  stored_deliverable = await db_session.scalar(
    select(WorkflowDeliverable).where(WorkflowDeliverable.node_instance_id == stored_node.id)
  )
  task_logs = list(
    await db_session.scalars(select(TaskLog).where(TaskLog.task_id == task.id).order_by(TaskLog.created_at.asc()))
  )

  tracked_review_item = next(item for item in tracking_before_approve if item.task_id == task.id)
  assert tracked_review_item.is_pending_review is True
  assert tracked_review_item.rework_count == 1
  assert tracked_review_item.latest_deliverable_submitted_at is not None
  assert approved_task.status == TaskStatus.DONE
  assert approved_task.completed_at is not None
  assert approved_task.extra_metadata["latest_review_quality_score"] == 5
  assert stored_instance is not None
  assert stored_instance.status.value == "completed"
  assert stored_node is not None
  assert stored_node.engine_state == WorkflowNodeEngineState.COMPLETED
  assert stored_node.business_state == WorkflowNodeBusinessState.DONE
  assert stored_deliverable is not None
  assert stored_deliverable.summary == "第二版交付说明"
  assert stored_deliverable.payload["latest_review"]["action"] == "approve_completion"
  assert approved_task.extra_metadata["latest_review_quality_score"] == 5
  assert len(stored_deliverable.payload["submission_history"]) == 2
  assert [log.detail.get("action") for log in task_logs if log.action_type == TaskActionType.STATUS_CHANGED][-4:] == [
    "submit_deliverable",
    "return_for_rework",
    "submit_deliverable",
    "approve_completion",
  ]
  assert task_logs[-1].detail.get("quality_score") == 5


@pytest.mark.asyncio
async def test_submit_task_deliverable_validates_attachment_links(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )
  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  task_service = TaskService(db_session)

  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  admin_profile = await profile_service.get_profile(actor=admin, user_id=admin.id)
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-001",
    real_name="普通员工",
    department_id=admin_profile.department_id,
  )

  task = await task_service.create_task(
    actor=admin,
    title="带附件交付",
    assignee_id=employee.id,
  )
  await task_service.transition_task_status(
    actor=employee,
    task_id=task.id,
    target_status=TaskStatus.DOING,
  )

  with TemporaryDirectory() as tmp_dir:
    attachment_service = AttachmentService(
      db_session,
      ObjectStorageService(LocalStorageAdapter(base_path=tmp_dir, bucket="filum-test")),
    )
    attachment = await attachment_service.upload_attachment(
      actor=employee,
      filename="script.txt",
      content_type="text/plain",
      content=b"script body",
      target_type=AttachmentTargetType.TASK,
      target_id=task.id,
      relation="deliverable",
    )

  review_task = await task_service.submit_task_deliverable(
    actor=employee,
    task_id=task.id,
    summary="脚本文稿",
    attachment_ids=[attachment.id],
  )

  assert review_task.status == TaskStatus.REVIEW
  assert review_task.extra_metadata["latest_deliverable_attachment_ids"] == [str(attachment.id)]


@pytest.mark.asyncio
async def test_phase4_graph_task_requires_accept_before_start_and_updates_inbox_context(db_session) -> None:
  settings = Settings(
    jwt_secret_key=TEST_JWT_SECRET,
    workflow_graph_engine_enabled=True,
  )
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  task_service = TaskService(
    db_session,
    NotificationService(db_session, InMemoryQueuePublisher()),
    settings=settings,
    workflow_graph_service=WorkflowGraphService(db_session),
  )

  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  admin_profile = await profile_service.get_profile(actor=admin, user_id=admin.id)
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-001",
    real_name="普通员工",
    department_id=admin_profile.department_id,
  )

  task = await task_service.create_task(
    actor=admin,
    title="等待接单的图任务",
    assignee_id=employee.id,
  )

  inbox_before_accept = (await task_service.list_task_inbox(actor=employee)).items
  assert any(entry.task_id == task.id and entry.current_stage_label.endswith("：待确认") for entry in inbox_before_accept)

  with pytest.raises(ConflictError, match="先由执行人接受任务"):
    await task_service.transition_task_status(
      actor=employee,
      task_id=task.id,
      target_status=TaskStatus.DOING,
    )

  accepted_task = await task_service.accept_task_assignment(
    actor=employee,
    task_id=task.id,
  )
  accepted_inbox = (await task_service.list_task_inbox(actor=employee)).items
  stored_instance = await db_session.scalar(
    select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == task.id)
  )
  stored_node = await db_session.scalar(
    select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == stored_instance.id)
  )

  assert accepted_task.status == TaskStatus.TODO
  assert accepted_task.extra_metadata["workflow_handshake_state"] == "accepted"
  assert any(entry.task_id == task.id and entry.current_stage_label.endswith("：已接受待开工") for entry in accepted_inbox)
  assert stored_node is not None
  assert stored_node.engine_state == WorkflowNodeEngineState.ACKNOWLEDGED
  assert stored_node.business_state == WorkflowNodeBusinessState.ACCEPTED

  doing_task = await task_service.transition_task_status(
    actor=employee,
    task_id=task.id,
    target_status=TaskStatus.DOING,
  )
  assert doing_task.status == TaskStatus.DOING


@pytest.mark.asyncio
async def test_phase4_graph_task_reject_and_delegate_refresh_runtime_projection(db_session) -> None:
  settings = Settings(
    jwt_secret_key=TEST_JWT_SECRET,
    workflow_graph_engine_enabled=True,
  )
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  task_service = TaskService(
    db_session,
    NotificationService(db_session, InMemoryQueuePublisher()),
    settings=settings,
    workflow_graph_service=WorkflowGraphService(db_session),
  )

  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  delegate_target = await user_service.create_user(
    actor=admin,
    email="delegate@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  admin_profile = await profile_service.get_profile(actor=admin, user_id=admin.id)
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-001",
    real_name="普通员工",
    department_id=admin_profile.department_id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=delegate_target.id,
    employee_no="EMP-002",
    real_name="代理执行人",
    department_id=admin_profile.department_id,
  )

  delegated_task = await task_service.create_task(
    actor=admin,
    title="待转办图任务",
    assignee_id=employee.id,
  )
  delegated_task = await task_service.delegate_task_assignment(
    actor=employee,
    task_id=delegated_task.id,
    assignee_id=delegate_target.id,
    reason="请由更熟悉客户的人处理",
  )

  delegate_inbox = (await task_service.list_task_inbox(actor=delegate_target)).items
  creator_tracking = (await task_service.list_task_tracking(actor=admin)).items

  assert delegated_task.assignee_id == delegate_target.id
  assert delegated_task.extra_metadata["workflow_handshake_state"] == "assigned"
  assert delegated_task.extra_metadata["latest_delegate_reason"] == "请由更熟悉客户的人处理"
  assert any(entry.task_id == delegated_task.id and entry.current_stage_label.endswith("：已转办待确认") for entry in delegate_inbox)
  assert any(
    entry.task_id == delegated_task.id
    and entry.current_handler_label.startswith("代理执行人")
    for entry in creator_tracking
  )

  rejected_task = await task_service.create_task(
    actor=admin,
    title="待退回协商图任务",
    assignee_id=employee.id,
  )
  rejected_task = await task_service.reject_task_assignment(
    actor=employee,
    task_id=rejected_task.id,
    reason="目标和截止时间都需要重谈",
  )

  creator_inbox = (await task_service.list_task_inbox(actor=admin)).items
  employee_inbox = (await task_service.list_task_inbox(actor=employee)).items
  stored_instance = await db_session.scalar(
    select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == rejected_task.id)
  )
  stored_node = await db_session.scalar(
    select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == stored_instance.id)
  )

  assert rejected_task.extra_metadata["workflow_handshake_state"] == "rejected"
  assert rejected_task.extra_metadata["latest_reject_reason"] == "目标和截止时间都需要重谈"
  assert any(entry.task_id == rejected_task.id and entry.current_stage_label.endswith("：已拒绝待调整") for entry in creator_inbox)
  assert all(entry.task_id != rejected_task.id for entry in employee_inbox)
  assert stored_node is not None
  assert stored_node.business_state == WorkflowNodeBusinessState.REJECTED


@pytest.mark.asyncio
async def test_board_service_limits_active_cards_and_archives_expired_cards(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  department_service = DepartmentService(db_session)
  profile_service = ProfileService(db_session)
  parent_department = await department_service.create_department(
    actor=admin,
    name="技术中心",
    code="tech-center",
  )
  team_department = await department_service.create_department(
    actor=admin,
    name="平台研发组",
    code="platform-team",
    parent_id=parent_department.id,
  )
  await profile_service.update_profile(
    actor=admin,
    user_id=admin.id,
    department_id=team_department.id,
  )

  board_service = BoardService(db_session)
  scope_options = await board_service.list_publish_scope_options(actor=admin)
  assert [option.label for option in scope_options] == ["公司", "技术中心", "平台研发组"]

  first_card = await board_service.create_card(
    actor=admin,
    scope_department_id=None,
    title="公司周会提醒",
    content_md="请准时参加周会。",
  )
  second_card = await board_service.create_card(
    actor=admin,
    scope_department_id=team_department.id,
    title="研发排期同步",
    content_md="请更新本周排期。",
  )

  with pytest.raises(ConflictError):
    await board_service.create_card(
      actor=admin,
      scope_department_id=parent_department.id,
      title="第三张卡片",
      content_md="超过上限。",
    )

  stored_first_card = await db_session.get(BoardCard, first_card.id)
  assert stored_first_card is not None
  stored_first_card.expires_at = datetime.now(UTC) - timedelta(minutes=5)
  await db_session.commit()

  archived_count = await board_service.archive_expired_cards()
  active_cards = await board_service.list_active_cards(actor=admin)
  archived_cards = await board_service.list_archives(actor=admin)

  assert second_card.id in {card.id for card in active_cards}
  assert archived_count == 1
  assert len(archived_cards) == 1
  assert archived_cards[0].original_card_id == first_card.id


@pytest.mark.asyncio
async def test_board_service_allows_admin_to_archive_card_manually(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  board_service = BoardService(db_session)
  card = await board_service.create_card(
    actor=admin,
    scope_department_id=None,
    title="人工归档测试",
    content_md="测试管理员手工归档。",
  )

  await board_service.archive_card(actor=admin, card_id=card.id)

  assert await db_session.get(BoardCard, card.id) is None
  archived_cards = await board_service.list_archives(actor=admin)
  assert len(archived_cards) == 1
  assert archived_cards[0].original_card_id == card.id


@pytest.mark.asyncio
async def test_announcement_service_respects_department_capabilities(db_session) -> None:
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
  queue_publisher = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, queue_publisher)
  announcement_service = AnnouncementService(db_session, notification_service)

  capable_department = await department_service.create_department(
    actor=admin,
    name="财务行政部",
    code="finance-admin",
    capabilities=[DepartmentCapability.PUBLISH_ANNOUNCEMENT],
  )
  other_department = await department_service.create_department(
    actor=admin,
    name="技术中心",
    code="tech-center",
  )

  capable_user = await user_service.create_user(
    actor=admin,
    email="notice@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  other_user = await user_service.create_user(
    actor=admin,
    email="engineer@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=capable_user.id,
    employee_no="EMP-001",
    real_name="公告发布人",
    department_id=capable_department.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=other_user.id,
    employee_no="EMP-002",
    real_name="研发工程师",
    department_id=other_department.id,
  )

  announcement = await announcement_service.create_announcement(
    actor=capable_user,
    publisher_department_id=capable_department.id,
    title="办公区维护通知",
    content_md="今晚 9 点进行网络维护。",
  )

  with pytest.raises(AuthorizationError):
    await announcement_service.create_announcement(
      actor=other_user,
      publisher_department_id=other_department.id,
      title="非法公告",
      content_md="不应成功。",
    )

  stored_announcement = await db_session.scalar(select(Announcement).where(Announcement.id == announcement.id))
  assert stored_announcement is not None
  assert len(queue_publisher.payloads) == 2


@pytest.mark.asyncio
async def test_task_service_builds_overview_inbox_and_tracking(db_session) -> None:
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
  notification_service = NotificationService(db_session, InMemoryQueuePublisher())
  task_service = TaskService(db_session, notification_service)

  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  watcher = await user_service.create_user(
    actor=admin,
    email="watcher@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="研发部",
    code="engineering",
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-001",
    real_name="执行人",
    department_id=department.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=watcher.id,
    employee_no="EMP-002",
    real_name="关注人",
    department_id=department.id,
  )

  inbox_task = await task_service.create_task(
    actor=admin,
    title="补齐总览接口",
    assignee_id=employee.id,
    department_id=department.id,
    due_date=datetime.now(UTC) + timedelta(hours=2),
    priority=TaskPriority.URGENT,
  )
  tracking_task = await task_service.create_task(
    actor=admin,
    title="补齐看板归档",
    assignee_id=admin.id,
    department_id=department.id,
    due_date=datetime.now(UTC) + timedelta(days=1),
    priority=TaskPriority.HIGH,
  )
  await task_service.add_task_watchers(
    actor=admin,
    task_id=tracking_task.id,
    watcher_user_ids=[employee.id],
  )

  inbox = (await task_service.list_task_inbox(actor=employee)).items
  tracking = (await task_service.list_task_tracking(actor=employee)).items

  assert [item.task_id for item in inbox] == [inbox_task.id]
  assert tracking[0].task_id == tracking_task.id
  assert "关注" in tracking[0].relation_types


@pytest.mark.asyncio
async def test_step3_task_center_permissions_history_and_memos(db_session) -> None:
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
  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="内容部",
    code="content",
    manager_id=manager.id,
    capabilities=[DepartmentCapability.PUBLISH_ORG_TASK],
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=manager.id,
    employee_no="EMP-MGR-STEP3",
    real_name="内容主管",
    department_id=department.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-EMP-STEP3",
    real_name="内容成员",
    department_id=department.id,
  )

  notification_service = NotificationService(db_session)
  task_service = TaskService(db_session, notification_service)
  task_memo_service = TaskMemoService(db_session, task_service)

  created_task = await task_service.create_task(
    actor=employee,
    title="内容整理",
    assignee_id=employee.id,
    department_id=department.id,
  )
  await task_service.transition_task_status(
    actor=employee,
    task_id=created_task.id,
    target_status=TaskStatus.DOING,
  )
  await task_service.transition_task_status(
    actor=employee,
    task_id=created_task.id,
    target_status=TaskStatus.REVIEW,
  )
  await task_service.transition_task_status(
    actor=employee,
    task_id=created_task.id,
    target_status=TaskStatus.DONE,
  )

  history = (await task_service.list_task_history(actor=employee)).items
  assert history[0].task_id == created_task.id
  assert "执行" in history[0].relation_types

  memo = await task_memo_service.create_memo(
    actor=employee,
    title="  周报备忘  ",
    content="完成后同步到周报。",
    related_task_id=created_task.id,
    is_pinned=True,
  )
  assert memo.title == "周报备忘"

  updated_memo = await task_memo_service.update_memo(
    actor=employee,
    memo_id=memo.id,
    title="",
    content="完成后同步到周报和群公告。",
  )
  memos = await task_memo_service.list_memos(actor=employee)

  assert updated_memo.related_task_id == created_task.id
  assert updated_memo.title is None
  assert memos[0].content == "完成后同步到周报和群公告。"


@pytest.mark.asyncio
async def test_notification_service_skips_web_push_without_subscription(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  notification_service = NotificationService(db_session)
  message = await notification_service.send(
    NotificationMessage(
      source_type="task",
      source_id=admin.id,
      recipient_user_id=admin.id,
      recipient_email=admin.email,
      message_type="task_assigned",
      title="收到新任务",
      body_text="请处理任务。",
      channels=list(DEFAULT_USER_NOTIFICATION_CHANNELS),
    )
  )
  deliveries = list(
    await db_session.scalars(
      select(NotificationDelivery)
      .where(NotificationDelivery.message_id == message.id)
      .order_by(NotificationDelivery.created_at.asc())
    )
  )

  assert {delivery.channel for delivery in deliveries} == {
    NotificationChannel.WEBSOCKET,
    NotificationChannel.EMAIL,
  }


@pytest.mark.asyncio
async def test_task_service_enforces_status_transitions_and_records_logs(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  notification_service = NotificationService(db_session, InMemoryQueuePublisher())
  task_service = TaskService(db_session, notification_service)

  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  admin_profile = await profile_service.get_profile(actor=admin, user_id=admin.id)
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-001",
    real_name="普通员工",
    department_id=admin_profile.department_id,
  )

  task = await task_service.create_task(
    actor=admin,
    title="推进 Phase 2",
    assignee_id=employee.id,
  )

  with pytest.raises(ConflictError):
    await task_service.transition_task_status(
      actor=employee,
      task_id=task.id,
      target_status=TaskStatus.DONE,
    )

  doing_task = await task_service.transition_task_status(
    actor=employee,
    task_id=task.id,
    target_status=TaskStatus.DOING,
  )
  review_task = await task_service.transition_task_status(
    actor=employee,
    task_id=task.id,
    target_status=TaskStatus.REVIEW,
  )
  assert review_task.status == TaskStatus.REVIEW
  done_task = await task_service.transition_task_status(
    actor=employee,
    task_id=task.id,
    target_status=TaskStatus.DONE,
  )
  task_logs = list(
    await db_session.scalars(select(TaskLog).where(TaskLog.task_id == task.id).order_by(TaskLog.created_at.asc()))
  )

  assert doing_task.started_at is not None
  assert done_task.completed_at is not None
  assert [log.action_type for log in task_logs][-3:] == [
    TaskActionType.STATUS_CHANGED,
    TaskActionType.STATUS_CHANGED,
    TaskActionType.STATUS_CHANGED,
  ]


@pytest.mark.asyncio
async def test_task_service_comments_attachments_and_stats(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  admin_profile = await profile_service.get_profile(actor=admin, user_id=admin.id)
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-001",
    real_name="普通员工",
    department_id=admin_profile.department_id,
  )

  with TemporaryDirectory() as tmp_dir:
    storage_service = ObjectStorageService(
      LocalStorageAdapter(base_path=tmp_dir, bucket="filum-test")
    )
    attachment_service = AttachmentService(db_session, storage_service)
    notification_service = NotificationService(db_session, InMemoryQueuePublisher())
    task_service = TaskService(db_session, notification_service, attachment_service)

    overdue_task = await task_service.create_task(
      actor=admin,
      title="补充服务层",
      assignee_id=employee.id,
      due_date=datetime.now(UTC) - timedelta(days=1),
    )

    active_task = await task_service.create_task(
      actor=admin,
      title="整理评论流",
      assignee_id=employee.id,
    )
    active_task = await task_service.transition_task_status(
      actor=employee,
      task_id=active_task.id,
      target_status=TaskStatus.DOING,
    )
    active_task = await task_service.transition_task_status(
      actor=employee,
      task_id=active_task.id,
      target_status=TaskStatus.REVIEW,
    )
    active_task = await task_service.transition_task_status(
      actor=employee,
      task_id=active_task.id,
      target_status=TaskStatus.DONE,
    )

    comment = await task_service.create_task_comment(
      actor=admin,
      task_id=active_task.id,
      content="请补充审计日志。",
      content_format=CommentFormat.MARKDOWN,
      is_internal=True,
      attachments=[
        CommentAttachmentInput(
          filename="review.md",
          content_type="text/markdown",
          content=b"# review",
        )
      ],
    )
    comments_for_admin = await task_service.list_task_comments(actor=admin, task_id=active_task.id)
    comments_for_employee = await task_service.list_task_comments(actor=employee, task_id=active_task.id)
    activity = await task_service.list_task_activity(actor=admin, task_id=active_task.id)
    summary = await task_service.get_task_stats_summary(actor=admin)
    workload = await task_service.get_task_workload(actor=admin)
    comment_logs = list(
      await db_session.scalars(
        select(TaskLog).where(TaskLog.task_id == active_task.id).order_by(TaskLog.created_at.asc())
      )
    )
    comment_attachment_link = await db_session.scalar(
      select(AttachmentLink).where(
        AttachmentLink.target_type == AttachmentTargetType.TASK_COMMENT,
        AttachmentLink.target_id == comment.id,
      )
    )

    assert comment in comments_for_admin
    assert comments_for_employee == []
    assert any(entry.entry_type == "comment" for entry in activity)
    assert any(entry.entry_type == "log" for entry in activity)
    assert comment_attachment_link is not None
    assert any(log.action_type == TaskActionType.COMMENTED for log in comment_logs)
    assert any(log.action_type == TaskActionType.ATTACHMENT_ADDED for log in comment_logs)
    assert summary.total_tasks == 2
    assert summary.completed_tasks == 1
    assert summary.overdue_tasks == 1
    assert summary.tasks_by_status[TaskStatus.DONE] == 1
    assert len(workload) == 1
    assert workload[0].assignee_id == employee.id
    assert workload[0].total_tasks == 2
    assert workload[0].completed_tasks == 1
    assert workload[0].overdue_tasks == 1

    with pytest.raises(AuthorizationError):
      await task_service.create_task_comment(
        actor=employee,
        task_id=active_task.id,
        content="这是内部备注",
        is_internal=True,
      )


@pytest.mark.asyncio
async def test_phase3_services_filter_fields_for_manager_and_delegate(db_session) -> None:
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
  delegation_service = DelegationService(db_session)

  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  delegate = await user_service.create_user(
    actor=admin,
    email="delegate@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  department = await department_service.create_department(
    actor=admin,
    name="运营部",
    code="operations",
    manager_id=manager.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=manager.id,
    employee_no="EMP-MANAGER-001",
    real_name="直属主管",
    department_id=department.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-001",
    real_name="普通员工",
    department_id=department.id,
  )

  position = await organization_relation_service.create_position(
    actor=admin,
    code="ops-specialist",
    name="运营专员",
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
  await organization_relation_service.create_reporting_line(
    actor=admin,
    user_id=employee.id,
    manager_user_id=manager.id,
    department_id=department.id,
    line_type=ReportingLineType.SOLID,
    is_primary=True,
    starts_at=date(2025, 1, 1),
  )

  await profile_service.update_profile(
    actor=admin,
    user_id=employee.id,
    custom_fields={
      "salary": 32000,
      "performance": "A",
      "hobby": "摄影",
    },
  )

  await delegation_service.create_delegation(
    actor=manager,
    delegator_user_id=manager.id,
    delegate_user_id=delegate.id,
    scope_type=DelegationScopeType.DATA_ACCESS,
    starts_at=datetime.now(UTC) - timedelta(hours=1),
    ends_at=datetime.now(UTC) + timedelta(days=7),
  )

  employee_view = await profile_service.get_profile_view(actor=employee, user_id=employee.id)
  manager_view = await profile_service.get_profile_view(actor=manager, user_id=employee.id)
  delegate_view = await profile_service.get_profile_view(actor=delegate, user_id=employee.id)

  assert employee_view["employee_no"] == "EMP-001"
  assert "hobby" in employee_view["custom_fields"]
  assert "salary" not in employee_view["custom_fields"]
  assert "performance" not in employee_view["custom_fields"]

  assert manager_view["custom_fields"]["performance"] == "A"
  assert "salary" not in manager_view["custom_fields"]
  assert any(
    field["field_key"] == "performance" and field["can_edit"] is True
    for field in manager_view["visible_fields"]
  )

  assert delegate_view["custom_fields"]["performance"] == "A"
  assert "salary" not in delegate_view["custom_fields"]


@pytest.mark.asyncio
async def test_phase3_services_apply_lifecycle_events(db_session) -> None:
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
  lifecycle_service = HRLifecycleService(db_session)

  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  department = await department_service.create_department(
    actor=admin,
    name="产品部",
    code="product",
    manager_id=manager.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-PRODUCT-001",
    real_name="产品同学",
    department_id=department.id,
  )

  specialist_position = await organization_relation_service.create_position(
    actor=admin,
    code="product-specialist",
    name="产品专员",
  )
  lead_position = await organization_relation_service.create_position(
    actor=admin,
    code="product-lead",
    name="产品负责人",
  )

  promotion_event = await lifecycle_service.create_event(
    actor=admin,
    user_id=employee.id,
    event_type=EmploymentEventType.PROMOTION,
    effective_date=date(2025, 2, 1),
    title="晋升产品负责人",
    payload={
      "position_id": str(lead_position.id),
      "department_id": str(department.id),
      "manager_user_id": str(manager.id),
      "job_title": "产品负责人",
      "assignment_type": PositionAssignmentType.PRIMARY.value,
      "is_primary": True,
    },
  )

  offboard_event = await lifecycle_service.create_event(
    actor=admin,
    user_id=employee.id,
    event_type=EmploymentEventType.OFFBOARD,
    effective_date=date(2025, 3, 1),
    title="办理离职",
    payload={},
  )

  rehire_event = await lifecycle_service.create_event(
    actor=admin,
    user_id=employee.id,
    event_type=EmploymentEventType.REHIRE,
    effective_date=date(2025, 4, 1),
    title="返聘为产品专员",
    payload={
      "position_id": str(specialist_position.id),
      "department_id": str(department.id),
      "assignment_type": PositionAssignmentType.PRIMARY.value,
      "is_primary": True,
    },
  )

  updated_profile = await profile_service.get_profile(actor=admin, user_id=employee.id)
  positions = await organization_relation_service.list_profile_positions(user_id=employee.id)
  events = await lifecycle_service.list_events(user_id=employee.id)
  employee_row = await db_session.get(type(employee), employee.id)

  assert promotion_event.event_type == EmploymentEventType.PROMOTION
  assert offboard_event.event_type == EmploymentEventType.OFFBOARD
  assert rehire_event.event_type == EmploymentEventType.REHIRE
  assert updated_profile.job_title == "产品专员"
  assert employee_row is not None
  assert employee_row.status == UserStatus.ACTIVE
  assert len(events) == 3
  assert any(position.position_id == lead_position.id for position in positions)
  assert any(position.position_id == specialist_position.id and position.is_primary for position in positions)


@pytest.mark.asyncio
async def test_phase3_lifecycle_event_automation_enqueues_and_runs_idempotently(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  queue_publisher = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, queue_publisher)
  workflow_engine_service = WorkflowEngineService(db_session, notification_service)
  lifecycle_service = HRLifecycleService(
    db_session,
    workflow_engine_service=workflow_engine_service,
    job_queue_publisher=queue_publisher,
  )

  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  admin_profile = await profile_service.get_profile(actor=admin, user_id=admin.id)
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-LIFECYCLE-001",
    real_name="新员工",
    department_id=admin_profile.department_id,
  )

  definition = await workflow_engine_service.create_definition(
    actor=admin,
    code="lifecycle-onboard-approval",
    name="入职审批",
    scope_type="employment_event",
    status=WorkflowDefinitionStatus.ACTIVE,
    steps=[
      {
        "step_key": "approve",
        "name": "确认入职",
        "step_type": "approval",
        "assignee_rule": {"type": "user", "user_id": str(admin.id)},
      }
    ],
  )

  event = await lifecycle_service.create_event(
    actor=admin,
    user_id=employee.id,
    event_type=EmploymentEventType.ONBOARD,
    effective_date=date(2025, 5, 1),
    title="办理入职",
    payload={"department_id": str(admin_profile.department_id)},
    workflow_definition_id=definition.id,
  )

  assert event.trigger_status.value == "pending"
  assert queue_publisher.jobs == [(PROCESS_EMPLOYMENT_EVENT_JOB, (str(event.id),))]

  processed_event = await lifecycle_service.process_event_automation(event_id=event.id)
  processed_again = await lifecycle_service.process_event_automation(event_id=event.id)

  workflow_instance_count = await db_session.scalar(
    select(func.count()).select_from(WorkflowInstance).where(WorkflowInstance.definition_id == definition.id)
  )

  assert processed_event.trigger_status.value == "succeeded"
  assert processed_event.triggered_workflow_instance_id is not None
  assert processed_again.trigger_status.value == "succeeded"
  assert workflow_instance_count == 1


@pytest.mark.asyncio
async def test_message_center_snapshot_is_user_scoped_and_tracks_source_metadata(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  watcher = await user_service.create_user(
    actor=admin,
    email="watcher@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  notification_service = NotificationService(db_session, InMemoryQueuePublisher())
  message_center_service = MessageCenterService(db_session)
  task_id = uuid4()
  report_id = uuid4()

  await notification_service.send(
    NotificationMessage(
      source_type="task",
      source_id=task_id,
      recipient_user_id=manager.id,
      recipient_email=manager.email,
      message_type="task_assigned",
      title="收到新任务：季度复盘",
      body_text="任务「季度复盘」已分配给你，请及时处理。",
      channels=list(DEFAULT_USER_NOTIFICATION_CHANNELS),
      payload=build_task_source_payload(task_id=task_id, task_title="季度复盘"),
    )
  )
  await notification_service.send(
    NotificationMessage(
      source_type="report",
      source_id=report_id,
      recipient_user_id=watcher.id,
      recipient_email=watcher.email,
      message_type="report_pending",
      title="新的向上汇报：预算申请",
      body_text="请处理「预算申请」。",
      channels=list(DEFAULT_USER_NOTIFICATION_CHANNELS),
    )
  )

  snapshot = await message_center_service.get_message_center_snapshot(actor=manager, state="unread")

  assert snapshot.total_count == 1
  assert snapshot.filtered_count == 1
  assert snapshot.unread_count == 1
  assert snapshot.items[0]["source"]["module_key"] == "task"
  assert snapshot.items[0]["source"]["module_label"] == "任务中心"
  assert snapshot.items[0]["source"]["target"]["route_name"] == "task-center"
  assert snapshot.items[0]["source"]["target"]["route_query"]["selected"] == str(task_id)
  assert snapshot.items[0]["receipt_state"]["is_read"] is False
  assert snapshot.source_counts == [
    {
      "source_type": "task",
      "label": "任务中心",
      "count": 1,
    }
  ]

  acknowledged_receipt = await message_center_service.create_receipt(
    actor=manager,
    message_id=snapshot.items[0]["id"],
    receipt_type=NotificationReceiptType.ACKNOWLEDGED,
  )
  acknowledged_snapshot = await message_center_service.get_message_center_snapshot(
    actor=manager,
    state="acknowledged",
  )

  assert acknowledged_receipt.receipt_type == NotificationReceiptType.ACKNOWLEDGED
  assert acknowledged_snapshot.filtered_count == 1
  assert acknowledged_snapshot.unread_count == 0
  assert acknowledged_snapshot.items[0]["receipt_state"]["is_acknowledged"] is True
  assert all(message.recipient_user_id == watcher.id for message in await message_center_service.list_messages(actor=watcher))

  with pytest.raises(NotFoundError):
    await message_center_service.get_message_view(actor=watcher, message_id=snapshot.items[0]["id"])


@pytest.mark.asyncio
async def test_message_center_snapshot_supports_delivery_filters_and_message_attachments(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  notification_service = NotificationService(db_session, InMemoryQueuePublisher())
  message_center_service = MessageCenterService(db_session)

  first_message = await notification_service.send(
    NotificationMessage(
      source_type="task",
      source_id=uuid4(),
      recipient_user_id=manager.id,
      recipient_email=manager.email,
      message_type="task_assigned",
      title="收到新任务：季度复盘",
      body_text="任务「季度复盘」已分配给你，请及时处理。",
      channels=[NotificationChannel.EMAIL, NotificationChannel.WEB_PUSH],
      payload={},
    )
  )
  second_message = await notification_service.send(
    NotificationMessage(
      source_type="report",
      source_id=uuid4(),
      recipient_user_id=manager.id,
      recipient_email=manager.email,
      message_type="report_pending",
      title="新的汇报：预算申请",
      body_text="请处理预算申请。",
      channels=[NotificationChannel.WEBSOCKET],
      payload={},
    )
  )

  attachment = Attachment(
    storage_provider="local",
    bucket="filum-test",
    object_key="messages/message-attachment.txt",
    original_filename="消息附件.txt",
    mime_type="text/plain",
    size_bytes=12,
    checksum_sha256="abc123",
    uploader_id=admin.id,
  )
  db_session.add(attachment)
  await db_session.flush()
  db_session.add(
    AttachmentLink(
      attachment_id=attachment.id,
      target_type=AttachmentTargetType.NOTIFICATION_MESSAGE,
      target_id=first_message.id,
      relation="primary",
      created_by=admin.id,
    )
  )

  first_message.created_at = datetime.now(UTC) - timedelta(days=2)
  first_message.status = NotificationMessageStatus.FAILED
  second_message.status = NotificationMessageStatus.COMPLETED
  for delivery in first_message.deliveries:
    delivery.attempt_count = 2
    delivery.attempted_at = datetime.now(UTC) - timedelta(days=1)
    if delivery.channel == NotificationChannel.EMAIL:
      delivery.status = NotificationDeliveryStatus.FAILED
      delivery.error_message = "邮箱通道不可用。"
    else:
      delivery.status = NotificationDeliveryStatus.SENT
      delivery.delivered_at = datetime.now(UTC) - timedelta(days=1)
  for delivery in second_message.deliveries:
    delivery.status = NotificationDeliveryStatus.SENT
    delivery.delivered_at = datetime.now(UTC)
  await db_session.commit()

  snapshot = await message_center_service.get_message_center_snapshot(
    actor=manager,
    channel=NotificationChannel.EMAIL,
    delivery_status=NotificationDeliveryStatus.FAILED,
    created_to=datetime.now(UTC) - timedelta(days=1),
  )
  message_view = await message_center_service.get_message_view(actor=manager, message_id=first_message.id)

  assert snapshot.total_count == 2
  assert snapshot.filtered_count == 1
  assert snapshot.applied_channel == NotificationChannel.EMAIL
  assert snapshot.applied_delivery_status == NotificationDeliveryStatus.FAILED
  assert snapshot.items[0]["id"] == first_message.id
  assert snapshot.items[0]["delivery_state"] == NotificationDeliveryStatus.FAILED
  assert len(message_view["attachments"]) == 1
  assert message_view["attachments"][0].original_filename == "消息附件.txt"
  assert message_view["delivery_state"] == NotificationDeliveryStatus.FAILED


@LEGACY_E_REMOVED
@pytest.mark.asyncio
async def test_phase4_template_automation_and_message_center_services(db_session) -> None:
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
  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.HR,
  )
  requester = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  watcher = await user_service.create_user(
    actor=admin,
    email="watcher@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="流程部",
    code="workflow-dept",
    manager_id=manager.id,
    capabilities=[DepartmentCapability.PUBLISH_ORG_TASK],
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=manager.id,
    employee_no="EMP-MGR-001",
    real_name="部门负责人",
    department_id=department.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=requester.id,
    employee_no="EMP-REQ-001",
    real_name="申请员工",
    department_id=department.id,
  )

  notification_queue = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, notification_queue)
  task_service = TaskService(db_session, notification_service)
  task_template_service = TaskTemplateService(db_session, task_service, notification_service)
  task_automation_service = TaskAutomationService(db_session, task_template_service)
  message_center_service = MessageCenterService(db_session)

  template = await task_template_service.create_template(
    actor=admin,
    code="onboard-sop",
    name="入职 SOP",
    category="hr",
    steps=[
      {
        "step_key": "prepare",
        "title": "提交资料",
        "default_assignee_rule": {"type": "initiator"},
      },
      {
        "step_key": "review",
        "title": "经理复核",
        "default_assignee_rule": {"type": "department_manager"},
        "depends_on_step_keys": ["prepare"],
      },
    ],
  )

  instantiation = await task_template_service.instantiate_template(
    actor=requester,
    template_id=template.id,
    watcher_user_ids=[watcher.id],
    payload={"department_id": str(department.id)},
  )
  tasks = instantiation.tasks
  instances = list(await db_session.scalars(select(TaskTemplateInstance)))
  step_runs = list(await db_session.scalars(select(TaskTemplateStepRun)))
  watchers = await task_service.list_task_watchers(actor=admin, task_id=tasks[0].id)
  watcher_messages = await message_center_service.list_messages(actor=watcher)
  read_receipt = await message_center_service.create_receipt(
    actor=watcher,
    message_id=watcher_messages[0].id,
    receipt_type=NotificationReceiptType.READ,
  )
  idempotent_receipt = await message_center_service.create_receipt(
    actor=watcher,
    message_id=watcher_messages[0].id,
    receipt_type=NotificationReceiptType.READ,
  )

  schedule = await task_automation_service.create_schedule(
    actor=admin,
    template_id=template.id,
    cron_expr="*/5 * * * *",
    payload={"department_id": str(department.id)},
  )
  schedule.next_run_at = datetime.now(UTC) - timedelta(minutes=1)
  await db_session.commit()
  executed_count = await task_automation_service.run_due_schedules(now=datetime.now(UTC))
  all_tasks = await task_service.list_tasks(actor=admin)
  refreshed_schedule = await task_automation_service.list_schedules(actor=admin)

  assert len(tasks) == 1
  assert tasks[0].source_type.value == "template"
  assert tasks[0].extra_metadata["template_step_key"] == "prepare"
  assert len(instances) == 1
  assert len(step_runs) == 1
  assert [watcher_binding.user_id for watcher_binding in watchers] == [watcher.id]
  assert len([message for message in watcher_messages if message.message_type == "task_cc_added"]) == 1
  assert read_receipt.id == idempotent_receipt.id
  assert executed_count == 1
  assert len(all_tasks) == 2
  assert schedule.next_run_at is not None
  assert refreshed_schedule[0].last_run_status == "success"
  assert refreshed_schedule[0].last_run_task_count == 1
  assert refreshed_schedule[0].last_run_message is not None


@LEGACY_E_REMOVED
@pytest.mark.asyncio
async def test_task_template_dependencies_block_downstream_status_transition(db_session) -> None:
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

  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  requester = await user_service.create_user(
    actor=admin,
    email="requester@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="视频部",
    code="video-dept",
    manager_id=manager.id,
    capabilities=[DepartmentCapability.PUBLISH_ORG_TASK],
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=manager.id,
    employee_no="EMP-MGR-001",
    real_name="视频主管",
    department_id=department.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=requester.id,
    employee_no="EMP-REQ-001",
    real_name="视频发起人",
    department_id=department.id,
  )

  notification_service = NotificationService(db_session, InMemoryQueuePublisher())
  task_service = TaskService(db_session, notification_service)
  task_template_service = TaskTemplateService(db_session, task_service, notification_service)

  template = await task_template_service.create_template(
    actor=admin,
    code="video-production",
    name="视频制作",
    category="media",
    steps=[
      {
        "step_key": "topic_meeting",
        "title": "召开选题会",
        "default_assignee_rule": {"type": "initiator"},
      },
      {
        "step_key": "manager_review",
        "title": "主管确认选题",
        "default_assignee_rule": {"type": "department_manager"},
        "depends_on_step_keys": ["topic_meeting"],
      },
    ],
  )

  instantiation = await task_template_service.instantiate_template(
    actor=requester,
    template_id=template.id,
    payload={"department_id": str(department.id)},
  )
  tasks = instantiation.tasks
  assert len(tasks) == 1
  upstream_task = tasks[0]

  await task_service.transition_task_status(
    actor=requester,
    task_id=upstream_task.id,
    target_status=TaskStatus.DOING,
  )
  await task_service.transition_task_status(
    actor=requester,
    task_id=upstream_task.id,
    target_status=TaskStatus.REVIEW,
  )
  await task_service.transition_task_status(
    actor=requester,
    task_id=upstream_task.id,
    target_status=TaskStatus.DONE,
  )

  all_tasks = await task_service.list_tasks(actor=admin)
  downstream_task = next(
    task for task in all_tasks if task.extra_metadata.get("template_step_key") == "manager_review"
  )

  activated_task = await task_service.transition_task_status(
    actor=manager,
    task_id=downstream_task.id,
    target_status=TaskStatus.DOING,
  )

  assert activated_task.status == TaskStatus.DOING


@LEGACY_E_REMOVED
@pytest.mark.asyncio
async def test_task_template_delete_only_allows_templates_without_instances(db_session) -> None:
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

  requester = await user_service.create_user(
    actor=admin,
    email="requester@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="模板部",
    code="template-dept",
    capabilities=[DepartmentCapability.PUBLISH_ORG_TASK],
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=requester.id,
    employee_no="EMP-TPL-001",
    real_name="模板发起人",
    department_id=department.id,
  )

  notification_service = NotificationService(db_session, InMemoryQueuePublisher())
  task_service = TaskService(db_session, notification_service)
  task_template_service = TaskTemplateService(db_session, task_service, notification_service)

  deletable_template = await task_template_service.create_template(
    actor=admin,
    code="deletable-template",
    name="可删除模板",
    category="ops",
    steps=[
      {
        "step_key": "draft",
        "title": "整理草稿",
        "default_assignee_rule": {"type": "initiator"},
      }
    ],
  )

  protected_template = await task_template_service.create_template(
    actor=admin,
    code="protected-template",
    name="已使用模板",
    category="ops",
    steps=[
      {
        "step_key": "draft",
        "title": "整理草稿",
        "default_assignee_rule": {"type": "initiator"},
      }
    ],
  )
  await task_template_service.instantiate_template(
    actor=requester,
    template_id=protected_template.id,
    payload={"department_id": str(department.id)},
  )

  await task_template_service.delete_template(actor=admin, template_id=deletable_template.id)

  assert await db_session.get(TaskTemplate, deletable_template.id) is None

  with pytest.raises(ConflictError, match="已有实例运行记录"):
    await task_template_service.delete_template(actor=admin, template_id=protected_template.id)


@LEGACY_E_REMOVED
@pytest.mark.asyncio
async def test_task_template_update_preserves_metadata_but_blocks_step_changes_after_instantiation(db_session) -> None:
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

  requester = await user_service.create_user(
    actor=admin,
    email="requester@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="流程模板部",
    code="workflow-template-dept",
    capabilities=[DepartmentCapability.PUBLISH_ORG_TASK],
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=requester.id,
    employee_no="EMP-TPL-UPD-001",
    real_name="模板执行人",
    department_id=department.id,
  )

  notification_service = NotificationService(db_session, InMemoryQueuePublisher())
  task_service = TaskService(db_session, notification_service)
  task_template_service = TaskTemplateService(db_session, task_service, notification_service)

  template = await task_template_service.create_template(
    actor=admin,
    code="template-update-guard",
    name="模板更新保护",
    category="ops",
    description="旧说明",
    steps=[
      {
        "step_key": "draft",
        "title": "整理草稿",
        "default_assignee_rule": {"type": "initiator"},
      },
      {
        "step_key": "review",
        "title": "主管复核",
        "default_assignee_rule": {"type": "department_manager"},
        "depends_on_step_keys": ["draft"],
      },
    ],
  )
  await task_template_service.instantiate_template(
    actor=requester,
    template_id=template.id,
    payload={"department_id": str(department.id)},
  )

  metadata_updated = await task_template_service.update_template(
    actor=admin,
    template_id=template.id,
    name="模板更新保护 v2",
    description="新说明",
    steps=[
      {
        "step_key": "draft",
        "title": "整理草稿",
        "description": None,
        "step_type": "task",
        "assignment_mode": "single",
        "join_mode": "all",
        "default_assignee_rule": {"type": "initiator"},
        "default_due_offset_hours": None,
        "sort_order": 1,
        "config": {},
        "depends_on_step_keys": [],
      },
      {
        "step_key": "review",
        "title": "主管复核",
        "description": None,
        "step_type": "task",
        "assignment_mode": "single",
        "join_mode": "all",
        "default_assignee_rule": {"type": "department_manager"},
        "default_due_offset_hours": None,
        "sort_order": 2,
        "config": {},
        "depends_on_step_keys": ["draft"],
      },
    ],
  )
  assert metadata_updated.name == "模板更新保护 v2"
  assert metadata_updated.description == "新说明"

  with pytest.raises(ConflictError, match="暂不支持修改步骤结构"):
    await task_template_service.update_template(
      actor=admin,
      template_id=template.id,
      steps=[
        {
          "step_key": "draft",
          "title": "整理基础资料",
          "description": None,
          "step_type": "task",
          "assignment_mode": "single",
          "join_mode": "all",
          "default_assignee_rule": {"type": "initiator"},
          "default_due_offset_hours": None,
          "sort_order": 1,
          "config": {},
          "depends_on_step_keys": [],
        },
        {
          "step_key": "review",
          "title": "主管复核",
          "description": None,
          "step_type": "task",
          "assignment_mode": "single",
          "join_mode": "all",
          "default_assignee_rule": {"type": "department_manager"},
          "default_due_offset_hours": None,
          "sort_order": 2,
          "config": {},
          "depends_on_step_keys": ["draft"],
        },
      ],
    )


@LEGACY_E_REMOVED
@pytest.mark.asyncio
async def test_task_template_can_create_new_version_from_locked_template(db_session) -> None:
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

  requester = await user_service.create_user(
    actor=admin,
    email="requester@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="版本模板部",
    code="version-template-dept",
    capabilities=[DepartmentCapability.PUBLISH_ORG_TASK],
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=requester.id,
    employee_no="EMP-TPL-V2-001",
    real_name="模板版本执行人",
    department_id=department.id,
  )

  notification_service = NotificationService(db_session, InMemoryQueuePublisher())
  task_service = TaskService(db_session, notification_service)
  task_template_service = TaskTemplateService(db_session, task_service, notification_service)

  template = await task_template_service.create_template(
    actor=admin,
    code="stage2-template",
    name="Stage 2 模板",
    category="ops",
    steps=[
      {
        "step_key": "draft",
        "title": "整理草稿",
        "default_assignee_rule": {"type": "initiator"},
      }
    ],
  )
  await task_template_service.instantiate_template(
    actor=requester,
    template_id=template.id,
    payload={"department_id": str(department.id)},
  )

  version_two = await task_template_service.create_template(
    actor=admin,
    code="stage2-template-v2",
    source_template_id=template.id,
    name="Stage 2 模板 V2",
    category="ops",
    steps=[
      {
        "step_key": "draft",
        "title": "整理草稿",
        "default_assignee_rule": {"type": "initiator"},
      },
      {
        "step_key": "review",
        "title": "主管复核",
        "default_assignee_rule": {"type": "initiator"},
        "depends_on_step_keys": ["draft"],
      },
    ],
  )
  metadata = await task_template_service.get_template_view_metadata(template_ids=[template.id, version_two.id])

  assert template.base_code == "stage2-template"
  assert template.version == 1
  assert version_two.base_code == "stage2-template"
  assert version_two.version == 2
  assert version_two.source_template_id == template.id
  assert metadata[template.id].has_instances is True
  assert metadata[template.id].latest_version == 2
  assert metadata[version_two.id].latest_version == 2


@LEGACY_E_REMOVED
@pytest.mark.asyncio
async def test_task_template_fan_out_join_modes_activate_downstream(db_session) -> None:
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

  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  requester = await user_service.create_user(
    actor=admin,
    email="requester@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  editor_a = await user_service.create_user(
    actor=admin,
    email="editor-a@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  editor_b = await user_service.create_user(
    actor=admin,
    email="editor-b@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="视频部",
    code="video-team",
    manager_id=manager.id,
    capabilities=[DepartmentCapability.PUBLISH_ORG_TASK],
  )
  for user_id, employee_no, real_name in [
    (manager.id, "EMP-MGR-ALL", "视频主管"),
    (requester.id, "EMP-REQ-ALL", "视频发起人"),
    (editor_a.id, "EMP-EDA-ALL", "剪辑 A"),
    (editor_b.id, "EMP-EDB-ALL", "剪辑 B"),
  ]:
    await profile_service.create_profile(
      actor=admin,
      user_id=user_id,
      employee_no=employee_no,
      real_name=real_name,
      department_id=department.id,
    )

  notification_service = NotificationService(db_session, InMemoryQueuePublisher())
  task_service = TaskService(db_session, notification_service)
  task_template_service = TaskTemplateService(db_session, task_service, notification_service)

  all_template = await task_template_service.create_template(
    actor=admin,
    code="video-all-join",
    name="视频素材会签",
    category="media",
    steps=[
      {
        "step_key": "kickoff",
        "title": "发起制作",
        "default_assignee_rule": {"type": "initiator"},
      },
      {
        "step_key": "collect_assets",
        "title": "多人提交素材",
        "assignment_mode": "fan_out",
        "join_mode": "all",
        "default_assignee_rule": {
          "type": "user_ids",
          "user_ids": [str(editor_a.id), str(editor_b.id)],
        },
        "depends_on_step_keys": ["kickoff"],
      },
      {
        "step_key": "manager_review",
        "title": "主管确认素材",
        "default_assignee_rule": {"type": "department_manager"},
        "depends_on_step_keys": ["collect_assets"],
      },
    ],
  )

  all_instantiation = await task_template_service.instantiate_template(
    actor=requester,
    template_id=all_template.id,
    payload={"department_id": str(department.id)},
  )
  initial_tasks = all_instantiation.tasks
  kickoff_task = initial_tasks[0]
  for target_status in [TaskStatus.DOING, TaskStatus.REVIEW, TaskStatus.DONE]:
    await task_service.transition_task_status(
      actor=requester,
      task_id=kickoff_task.id,
      target_status=target_status,
    )

  after_kickoff_tasks = await task_service.list_tasks(actor=admin)
  fan_out_tasks = [
    task
    for task in after_kickoff_tasks
    if task.extra_metadata.get("template_step_key") == "collect_assets"
    and task.extra_metadata.get("template_id") == str(all_template.id)
  ]
  assert len(fan_out_tasks) == 2

  first_fan_out_task = next(task for task in fan_out_tasks if task.assignee_id == editor_a.id)
  for target_status in [TaskStatus.DOING, TaskStatus.REVIEW, TaskStatus.DONE]:
    await task_service.transition_task_status(
      actor=editor_a,
      task_id=first_fan_out_task.id,
      target_status=target_status,
    )

  tasks_after_first_completion = await task_service.list_tasks(actor=admin)
  assert not any(
    task.extra_metadata.get("template_step_key") == "manager_review"
    and task.extra_metadata.get("template_id") == str(all_template.id)
    for task in tasks_after_first_completion
  )

  second_fan_out_task = next(task for task in fan_out_tasks if task.assignee_id == editor_b.id)
  for target_status in [TaskStatus.DOING, TaskStatus.REVIEW, TaskStatus.DONE]:
    await task_service.transition_task_status(
      actor=editor_b,
      task_id=second_fan_out_task.id,
      target_status=target_status,
    )

  tasks_after_all_completion = await task_service.list_tasks(actor=admin)
  assert any(
    task.extra_metadata.get("template_step_key") == "manager_review"
    and task.extra_metadata.get("template_id") == str(all_template.id)
    for task in tasks_after_all_completion
  )
  manager_review_tasks = [
    task
    for task in tasks_after_all_completion
    if task.extra_metadata.get("template_step_key") == "manager_review"
    and task.extra_metadata.get("template_id") == str(all_template.id)
  ]
  assert len(manager_review_tasks) == 1

  repeated_activation_tasks = await task_service.activate_template_instance_steps(
    instance_id=all_instantiation.instance.id,
  )
  tasks_after_repeated_activation = await task_service.list_tasks(actor=admin)
  repeated_manager_review_tasks = [
    task
    for task in tasks_after_repeated_activation
    if task.extra_metadata.get("template_step_key") == "manager_review"
    and task.extra_metadata.get("template_id") == str(all_template.id)
  ]
  assert repeated_activation_tasks == []
  assert len(repeated_manager_review_tasks) == 1

  any_template = await task_template_service.create_template(
    actor=admin,
    code="video-any-join",
    name="视频素材或签",
    category="media",
    steps=[
      {
        "step_key": "kickoff",
        "title": "发起制作",
        "default_assignee_rule": {"type": "initiator"},
      },
      {
        "step_key": "collect_assets",
        "title": "任一人先提交素材",
        "assignment_mode": "fan_out",
        "join_mode": "any",
        "default_assignee_rule": {
          "type": "user_ids",
          "user_ids": [str(editor_a.id), str(editor_b.id)],
        },
        "depends_on_step_keys": ["kickoff"],
      },
      {
        "step_key": "manager_review",
        "title": "主管确认素材",
        "default_assignee_rule": {"type": "department_manager"},
        "depends_on_step_keys": ["collect_assets"],
      },
    ],
  )

  any_instantiation = await task_template_service.instantiate_template(
    actor=requester,
    template_id=any_template.id,
    payload={"department_id": str(department.id)},
  )
  any_initial_tasks = any_instantiation.tasks
  any_kickoff_task = any_initial_tasks[0]
  for target_status in [TaskStatus.DOING, TaskStatus.REVIEW, TaskStatus.DONE]:
    await task_service.transition_task_status(
      actor=requester,
      task_id=any_kickoff_task.id,
      target_status=target_status,
    )

  any_fan_out_tasks = [
    task
    for task in await task_service.list_tasks(actor=admin)
    if task.extra_metadata.get("template_step_key") == "collect_assets"
    and task.extra_metadata.get("template_id") == str(any_template.id)
  ]
  assert len(any_fan_out_tasks) == 2

  first_any_task = next(task for task in any_fan_out_tasks if task.assignee_id == editor_a.id)
  for target_status in [TaskStatus.DOING, TaskStatus.REVIEW, TaskStatus.DONE]:
    await task_service.transition_task_status(
      actor=editor_a,
      task_id=first_any_task.id,
      target_status=target_status,
    )

  tasks_after_any_completion = await task_service.list_tasks(actor=admin)
  assert any(
    task.extra_metadata.get("template_step_key") == "manager_review"
    and task.extra_metadata.get("template_id") == str(any_template.id)
    for task in tasks_after_any_completion
  )


@pytest.mark.asyncio
async def test_phase4_workflow_engine_supports_delegation_and_return_flow(db_session) -> None:
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
  delegation_service = DelegationService(db_session)
  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.HR,
  )
  delegate = await user_service.create_user(
    actor=admin,
    email="delegate@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  requester = await user_service.create_user(
    actor=admin,
    email="requester@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="审批部",
    code="approval-dept",
    manager_id=manager.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=manager.id,
    employee_no="EMP-MGR-002",
    real_name="审批经理",
    department_id=department.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=requester.id,
    employee_no="EMP-REQ-002",
    real_name="申请人",
    department_id=department.id,
  )

  await delegation_service.create_delegation(
    actor=manager,
    delegator_user_id=manager.id,
    delegate_user_id=delegate.id,
    scope_type=DelegationScopeType.APPROVAL,
    scope_department_id=department.id,
    starts_at=datetime.now(UTC) - timedelta(hours=1),
    ends_at=datetime.now(UTC) + timedelta(days=2),
  )

  notification_queue = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, notification_queue)
  workflow_engine_service = WorkflowEngineService(db_session, notification_service)

  definition = await workflow_engine_service.create_definition(
    actor=admin,
    code="leave-approval",
    name="请假审批",
    scope_type="leave_request",
    status=WorkflowDefinitionStatus.ACTIVE,
    steps=[
      {
        "step_key": "draft",
        "name": "申请提交",
        "step_type": "task",
        "assignee_rule": {"type": "initiator"},
      },
      {
        "step_key": "approve",
        "name": "经理审批",
        "step_type": "approval",
        "assignee_rule": {"type": "department_manager"},
        "reject_target_step_key": "draft",
      },
    ],
  )

  instance = await workflow_engine_service.start_workflow(
    actor=requester,
    definition_id=definition.id,
    source_type="leave_request",
    payload={"department_id": str(department.id)},
  )
  draft_step_run = next(
    step_run
    for step_run in instance.step_runs
    if step_run.step is not None and step_run.step.step_key == "draft" and step_run.status.value == "pending"
  )
  instance = await workflow_engine_service.act_step_run(
    actor=requester,
    step_run_id=draft_step_run.id,
    action="approve",
  )
  delegated_step_run = next(
    step_run
    for step_run in instance.step_runs
    if step_run.step is not None and step_run.step.step_key == "approve" and step_run.status.value == "pending"
  )
  assert delegated_step_run.assignee_user_id == delegate.id
  assert delegated_step_run.delegated_from_user_id == manager.id

  returned_instance = await workflow_engine_service.act_step_run(
    actor=delegate,
    step_run_id=delegated_step_run.id,
    action="return",
    comment="补充说明",
  )
  returned_draft_step_run = next(
    step_run
    for step_run in returned_instance.step_runs
    if (
      step_run.step is not None
      and step_run.step.step_key == "draft"
      and step_run.status.value == "pending"
      and step_run.payload.get("iteration") == 2
    )
  )
  assert returned_instance.status == WorkflowInstanceStatus.RETURNED

  resubmitted_instance = await workflow_engine_service.act_step_run(
    actor=requester,
    step_run_id=returned_draft_step_run.id,
    action="approve",
  )
  delegated_step_run = next(
    step_run
    for step_run in resubmitted_instance.step_runs
    if (
      step_run.step is not None
      and step_run.step.step_key == "approve"
      and step_run.status.value == "pending"
      and step_run.payload.get("iteration") == 2
    )
  )
  completed_instance = await workflow_engine_service.act_step_run(
    actor=delegate,
    step_run_id=delegated_step_run.id,
    action="approve",
  )

  assert completed_instance.status == WorkflowInstanceStatus.APPROVED
  assert any(payload["message_type"] == "workflow_action_required" for payload in notification_queue.payloads)
  assert any(payload["message_type"] == "workflow_returned" for payload in notification_queue.payloads)


@pytest.mark.asyncio
async def test_step4_report_center_supports_routing_delegation_and_archive(db_session) -> None:
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
  delegation_service = DelegationService(db_session)

  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  delegate = await user_service.create_user(
    actor=admin,
    email="delegate@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  requester = await user_service.create_user(
    actor=admin,
    email="requester@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="汇报测试部",
    code="reporting-test",
    manager_id=admin.id,
  )
  for user, employee_no, real_name in [
    (manager, "EMP-RPT-002", "中层经理"),
    (delegate, "EMP-RPT-003", "代理人"),
    (requester, "EMP-RPT-004", "汇报员工"),
  ]:
    await profile_service.create_profile(
      actor=admin,
      user_id=user.id,
      employee_no=employee_no,
      real_name=real_name,
      department_id=department.id,
    )

  await organization_relation_service.create_reporting_line(
    actor=admin,
    user_id=requester.id,
    manager_user_id=manager.id,
    line_type=ReportingLineType.SOLID,
    starts_at=date(2025, 1, 1),
    department_id=department.id,
    is_primary=True,
  )
  await organization_relation_service.create_reporting_line(
    actor=admin,
    user_id=manager.id,
    manager_user_id=admin.id,
    line_type=ReportingLineType.SOLID,
    starts_at=date(2025, 1, 1),
    department_id=department.id,
    is_primary=True,
  )
  await delegation_service.create_delegation(
    actor=manager,
    delegator_user_id=manager.id,
    delegate_user_id=delegate.id,
    scope_type=DelegationScopeType.ALL,
    starts_at=datetime.now(UTC) - timedelta(hours=1),
    ends_at=datetime.now(UTC) + timedelta(days=2),
  )

  notification_queue = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, notification_queue)
  workflow_engine_service = WorkflowEngineService(db_session, notification_service)
  report_service = ReportService(db_session, notification_service, workflow_engine_service)
  report_center_service = ReportCenterService(report_service, workflow_engine_service)

  definition = await workflow_engine_service.create_definition(
    actor=admin,
    code="report-approval",
    name="汇报挂接审批",
    scope_type="report",
    status=WorkflowDefinitionStatus.ACTIVE,
    steps=[
      {
        "step_key": "approve",
        "name": "经理审批",
        "step_type": "approval",
        "assignee_rule": {"type": "department_manager"},
      }
    ],
  )

  report = await report_service.create_report(
    actor=requester,
    direction=ReportDirection.UPWARD,
    target_user_id=admin.id,
    title="周报",
    content_md="本周已完成重构准备与联调排期。",
    workflow_definition_id=definition.id,
  )
  first_route = report.routes[0]
  delegate_snapshot = await report_center_service.get_snapshot(actor=delegate)
  requester_snapshot = await report_center_service.get_snapshot(actor=requester)

  assert report.workflow_instance_id is not None
  assert first_route.recipient_user_id == manager.id
  assert first_route.assigned_user_id == delegate.id
  assert delegate_snapshot.pending_reports[0].id == report.id
  assert requester_snapshot.permissions["can_create_upward"] is True

  forwarded = await report_service.act_report(
    actor=delegate,
    report_id=report.id,
    action="advance",
    note="已转交给最终上级。",
  )
  second_route = next(route for route in forwarded.routes if route.sequence_no == 2)
  assert forwarded.current_recipient_user_id == admin.id
  assert second_route.status == ReportRouteStatus.PENDING

  completed = await report_service.act_report(
    actor=admin,
    report_id=report.id,
    action="advance",
  )
  assert completed.status == ReportStatus.COMPLETED

  archived = await report_service.act_report(
    actor=requester,
    report_id=report.id,
    action="archive",
  )
  history_reports = await report_service.list_history_reports(actor=requester)

  assert archived.status == ReportStatus.ARCHIVED
  assert any(item.id == report.id for item in history_reports)
  assert any(payload["message_type"] == "report_pending" for payload in notification_queue.payloads)
  assert any(payload["message_type"] == "report_completed" for payload in notification_queue.payloads)
  assert any(payload["message_type"] == "workflow_action_required" for payload in notification_queue.payloads)


@pytest.mark.asyncio
async def test_step4_report_service_creates_upward_and_downward_reports_without_delegation(db_session) -> None:
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

  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  requester = await user_service.create_user(
    actor=admin,
    email="requester@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="汇报无代理测试部",
    code="report-no-delegate",
    manager_id=admin.id,
  )
  for user, employee_no, real_name in [
    (manager, "EMP-RPT-ND-001", "中层经理"),
    (requester, "EMP-RPT-ND-002", "汇报员工"),
  ]:
    await profile_service.create_profile(
      actor=admin,
      user_id=user.id,
      employee_no=employee_no,
      real_name=real_name,
      department_id=department.id,
    )

  await organization_relation_service.create_reporting_line(
    actor=admin,
    user_id=requester.id,
    manager_user_id=manager.id,
    line_type=ReportingLineType.SOLID,
    starts_at=date(2025, 1, 1),
    department_id=department.id,
    is_primary=True,
  )
  await organization_relation_service.create_reporting_line(
    actor=admin,
    user_id=manager.id,
    manager_user_id=admin.id,
    line_type=ReportingLineType.SOLID,
    starts_at=date(2025, 1, 1),
    department_id=department.id,
    is_primary=True,
  )

  notification_queue = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, notification_queue)
  report_service = ReportService(db_session, notification_service)

  upward_report = await report_service.create_report(
    actor=requester,
    direction=ReportDirection.UPWARD,
    target_user_id=admin.id,
    title="向上汇报测试",
    content_md="验证无代理时也能正常创建。",
  )
  downward_report = await report_service.create_report(
    actor=admin,
    direction=ReportDirection.DOWNWARD,
    target_user_id=requester.id,
    title="向下传达测试",
    content_md="验证逐级向下传达的创建链路。",
  )

  assert upward_report.current_recipient_user_id == manager.id
  assert upward_report.routes[0].assigned_user_id == manager.id
  assert downward_report.current_recipient_user_id == manager.id
  assert downward_report.routes[0].assigned_user_id == manager.id
  assert sum(payload["message_type"] == "report_pending" for payload in notification_queue.payloads) == 2


@pytest.mark.asyncio
async def test_step4_report_service_keeps_report_creation_successful_when_notification_queue_fails(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )
  await SampleDataService(db_session, settings).seed_manual_test_workspace(default_password="FilumTest123!")

  actor = await db_session.scalar(select(User).where(User.email == "demo.engineer.a@example.com"))
  target = await db_session.scalar(select(User).where(User.email == "demo.tech.director@example.com"))
  assert actor is not None
  assert target is not None

  report_service = ReportService(
    db_session,
    NotificationService(db_session, FailingQueuePublisher("redis unavailable")),
  )

  report = await report_service.create_report(
    actor=actor,
    direction=ReportDirection.UPWARD,
    target_user_id=target.id,
    title="队列故障汇报测试",
    content_md="即使通知队列不可用，也不应返回 500。",
  )

  message = await db_session.scalar(
    select(NotificationMessageModel)
    .where(
      NotificationMessageModel.source_type == "report",
      NotificationMessageModel.source_id == report.id,
      NotificationMessageModel.message_type == "report_pending",
    )
  )
  deliveries = list(
    await db_session.scalars(
      select(NotificationDelivery)
      .where(NotificationDelivery.message_id == message.id)
      .order_by(NotificationDelivery.created_at.asc())
    )
  )

  assert message is not None
  assert report.current_recipient_user_id is not None
  assert message.status == NotificationMessageStatus.FAILED
  assert len(deliveries) == 2
  assert all(delivery.status == NotificationDeliveryStatus.FAILED for delivery in deliveries)
  assert all(delivery.attempt_count == 1 for delivery in deliveries)
  assert all(delivery.error_message == "通知入队失败：redis unavailable" for delivery in deliveries)


@pytest.mark.asyncio
async def test_phase5_document_service_controls_visibility_and_document_attachments(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  document_service = DocumentService(db_session)
  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  with TemporaryDirectory() as tmp_dir:
    storage_service = ObjectStorageService(
      LocalStorageAdapter(base_path=tmp_dir, bucket="filum-test")
    )
    attachment_service = AttachmentService(db_session, storage_service)

    document = await document_service.create_document(
      actor=admin,
      title="员工入职指南",
      slug=None,
      category=DocumentCategory.SOP,
      content_md="# 入职\n\n准备材料并开通账号。",
    )
    await attachment_service.upload_attachment(
      actor=admin,
      filename="onboarding.pdf",
      content_type="application/pdf",
      content=b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
      target_type=AttachmentTargetType.DOCUMENT,
      target_id=document.id,
      relation="reference",
    )

    assert await document_service.list_documents(actor=employee) == []

    published_document = await document_service.publish_document(
      actor=admin,
      document_id=document.id,
    )
    updated_document = await document_service.update_document(
      actor=admin,
      document_id=document.id,
      content_md="# 入职\n\n准备材料、开通账号并签收设备。",
    )

    visible_documents = await document_service.list_documents(actor=employee)
    attachments = await document_service.list_document_attachments(
      actor=employee,
      document_id=document.id,
    )
    employee_view = await document_service.get_document_by_slug(
      actor=employee,
      slug="员工入职指南",
    )

    assert published_document.status == DocumentStatus.PUBLISHED
    assert updated_document.version == 2
    assert len(visible_documents) == 1
    assert visible_documents[0].slug == "员工入职指南"
    assert employee_view.id == document.id
    assert len(attachments) == 1
    assert attachments[0].original_filename == "onboarding.pdf"


@pytest.mark.asyncio
async def test_phase5_knowledge_retrieval_reindexes_and_filters_by_access(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  document_service = DocumentService(db_session)
  retrieval_service = KnowledgeRetrievalService(
    db_session,
    settings,
    FakeOpenAIClient(),
  )
  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  onboarding_document = await document_service.create_document(
    actor=admin,
    title="入职资料清单",
    slug="employee-onboarding-checklist",
    category=DocumentCategory.SOP,
    content_md="入职 账号 设备",
    status=DocumentStatus.PUBLISHED,
  )
  procurement_document = await document_service.create_document(
    actor=admin,
    title="采购审批规范",
    slug="procurement-approval-policy",
    category=DocumentCategory.POLICY,
    content_md="采购 审批 预算",
    status=DocumentStatus.PUBLISHED,
  )
  draft_document = await document_service.create_document(
    actor=admin,
    title="草稿制度",
    slug="draft-policy",
    category=DocumentCategory.POLICY,
    content_md="采购 审批 草稿",
    status=DocumentStatus.DRAFT,
  )

  await retrieval_service.rebuild_document_embeddings(document_id=onboarding_document.id)
  await retrieval_service.rebuild_document_embeddings(document_id=procurement_document.id)
  await retrieval_service.rebuild_document_embeddings(document_id=draft_document.id)

  onboarding_hits = await retrieval_service.search_documents(
    actor=employee,
    query="入职账号",
  )
  policy_hits = await retrieval_service.search_documents(
    actor=admin,
    query="采购审批",
    category=DocumentCategory.POLICY,
  )
  context, context_hits = await retrieval_service.build_rag_context(
    actor=employee,
    query="入职设备",
  )

  assert onboarding_hits
  assert onboarding_hits[0].document.id == onboarding_document.id
  assert all(hit.document.status == DocumentStatus.PUBLISHED for hit in onboarding_hits)
  assert policy_hits
  assert any(hit.document.id == procurement_document.id for hit in policy_hits)
  assert any(hit.document.id == draft_document.id for hit in policy_hits)
  assert "入职资料清单" in context
  assert context_hits[0].document.id == onboarding_document.id


@pytest.mark.asyncio
async def test_phase5_browser_push_service_upserts_and_revokes_subscriptions(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  push_service = BrowserPushService(db_session)
  notification_service = NotificationService(db_session, InMemoryQueuePublisher())

  subscription = await push_service.upsert_subscription(
    actor=admin,
    endpoint="https://push.example.com/subscriptions/1",
    p256dh_key="key-1",
    auth_key="auth-1",
    user_agent="Mozilla/5.0",
  )
  updated_subscription = await push_service.upsert_subscription(
    actor=admin,
    endpoint="https://push.example.com/subscriptions/1",
    p256dh_key="key-2",
    auth_key="auth-2",
    user_agent="Chrome",
  )
  listed_subscriptions = await push_service.list_subscriptions(actor=admin)
  message = await notification_service.send(
    NotificationMessage(
      source_type="knowledge",
      source_id=None,
      recipient_user_id=admin.id,
      recipient_email=admin.email,
      message_type="knowledge_published",
      title="新制度已发布",
      body_text="员工入职 SOP 已发布。",
      channels=[NotificationChannel.WEB_PUSH],
      payload={"document_slug": "employee-onboarding-checklist"},
    )
  )
  payload = push_service.build_payload(message=message)
  revoked_subscription = await push_service.revoke_subscription(
    actor=admin,
    subscription_id=subscription.id,
  )

  assert subscription.id == updated_subscription.id
  assert updated_subscription.p256dh_key == "key-2"
  assert len(listed_subscriptions) == 1
  assert payload["title"] == "新制度已发布"
  assert payload["payload"] == {"document_slug": "employee-onboarding-checklist"}
  assert revoked_subscription.status == PushSubscriptionStatus.REVOKED


@pytest.mark.asyncio
async def test_phase5_llm_router_handles_slash_commands_and_tool_calls(db_session) -> None:
  settings = Settings(
    jwt_secret_key=TEST_JWT_SECRET,
    openai_api_key="test-openai-key",
  )
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  document_service = DocumentService(db_session)
  task_service = TaskService(db_session, NotificationService(db_session, InMemoryQueuePublisher()))
  workflow_engine_service = WorkflowEngineService(
    db_session,
    NotificationService(db_session, InMemoryQueuePublisher()),
  )
  message_center_service = MessageCenterService(db_session)
  profile_service = ProfileService(db_session)
  router_openai_client = FakeRouterOpenAIClient()
  retrieval_service = KnowledgeRetrievalService(
    db_session,
    settings,
    router_openai_client,
  )
  tool_registry_service = ToolRegistryService(
    document_service=document_service,
    retrieval_service=retrieval_service,
    task_service=task_service,
    workflow_engine_service=workflow_engine_service,
    message_center_service=message_center_service,
    profile_service=profile_service,
  )
  router_service = LLMRouterService(
    settings=settings,
    openai_client=router_openai_client,
    retrieval_service=retrieval_service,
    tool_registry_service=tool_registry_service,
  )

  document = await document_service.create_document(
    actor=admin,
    title="员工入职 SOP",
    slug="employee-onboarding-sop",
    category=DocumentCategory.SOP,
    content_md="入职流程需要先提交材料，再开通账号。",
    status=DocumentStatus.PUBLISHED,
  )
  await retrieval_service.rebuild_document_embeddings(document_id=document.id)

  slash_result = await router_service.route_text(actor=admin, text="/profile")
  mention_result = await router_service.route_text(actor=admin, text="@系统 入职流程是什么？")
  profile_tool_result = await tool_registry_service.execute_tool(
    actor=admin,
    tool_name="get_profile_summary",
    arguments={},
  )

  assert slash_result.mode == "slash_command"
  assert slash_result.command_name == "profile"
  assert slash_result.tool_results[0]["tool_name"] == "get_profile_summary"
  assert "档案摘要" in slash_result.reply_text
  assert "员工编号" not in slash_result.reply_text

  assert profile_tool_result["result"]["profile"]["real_name"] == "管理员"
  assert "user_email" not in profile_tool_result["result"]["profile"]
  assert "employee_no" not in profile_tool_result["result"]["profile"]
  assert "custom_fields" not in profile_tool_result["result"]["profile"]

  assert mention_result.mode == "mention"
  assert mention_result.tool_results
  assert mention_result.tool_results[0]["tool_name"] == "search_documents"
  assert "入职流程需要先提交材料" in mention_result.reply_text
  assert mention_result.knowledge_hits


@LEGACY_E_REMOVED
@pytest.mark.asyncio
async def test_task_template_department_members_fan_out(db_session) -> None:
  """department_members 规则结合 fan_out 模式，应为部门每位成员各创建一个任务。"""
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

  manager = await user_service.create_user(
    actor=admin,
    email="manager@dept-members.example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  member_a = await user_service.create_user(
    actor=admin,
    email="member-a@dept-members.example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  member_b = await user_service.create_user(
    actor=admin,
    email="member-b@dept-members.example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  department = await department_service.create_department(
    actor=admin,
    name="全员部门",
    code="all-members-dept",
    manager_id=manager.id,
    capabilities=[DepartmentCapability.PUBLISH_ORG_TASK],
  )
  for user_id, employee_no, real_name in [
    (manager.id, "EMP-MGR-DM", "部门主管"),
    (member_a.id, "EMP-MA-DM", "成员甲"),
    (member_b.id, "EMP-MB-DM", "成员乙"),
  ]:
    await profile_service.create_profile(
      actor=admin,
      user_id=user_id,
      employee_no=employee_no,
      real_name=real_name,
      department_id=department.id,
    )

  notification_service = NotificationService(db_session, InMemoryQueuePublisher())
  task_service = TaskService(db_session, notification_service)
  task_template_service = TaskTemplateService(db_session, task_service, notification_service)

  template = await task_template_service.create_template(
    actor=admin,
    code="dept-broadcast-sop",
    name="部门全员下发",
    category="ops",
    steps=[
      {
        "step_key": "broadcast",
        "title": "全员执行",
        "assignment_mode": "fan_out",
        "join_mode": "all",
        "default_assignee_rule": {"type": "department_members"},
      },
    ],
  )

  instantiation = await task_template_service.instantiate_template(
    actor=manager,
    template_id=template.id,
    payload={"department_id": str(department.id)},
  )
  tasks = instantiation.tasks

  assert len(tasks) == 3
  assignee_ids = {task.assignee_id for task in tasks}
  assert manager.id in assignee_ids
  assert member_a.id in assignee_ids
  assert member_b.id in assignee_ids
  for task in tasks:
    assert task.extra_metadata.get("template_step_key") == "broadcast"
    assert task.extra_metadata.get("assignment_mode") == "fan_out"


@LEGACY_E_REMOVED
@pytest.mark.asyncio
async def test_task_template_department_members_empty_department_raises(db_session) -> None:
  """department_members 规则在部门无成员时应抛出 ConflictError。"""
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  department_service = DepartmentService(db_session)
  # 建一个空部门（无任何 profile 归属）
  empty_department = await department_service.create_department(
    actor=admin,
    name="空部门",
    code="empty-dept",
    capabilities=[DepartmentCapability.PUBLISH_ORG_TASK],
  )

  notification_service = NotificationService(db_session, InMemoryQueuePublisher())
  task_service = TaskService(db_session, notification_service)
  task_template_service = TaskTemplateService(db_session, task_service, notification_service)

  template = await task_template_service.create_template(
    actor=admin,
    code="dept-broadcast-empty",
    name="全员下发（空部门）",
    category="ops",
    steps=[
      {
        "step_key": "broadcast",
        "title": "全员执行",
        "assignment_mode": "fan_out",
        "join_mode": "all",
        "default_assignee_rule": {"type": "department_members"},
      },
    ],
  )

  with pytest.raises(ConflictError):
    await task_template_service.instantiate_template(
      actor=admin,
      template_id=template.id,
      payload={"department_id": str(empty_department.id)},
    )


# =========================================================================
# Phase 6 / Multi-node graph engine: sequential, fan-out, wait-all
# =========================================================================

@pytest.mark.asyncio
async def test_phase6_sequential_flow_activation(db_session) -> None:
  """A→B 顺序流：节点 A 完成后，节点 B 应自动激活。"""
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode, WorkflowGraphTemplateEdge
  from app.core.enums import WorkflowGraphTemplateStatus

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  # 手动建 WorkflowGraphTemplate（A→B 两节点）
  template = WorkflowGraphTemplate(
    code="seq-flow-test",
    base_code="seq-flow-test",
    version=1,
    name="顺序流测试模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

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
  db_session.add_all([node_a, node_b])
  await db_session.flush()

  edge_ab = WorkflowGraphTemplateEdge(
    template_id=template.id,
    from_node_id=node_a.id,
    to_node_id=node_b.id,
  )
  db_session.add(edge_ab)
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(
    template_id=template.id,
    initiator_id=admin.id,
  )

  instance = result.instance
  node_instances = result.node_instances
  ni_a = next(ni for ni in node_instances if ni.node_key == "node-a")
  ni_b = next(ni for ni in node_instances if ni.node_key == "node-b")

  assert ni_a.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert ni_b.engine_state == WorkflowNodeEngineState.PENDING
  assert instance.current_node_key == "node-a"

  # 完成 A，B 应激活
  await wg_service.complete_node_instance(
    node_instance_id=ni_a.id,
    actor_id=admin.id,
  )
  await db_session.refresh(ni_a)
  await db_session.refresh(ni_b)
  await db_session.refresh(instance)

  assert ni_a.engine_state == WorkflowNodeEngineState.COMPLETED
  assert ni_b.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert instance.current_node_key == "node-b"
  assert instance.status == WorkflowGraphInstanceStatus.ACTIVE

  # 完成 B，实例收口
  await wg_service.complete_node_instance(
    node_instance_id=ni_b.id,
    actor_id=admin.id,
  )
  await db_session.refresh(ni_b)
  await db_session.refresh(instance)

  assert ni_b.engine_state == WorkflowNodeEngineState.COMPLETED
  assert instance.status == WorkflowGraphInstanceStatus.COMPLETED
  assert instance.completed_at is not None


@pytest.mark.asyncio
async def test_phase6_fan_out_activation(db_session) -> None:
  """A→B, A→C fan-out：A 完成后，B 和 C 应同时激活。"""
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode, WorkflowGraphTemplateEdge
  from app.core.enums import WorkflowGraphTemplateStatus

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  template = WorkflowGraphTemplate(
    code="fan-out-test",
    base_code="fan-out-test",
    version=1,
    name="Fan-out 测试模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-a", title="节点 A", sort_order=1)
  node_b = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-b", title="节点 B", sort_order=2)
  node_c = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-c", title="节点 C", sort_order=3)
  db_session.add_all([node_a, node_b, node_c])
  await db_session.flush()

  db_session.add_all([
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_b.id),
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_c.id),
  ])
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(
    template_id=template.id,
    initiator_id=admin.id,
  )

  ni_a = next(ni for ni in result.node_instances if ni.node_key == "node-a")
  ni_b = next(ni for ni in result.node_instances if ni.node_key == "node-b")
  ni_c = next(ni for ni in result.node_instances if ni.node_key == "node-c")

  assert ni_a.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert ni_b.engine_state == WorkflowNodeEngineState.PENDING
  assert ni_c.engine_state == WorkflowNodeEngineState.PENDING

  await wg_service.complete_node_instance(node_instance_id=ni_a.id, actor_id=admin.id)
  await db_session.refresh(ni_b)
  await db_session.refresh(ni_c)

  assert ni_b.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert ni_c.engine_state == WorkflowNodeEngineState.ACTIVATED


@pytest.mark.asyncio
async def test_phase6_wait_all_join(db_session) -> None:
  """B+C→D AND-Join：B 完成后 D 仍 PENDING，C 完成后 D 激活。"""
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode, WorkflowGraphTemplateEdge
  from app.core.enums import WorkflowGraphTemplateStatus

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  template = WorkflowGraphTemplate(
    code="wait-all-test",
    base_code="wait-all-test",
    version=1,
    name="Wait-All 测试模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  # A → B, A → C, B → D (join_mode=all), C → D
  node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-a", title="节点 A", sort_order=1)
  node_b = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-b", title="节点 B", sort_order=2)
  node_c = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-c", title="节点 C", sort_order=3)
  node_d = WorkflowGraphTemplateNode(
    template_id=template.id, node_key="node-d", title="节点 D", sort_order=4, join_mode="all"
  )
  db_session.add_all([node_a, node_b, node_c, node_d])
  await db_session.flush()

  db_session.add_all([
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_b.id),
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_c.id),
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_b.id, to_node_id=node_d.id),
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_c.id, to_node_id=node_d.id),
  ])
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(
    template_id=template.id,
    initiator_id=admin.id,
  )

  ni_a = next(ni for ni in result.node_instances if ni.node_key == "node-a")
  ni_b = next(ni for ni in result.node_instances if ni.node_key == "node-b")
  ni_c = next(ni for ni in result.node_instances if ni.node_key == "node-c")
  ni_d = next(ni for ni in result.node_instances if ni.node_key == "node-d")
  instance = result.instance

  # 完成 A → B,C 激活
  await wg_service.complete_node_instance(node_instance_id=ni_a.id, actor_id=admin.id)
  await db_session.refresh(ni_b)
  await db_session.refresh(ni_c)
  await db_session.refresh(ni_d)
  assert ni_b.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert ni_c.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert ni_d.engine_state == WorkflowNodeEngineState.PENDING

  # 完成 B → D 仍 PENDING（C 未完成）
  await wg_service.complete_node_instance(node_instance_id=ni_b.id, actor_id=admin.id)
  await db_session.refresh(ni_d)
  assert ni_d.engine_state == WorkflowNodeEngineState.PENDING

  # 完成 C → D 激活，实例仍 ACTIVE
  await wg_service.complete_node_instance(node_instance_id=ni_c.id, actor_id=admin.id)
  await db_session.refresh(ni_d)
  await db_session.refresh(instance)
  assert ni_d.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert instance.status == WorkflowGraphInstanceStatus.ACTIVE

  # 完成 D → 实例收口
  await wg_service.complete_node_instance(node_instance_id=ni_d.id, actor_id=admin.id)
  await db_session.refresh(instance)
  assert instance.status == WorkflowGraphInstanceStatus.COMPLETED
  assert instance.completed_at is not None


@pytest.mark.asyncio
async def test_phase11d_wait_all_join_replay_keeps_single_downstream_activation(db_session) -> None:
  """Wait-All 最后一个上游重复提交时，下游节点不能被再次激活或重复改版本。"""
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode, WorkflowGraphTemplateEdge
  from app.core.enums import WorkflowGraphTemplateStatus

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  template = WorkflowGraphTemplate(
    code="phase11d-wait-all-replay",
    base_code="phase11d-wait-all-replay",
    version=1,
    name="Phase 11-D Wait-All 重放测试",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-a", title="节点 A", sort_order=1)
  node_b = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-b", title="节点 B", sort_order=2)
  node_c = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-c", title="节点 C", sort_order=3)
  node_d = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="node-d",
    title="汇聚节点 D",
    sort_order=4,
    join_mode="all",
  )
  db_session.add_all([node_a, node_b, node_c, node_d])
  await db_session.flush()

  db_session.add_all([
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_b.id),
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_c.id),
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_b.id, to_node_id=node_d.id),
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_c.id, to_node_id=node_d.id),
  ])
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(
    template_id=template.id,
    initiator_id=admin.id,
  )

  instance = result.instance
  ni_a = next(ni for ni in result.node_instances if ni.node_key == "node-a")
  ni_b = next(ni for ni in result.node_instances if ni.node_key == "node-b")
  ni_c = next(ni for ni in result.node_instances if ni.node_key == "node-c")
  ni_d = next(ni for ni in result.node_instances if ni.node_key == "node-d")

  await wg_service.complete_node_instance(node_instance_id=ni_a.id, actor_id=admin.id)
  await wg_service.complete_node_instance(node_instance_id=ni_b.id, actor_id=admin.id)
  await wg_service.complete_node_instance(node_instance_id=ni_c.id, actor_id=admin.id)
  await db_session.refresh(ni_d)
  await db_session.refresh(instance)

  first_downstream_version = ni_d.node_instance_version
  first_activated_at = ni_d.activated_at

  await wg_service.complete_node_instance(node_instance_id=ni_c.id, actor_id=admin.id)
  await db_session.refresh(ni_d)
  await db_session.refresh(instance)

  assert ni_d.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert ni_d.node_instance_version == first_downstream_version
  assert ni_d.activated_at == first_activated_at
  assert instance.current_node_key == "node-d"


@pytest.mark.asyncio
async def test_phase6_instance_completion_marks_graph_done(db_session) -> None:
  """单节点图（无出边叶节点）完成后，实例状态直接变为 COMPLETED。"""
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode
  from app.core.enums import WorkflowGraphTemplateStatus

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  template = WorkflowGraphTemplate(
    code="single-leaf-test",
    base_code="single-leaf-test",
    version=1,
    name="单叶节点模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="only-node", title="唯一节点", sort_order=1)
  db_session.add(node_a)
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(
    template_id=template.id,
    initiator_id=admin.id,
  )
  ni = result.node_instances[0]
  instance = result.instance

  assert ni.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert instance.status == WorkflowGraphInstanceStatus.ACTIVE

  await wg_service.complete_node_instance(node_instance_id=ni.id, actor_id=admin.id)
  await db_session.refresh(instance)

  assert instance.status == WorkflowGraphInstanceStatus.COMPLETED
  assert instance.completed_at is not None
  assert instance.current_node_key is None


@pytest.mark.asyncio
async def test_phase7_context_conditional_routing_and_notice_auto_completion(db_session) -> None:
  from app.core.enums import WorkflowGraphNodeType, WorkflowGraphTemplateStatus
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  template = WorkflowGraphTemplate(
    code="phase7-context-condition-notice",
    base_code="phase7-context-condition-notice",
    version=1,
    name="Phase 7 条件路由与 Notice 测试模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-a", title="发起节点", sort_order=1)
  node_notice = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="notice-middle",
    title="抄送通知",
    node_type=WorkflowGraphNodeType.NOTICE,
    sort_order=2,
  )
  node_b = WorkflowGraphTemplateNode(template_id=template.id, node_key="path-b", title="高金额路径", sort_order=3)
  node_c = WorkflowGraphTemplateNode(template_id=template.id, node_key="path-c", title="默认路径", sort_order=4)
  db_session.add_all([node_a, node_notice, node_b, node_c])
  await db_session.flush()

  db_session.add_all(
    [
      WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_notice.id),
      WorkflowGraphTemplateEdge(
        template_id=template.id,
        from_node_id=node_a.id,
        to_node_id=node_b.id,
        condition={"field": "amount", "operator": "gte", "value": 100000},
      ),
      WorkflowGraphTemplateEdge(
        template_id=template.id,
        from_node_id=node_a.id,
        to_node_id=node_c.id,
        condition={"else": True},
      ),
    ]
  )
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(template_id=template.id, initiator_id=admin.id)

  instance = result.instance
  node_a_instance = next(node for node in result.node_instances if node.node_key == "node-a")
  notice_instance = next(node for node in result.node_instances if node.node_key == "notice-middle")
  node_b_instance = next(node for node in result.node_instances if node.node_key == "path-b")
  node_c_instance = next(node for node in result.node_instances if node.node_key == "path-c")

  await wg_service.complete_node_instance(
    node_instance_id=node_a_instance.id,
    actor_id=admin.id,
    context_updates={"amount": 200000, "request_type": "purchase"},
    expected_context_version=1,
  )

  await db_session.refresh(instance)
  await db_session.refresh(notice_instance)
  await db_session.refresh(node_b_instance)
  await db_session.refresh(node_c_instance)

  assert instance.context["amount"] == 200000
  assert instance.context["request_type"] == "purchase"
  assert instance.context_version == 2
  assert notice_instance.engine_state == WorkflowNodeEngineState.COMPLETED
  assert node_b_instance.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert node_c_instance.engine_state == WorkflowNodeEngineState.SKIPPED


@pytest.mark.asyncio
async def test_phase7_smart_notice_candidates_returns_manager_chain(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  department_service = DepartmentService(db_session)
  organization_relation_service = OrganizationRelationService(db_session)

  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  executor = await user_service.create_user(
    actor=admin,
    email="executor@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  department = await department_service.create_department(actor=admin, name="研发部", code="phase7-notice-dept")

  await profile_service.create_profile(
    actor=admin,
    user_id=manager.id,
    employee_no="EMP-P7-MGR",
    real_name="中层经理",
    department_id=department.id,
    custom_fields={},
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=executor.id,
    employee_no="EMP-P7-EXEC",
    real_name="执行人",
    department_id=department.id,
    custom_fields={},
  )

  await organization_relation_service.create_reporting_line(
    actor=admin,
    user_id=executor.id,
    manager_user_id=manager.id,
    line_type=ReportingLineType.SOLID,
    starts_at=date(2025, 1, 1),
    department_id=department.id,
    is_primary=True,
  )
  await organization_relation_service.create_reporting_line(
    actor=admin,
    user_id=manager.id,
    manager_user_id=admin.id,
    line_type=ReportingLineType.SOLID,
    starts_at=date(2025, 1, 1),
    department_id=department.id,
    is_primary=True,
  )

  candidate_user_ids, reached_initiator = await organization_relation_service.suggest_notice_recipients(
    initiator_user_id=admin.id,
    target_user_id=executor.id,
    include_user_ids=[admin.id],
    exclude_user_ids=[executor.id],
  )

  assert reached_initiator is True
  assert candidate_user_ids == [manager.id]


@pytest.mark.asyncio
async def test_phase8_wait_any_activates_downstream_and_terminates_peer_nodes(db_session) -> None:
  """join_mode=any: 任一分支先完成即推进下游，并自动撤销同批并发节点。"""
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode
  from app.core.enums import WorkflowGraphTemplateStatus

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  template = WorkflowGraphTemplate(
    code="phase8-wait-any-race",
    base_code="phase8-wait-any-race",
    version=1,
    name="Phase 8 Wait-Any 测试模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-a", title="节点 A", sort_order=1)
  node_b = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-b", title="节点 B", sort_order=2)
  node_c = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-c", title="节点 C", sort_order=3)
  node_d = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="node-d",
    title="汇聚节点 D",
    sort_order=4,
    join_mode="any",
  )
  db_session.add_all([node_a, node_b, node_c, node_d])
  await db_session.flush()

  db_session.add_all(
    [
      WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_b.id),
      WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_c.id),
      WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_b.id, to_node_id=node_d.id),
      WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_c.id, to_node_id=node_d.id),
    ]
  )
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(template_id=template.id, initiator_id=admin.id)

  instance = result.instance
  ni_a = next(ni for ni in result.node_instances if ni.node_key == "node-a")
  ni_b = next(ni for ni in result.node_instances if ni.node_key == "node-b")
  ni_c = next(ni for ni in result.node_instances if ni.node_key == "node-c")
  ni_d = next(ni for ni in result.node_instances if ni.node_key == "node-d")

  await wg_service.complete_node_instance(node_instance_id=ni_a.id, actor_id=admin.id)
  await db_session.refresh(ni_b)
  await db_session.refresh(ni_c)
  assert ni_b.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert ni_c.engine_state == WorkflowNodeEngineState.ACTIVATED

  await wg_service.complete_node_instance(node_instance_id=ni_b.id, actor_id=admin.id)
  await db_session.refresh(ni_b)
  await db_session.refresh(ni_c)
  await db_session.refresh(ni_d)

  assert ni_b.engine_state == WorkflowNodeEngineState.COMPLETED
  assert ni_d.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert ni_c.engine_state == WorkflowNodeEngineState.TERMINATED
  assert ni_c.business_state == WorkflowNodeBusinessState.CANCELLED
  assert ni_c.terminated_at is not None
  assert dict(ni_c.config).get("system_resolution", {}).get("reason") == "wait_any_resolved"
  assert dict(ni_c.config).get("system_resolution", {}).get("cancel_policy") == "revoke"

  with pytest.raises(ConflictError, match="已被系统撤权"):
    await wg_service.complete_node_instance(node_instance_id=ni_c.id, actor_id=admin.id)

  await wg_service.complete_node_instance(node_instance_id=ni_d.id, actor_id=admin.id)
  await db_session.refresh(instance)

  assert instance.status == WorkflowGraphInstanceStatus.COMPLETED
  assert instance.current_node_key is None


@pytest.mark.asyncio
async def test_phase11d_wait_any_replay_keeps_single_downstream_activation(db_session) -> None:
  """Wait-Any 获胜上游重复提交时，下游节点和输家节点版本都应保持稳定。"""
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode
  from app.core.enums import WorkflowGraphTemplateStatus

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  template = WorkflowGraphTemplate(
    code="phase11d-wait-any-replay",
    base_code="phase11d-wait-any-replay",
    version=1,
    name="Phase 11-D Wait-Any 重放测试",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-a", title="节点 A", sort_order=1)
  node_b = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-b", title="节点 B", sort_order=2)
  node_c = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-c", title="节点 C", sort_order=3)
  node_d = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="node-d",
    title="汇聚节点 D",
    sort_order=4,
    join_mode="any",
  )
  db_session.add_all([node_a, node_b, node_c, node_d])
  await db_session.flush()

  db_session.add_all(
    [
      WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_b.id),
      WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_c.id),
      WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_b.id, to_node_id=node_d.id),
      WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_c.id, to_node_id=node_d.id),
    ]
  )
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(template_id=template.id, initiator_id=admin.id)

  instance = result.instance
  ni_a = next(ni for ni in result.node_instances if ni.node_key == "node-a")
  ni_b = next(ni for ni in result.node_instances if ni.node_key == "node-b")
  ni_c = next(ni for ni in result.node_instances if ni.node_key == "node-c")
  ni_d = next(ni for ni in result.node_instances if ni.node_key == "node-d")

  await wg_service.complete_node_instance(node_instance_id=ni_a.id, actor_id=admin.id)
  await wg_service.complete_node_instance(node_instance_id=ni_b.id, actor_id=admin.id)
  await db_session.refresh(ni_c)
  await db_session.refresh(ni_d)
  await db_session.refresh(instance)

  first_downstream_version = ni_d.node_instance_version
  first_downstream_activated_at = ni_d.activated_at
  first_loser_version = ni_c.node_instance_version
  first_loser_terminated_at = ni_c.terminated_at

  await wg_service.complete_node_instance(node_instance_id=ni_b.id, actor_id=admin.id)
  await db_session.refresh(ni_c)
  await db_session.refresh(ni_d)
  await db_session.refresh(instance)

  assert ni_d.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert ni_d.node_instance_version == first_downstream_version
  assert ni_d.activated_at == first_downstream_activated_at
  assert ni_c.engine_state == WorkflowNodeEngineState.TERMINATED
  assert ni_c.node_instance_version == first_loser_version
  assert ni_c.terminated_at == first_loser_terminated_at
  assert instance.current_node_key == "node-d"


@pytest.mark.asyncio
async def test_phase9_deep_reject_replays_from_target_with_append_only_iteration(db_session) -> None:
  """D 打回 A 后应生成 A/B/C/D 的新迭代实例，历史节点保留不覆盖。"""
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode
  from app.core.enums import WorkflowGraphTemplateStatus

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  template = WorkflowGraphTemplate(
    code="phase9-deep-reject",
    base_code="phase9-deep-reject",
    version=1,
    name="Phase 9 深度打回测试模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-a", title="节点 A", sort_order=1)
  node_b = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-b", title="节点 B", sort_order=2)
  node_c = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-c", title="节点 C", sort_order=3)
  node_d = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-d", title="节点 D", sort_order=4)
  db_session.add_all([node_a, node_b, node_c, node_d])
  await db_session.flush()

  db_session.add_all(
    [
      WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_b.id),
      WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_b.id, to_node_id=node_c.id),
      WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_c.id, to_node_id=node_d.id),
    ]
  )
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(template_id=template.id, initiator_id=admin.id)

  instance = result.instance
  ni_a = next(ni for ni in result.node_instances if ni.node_key == "node-a")
  ni_b = next(ni for ni in result.node_instances if ni.node_key == "node-b")
  ni_c = next(ni for ni in result.node_instances if ni.node_key == "node-c")
  ni_d = next(ni for ni in result.node_instances if ni.node_key == "node-d")

  await wg_service.complete_node_instance(node_instance_id=ni_a.id, actor_id=admin.id)
  await wg_service.complete_node_instance(node_instance_id=ni_b.id, actor_id=admin.id)
  await wg_service.complete_node_instance(node_instance_id=ni_c.id, actor_id=admin.id)
  await db_session.refresh(ni_d)
  assert ni_d.engine_state == WorkflowNodeEngineState.ACTIVATED

  await wg_service.deep_reject_to_upstream(
    node_instance_id=ni_d.id,
    actor_id=admin.id,
    target_node_key="node-a",
    reason="回到草稿重做",
  )

  all_nodes = await wg_service.list_node_instances_for_graph(instance_id=instance.id)
  assert len(all_nodes) == 8

  node_a_v1 = [node for node in all_nodes if node.node_key == "node-a" and node.iteration == 1][0]
  node_b_v1 = [node for node in all_nodes if node.node_key == "node-b" and node.iteration == 1][0]
  node_c_v1 = [node for node in all_nodes if node.node_key == "node-c" and node.iteration == 1][0]
  node_d_v1 = [node for node in all_nodes if node.node_key == "node-d" and node.iteration == 1][0]
  node_a_v2 = [node for node in all_nodes if node.node_key == "node-a" and node.iteration == 2][0]
  node_b_v2 = [node for node in all_nodes if node.node_key == "node-b" and node.iteration == 2][0]
  node_c_v2 = [node for node in all_nodes if node.node_key == "node-c" and node.iteration == 2][0]
  node_d_v2 = [node for node in all_nodes if node.node_key == "node-d" and node.iteration == 2][0]

  assert node_a_v1.engine_state == WorkflowNodeEngineState.COMPLETED
  assert node_b_v1.engine_state == WorkflowNodeEngineState.COMPLETED
  assert node_c_v1.engine_state == WorkflowNodeEngineState.COMPLETED
  assert node_d_v1.engine_state == WorkflowNodeEngineState.TERMINATED
  assert node_d_v1.business_state == WorkflowNodeBusinessState.CANCELLED

  assert node_a_v2.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert node_b_v2.engine_state == WorkflowNodeEngineState.PENDING
  assert node_c_v2.engine_state == WorkflowNodeEngineState.PENDING
  assert node_d_v2.engine_state == WorkflowNodeEngineState.PENDING

  await db_session.refresh(instance)
  assert instance.current_node_key == "node-a"
  assert instance.status == WorkflowGraphInstanceStatus.ACTIVE


@pytest.mark.asyncio
async def test_phase9_deep_reject_blocks_when_iteration_exceeds_max_iterations(db_session) -> None:
  """当新迭代超过 max_iterations 时应拒绝深度打回。"""
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode
  from app.core.enums import WorkflowGraphTemplateStatus

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  template = WorkflowGraphTemplate(
    code="phase9-max-iterations",
    base_code="phase9-max-iterations",
    version=1,
    name="Phase 9 迭代上限测试模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-a", title="节点 A", sort_order=1)
  node_b = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-b", title="节点 B", sort_order=2)
  db_session.add_all([node_a, node_b])
  await db_session.flush()

  db_session.add(
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_b.id)
  )
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(template_id=template.id, initiator_id=admin.id)
  instance = result.instance
  instance.max_iterations = 1
  await db_session.flush()

  ni_a = next(ni for ni in result.node_instances if ni.node_key == "node-a")
  ni_b = next(ni for ni in result.node_instances if ni.node_key == "node-b")
  await wg_service.complete_node_instance(node_instance_id=ni_a.id, actor_id=admin.id)
  await db_session.refresh(ni_b)
  assert ni_b.engine_state == WorkflowNodeEngineState.ACTIVATED

  with pytest.raises(ConflictError, match="已达上限"):
    await wg_service.deep_reject_to_upstream(
      node_instance_id=ni_b.id,
      actor_id=admin.id,
      target_node_key="node-a",
      reason="超过上限",
    )


@pytest.mark.asyncio
async def test_phase6_repeat_completion_is_idempotent_and_keeps_single_downstream_activation(db_session) -> None:
  """重复完成同一节点时应保持幂等，不应重复激活下游或污染实例状态。"""
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode, WorkflowGraphTemplateEdge
  from app.core.enums import WorkflowGraphTemplateStatus

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  template = WorkflowGraphTemplate(
    code="repeat-complete-test",
    base_code="repeat-complete-test",
    version=1,
    name="重复完成测试模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-a", title="节点 A", sort_order=1)
  node_b = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-b", title="节点 B", sort_order=2)
  db_session.add_all([node_a, node_b])
  await db_session.flush()

  db_session.add(
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_b.id)
  )
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(template_id=template.id, initiator_id=admin.id)

  instance = result.instance
  ni_a = next(ni for ni in result.node_instances if ni.node_key == "node-a")
  ni_b = next(ni for ni in result.node_instances if ni.node_key == "node-b")

  await wg_service.complete_node_instance(node_instance_id=ni_a.id, actor_id=admin.id)
  await db_session.refresh(ni_a)
  await db_session.refresh(ni_b)
  await db_session.refresh(instance)

  first_completed_at = ni_a.completed_at
  first_node_version = ni_a.node_instance_version
  first_downstream_version = ni_b.node_instance_version

  await wg_service.complete_node_instance(node_instance_id=ni_a.id, actor_id=admin.id)
  await db_session.refresh(ni_a)
  await db_session.refresh(ni_b)
  await db_session.refresh(instance)

  assert ni_a.completed_at == first_completed_at
  assert ni_a.node_instance_version == first_node_version
  assert ni_b.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert ni_b.node_instance_version == first_downstream_version
  assert instance.status == WorkflowGraphInstanceStatus.ACTIVE
  assert instance.current_node_key == "node-b"


@pytest.mark.asyncio
async def test_phase6_fan_out_current_node_key_uses_lowest_sort_order_active_node(db_session) -> None:
  """fan-out 同时激活多个节点时，current_node_key 应稳定指向排序最靠前的激活节点。"""
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode, WorkflowGraphTemplateEdge
  from app.core.enums import WorkflowGraphTemplateStatus

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  template = WorkflowGraphTemplate(
    code="fan-out-current-node-test",
    base_code="fan-out-current-node-test",
    version=1,
    name="Fan-out current_node_key 测试模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-a", title="节点 A", sort_order=1)
  node_c = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-c", title="节点 C", sort_order=3)
  node_b = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-b", title="节点 B", sort_order=2)
  db_session.add_all([node_a, node_c, node_b])
  await db_session.flush()

  db_session.add_all([
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_c.id),
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_b.id),
  ])
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(template_id=template.id, initiator_id=admin.id)

  instance = result.instance
  ni_a = next(ni for ni in result.node_instances if ni.node_key == "node-a")
  ni_b = next(ni for ni in result.node_instances if ni.node_key == "node-b")
  ni_c = next(ni for ni in result.node_instances if ni.node_key == "node-c")

  await wg_service.complete_node_instance(node_instance_id=ni_a.id, actor_id=admin.id)
  await db_session.refresh(ni_b)
  await db_session.refresh(ni_c)
  await db_session.refresh(instance)

  assert ni_b.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert ni_c.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert instance.current_node_key == "node-b"


# =========================================================================
# Phase 6 / Multi-node graph engine: sequential, fan-out, wait-all
# =========================================================================

@pytest.mark.asyncio
async def test_phase6_sequential_flow_activation(db_session) -> None:
  """A→B 顺序流：节点 A 完成后，节点 B 应自动激活。"""
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode, WorkflowGraphTemplateEdge
  from app.core.enums import WorkflowGraphTemplateStatus

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  # 手动建 WorkflowGraphTemplate（A→B 两节点）
  template = WorkflowGraphTemplate(
    code="seq-flow-test",
    base_code="seq-flow-test",
    version=1,
    name="顺序流测试模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

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
  db_session.add_all([node_a, node_b])
  await db_session.flush()

  edge_ab = WorkflowGraphTemplateEdge(
    template_id=template.id,
    from_node_id=node_a.id,
    to_node_id=node_b.id,
  )
  db_session.add(edge_ab)
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(
    template_id=template.id,
    initiator_id=admin.id,
  )

  instance = result.instance
  node_instances = result.node_instances
  ni_a = next(ni for ni in node_instances if ni.node_key == "node-a")
  ni_b = next(ni for ni in node_instances if ni.node_key == "node-b")

  assert ni_a.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert ni_b.engine_state == WorkflowNodeEngineState.PENDING
  assert instance.current_node_key == "node-a"

  # 完成 A，B 应激活
  await wg_service.complete_node_instance(
    node_instance_id=ni_a.id,
    actor_id=admin.id,
  )
  await db_session.refresh(ni_a)
  await db_session.refresh(ni_b)
  await db_session.refresh(instance)

  assert ni_a.engine_state == WorkflowNodeEngineState.COMPLETED
  assert ni_b.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert instance.current_node_key == "node-b"
  assert instance.status == WorkflowGraphInstanceStatus.ACTIVE

  # 完成 B，实例收口
  await wg_service.complete_node_instance(
    node_instance_id=ni_b.id,
    actor_id=admin.id,
  )
  await db_session.refresh(ni_b)
  await db_session.refresh(instance)

  assert ni_b.engine_state == WorkflowNodeEngineState.COMPLETED
  assert instance.status == WorkflowGraphInstanceStatus.COMPLETED
  assert instance.completed_at is not None


@pytest.mark.asyncio
async def test_phase6_fan_out_activation(db_session) -> None:
  """A→B, A→C fan-out：A 完成后，B 和 C 应同时激活。"""
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode, WorkflowGraphTemplateEdge
  from app.core.enums import WorkflowGraphTemplateStatus

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  template = WorkflowGraphTemplate(
    code="fan-out-test",
    base_code="fan-out-test",
    version=1,
    name="Fan-out 测试模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-a", title="节点 A", sort_order=1)
  node_b = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-b", title="节点 B", sort_order=2)
  node_c = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-c", title="节点 C", sort_order=3)
  db_session.add_all([node_a, node_b, node_c])
  await db_session.flush()

  db_session.add_all([
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_b.id),
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_c.id),
  ])
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(
    template_id=template.id,
    initiator_id=admin.id,
  )

  ni_a = next(ni for ni in result.node_instances if ni.node_key == "node-a")
  ni_b = next(ni for ni in result.node_instances if ni.node_key == "node-b")
  ni_c = next(ni for ni in result.node_instances if ni.node_key == "node-c")

  assert ni_a.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert ni_b.engine_state == WorkflowNodeEngineState.PENDING
  assert ni_c.engine_state == WorkflowNodeEngineState.PENDING

  await wg_service.complete_node_instance(node_instance_id=ni_a.id, actor_id=admin.id)
  await db_session.refresh(ni_b)
  await db_session.refresh(ni_c)

  assert ni_b.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert ni_c.engine_state == WorkflowNodeEngineState.ACTIVATED


@pytest.mark.asyncio
async def test_phase6_wait_all_join(db_session) -> None:
  """B+C→D AND-Join：B 完成后 D 仍 PENDING，C 完成后 D 激活。"""
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode, WorkflowGraphTemplateEdge
  from app.core.enums import WorkflowGraphTemplateStatus

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  template = WorkflowGraphTemplate(
    code="wait-all-test",
    base_code="wait-all-test",
    version=1,
    name="Wait-All 测试模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  # A → B, A → C, B → D (join_mode=all), C → D
  node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-a", title="节点 A", sort_order=1)
  node_b = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-b", title="节点 B", sort_order=2)
  node_c = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-c", title="节点 C", sort_order=3)
  node_d = WorkflowGraphTemplateNode(
    template_id=template.id, node_key="node-d", title="节点 D", sort_order=4, join_mode="all"
  )
  db_session.add_all([node_a, node_b, node_c, node_d])
  await db_session.flush()

  db_session.add_all([
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_b.id),
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_c.id),
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_b.id, to_node_id=node_d.id),
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_c.id, to_node_id=node_d.id),
  ])
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(
    template_id=template.id,
    initiator_id=admin.id,
  )

  ni_a = next(ni for ni in result.node_instances if ni.node_key == "node-a")
  ni_b = next(ni for ni in result.node_instances if ni.node_key == "node-b")
  ni_c = next(ni for ni in result.node_instances if ni.node_key == "node-c")
  ni_d = next(ni for ni in result.node_instances if ni.node_key == "node-d")
  instance = result.instance

  # 完成 A → B,C 激活
  await wg_service.complete_node_instance(node_instance_id=ni_a.id, actor_id=admin.id)
  await db_session.refresh(ni_b)
  await db_session.refresh(ni_c)
  await db_session.refresh(ni_d)
  assert ni_b.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert ni_c.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert ni_d.engine_state == WorkflowNodeEngineState.PENDING

  # 完成 B → D 仍 PENDING（C 未完成）
  await wg_service.complete_node_instance(node_instance_id=ni_b.id, actor_id=admin.id)
  await db_session.refresh(ni_d)
  assert ni_d.engine_state == WorkflowNodeEngineState.PENDING

  # 完成 C → D 激活，实例仍 ACTIVE
  await wg_service.complete_node_instance(node_instance_id=ni_c.id, actor_id=admin.id)
  await db_session.refresh(ni_d)
  await db_session.refresh(instance)
  assert ni_d.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert instance.status == WorkflowGraphInstanceStatus.ACTIVE

  # 完成 D → 实例收口
  await wg_service.complete_node_instance(node_instance_id=ni_d.id, actor_id=admin.id)
  await db_session.refresh(instance)
  assert instance.status == WorkflowGraphInstanceStatus.COMPLETED
  assert instance.completed_at is not None


@pytest.mark.asyncio
async def test_phase6_instance_completion_marks_graph_done(db_session) -> None:
  """单节点图（无出边叶节点）完成后，实例状态直接变为 COMPLETED。"""
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode
  from app.core.enums import WorkflowGraphTemplateStatus

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  template = WorkflowGraphTemplate(
    code="single-leaf-test",
    base_code="single-leaf-test",
    version=1,
    name="单叶节点模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="only-node", title="唯一节点", sort_order=1)
  db_session.add(node_a)
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(
    template_id=template.id,
    initiator_id=admin.id,
  )
  ni = result.node_instances[0]
  instance = result.instance

  assert ni.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert instance.status == WorkflowGraphInstanceStatus.ACTIVE

  await wg_service.complete_node_instance(node_instance_id=ni.id, actor_id=admin.id)
  await db_session.refresh(instance)

  assert instance.status == WorkflowGraphInstanceStatus.COMPLETED
  assert instance.completed_at is not None
  assert instance.current_node_key is None


# =========================================================================
# Phase 11-A: routing_rules 桥接到旧模板系统的条件激活
# =========================================================================

@LEGACY_E_REMOVED
@pytest.mark.asyncio
async def test_phase11a_routing_rules_condition_match_activates_only_target_step(db_session) -> None:
  """步骤 A 配置 routing_rules（条件 amount > 10000 -> step_b，else -> step_c）:
  当 instance.payload.amount == 50000 时，步骤 A 完成后应只激活 step_b，
  而 step_c 不被激活。
  """
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

  manager = await user_service.create_user(
    actor=admin,
    email="manager@routing-rules.example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  requester = await user_service.create_user(
    actor=admin,
    email="requester@routing-rules.example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="路由规则测试部",
    code="routing-rules-dept",
    manager_id=manager.id,
    capabilities=[DepartmentCapability.PUBLISH_ORG_TASK],
  )
  for user_id, employee_no, real_name in [
    (manager.id, "EMP-RR-MGR", "路由规则主管"),
    (requester.id, "EMP-RR-REQ", "路由规则发起人"),
  ]:
    await profile_service.create_profile(
      actor=admin,
      user_id=user_id,
      employee_no=employee_no,
      real_name=real_name,
      department_id=department.id,
    )

  notification_service = NotificationService(db_session, InMemoryQueuePublisher())
  task_service = TaskService(db_session, notification_service)
  task_template_service = TaskTemplateService(db_session, task_service, notification_service)

  routing_rules = [
    {
      "condition": {"field": "amount", "operator": "gt", "value": 10000},
      "target_step_key": "step_b",
    },
    {"else": True, "target_step_key": "step_c"},
  ]

  template = await task_template_service.create_template(
    actor=admin,
    code="routing-rules-branch-test",
    name="路由分支测试模板",
    category="ops",
    steps=[
      {
        "step_key": "step_a",
        "title": "申请提交",
        "default_assignee_rule": {"type": "initiator"},
        "config": {"routing_rules": routing_rules},
      },
      {
        "step_key": "step_b",
        "title": "大额审批",
        "default_assignee_rule": {"type": "department_manager"},
        "depends_on_step_keys": ["step_a"],
      },
      {
        "step_key": "step_c",
        "title": "普通确认",
        "default_assignee_rule": {"type": "department_manager"},
        "depends_on_step_keys": ["step_a"],
      },
    ],
  )

  instantiation = await task_template_service.instantiate_template(
    actor=requester,
    template_id=template.id,
    payload={"department_id": str(department.id), "amount": 50000},
  )
  initial_tasks = instantiation.tasks
  assert len(initial_tasks) == 1
  step_a_task = initial_tasks[0]
  assert step_a_task.extra_metadata.get("template_step_key") == "step_a"

  for target_status in [TaskStatus.DOING, TaskStatus.REVIEW, TaskStatus.DONE]:
    await task_service.transition_task_status(
      actor=requester,
      task_id=step_a_task.id,
      target_status=target_status,
    )

  all_tasks = await task_service.list_tasks(actor=admin)
  activated_step_keys = {
    task.extra_metadata.get("template_step_key")
    for task in all_tasks
    if task.extra_metadata.get("template_id") == str(template.id)
    and task.id != step_a_task.id
  }

  assert "step_b" in activated_step_keys
  assert "step_c" not in activated_step_keys


@LEGACY_E_REMOVED
@pytest.mark.asyncio
async def test_phase11a_routing_rules_else_fallback_activates_when_no_condition_matches(db_session) -> None:
  """步骤 A 配置 routing_rules（条件 amount > 10000 -> step_b，else -> step_c）:
  当 instance.payload.amount == 3000 时（不满足条件），
  步骤 A 完成后应通过 ELSE 规则激活 step_c 而非 step_b。
  """
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

  manager = await user_service.create_user(
    actor=admin,
    email="manager@routing-else.example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  requester = await user_service.create_user(
    actor=admin,
    email="requester@routing-else.example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="路由 ELSE 测试部",
    code="routing-else-dept",
    manager_id=manager.id,
    capabilities=[DepartmentCapability.PUBLISH_ORG_TASK],
  )
  for user_id, employee_no, real_name in [
    (manager.id, "EMP-RR-ELSE-MGR", "路由 ELSE 主管"),
    (requester.id, "EMP-RR-ELSE-REQ", "路由 ELSE 发起人"),
  ]:
    await profile_service.create_profile(
      actor=admin,
      user_id=user_id,
      employee_no=employee_no,
      real_name=real_name,
      department_id=department.id,
    )

  notification_service = NotificationService(db_session, InMemoryQueuePublisher())
  task_service = TaskService(db_session, notification_service)
  task_template_service = TaskTemplateService(db_session, task_service, notification_service)

  routing_rules = [
    {
      "condition": {"field": "amount", "operator": "gt", "value": 10000},
      "target_step_key": "step_b",
    },
    {"else": True, "target_step_key": "step_c"},
  ]

  template = await task_template_service.create_template(
    actor=admin,
    code="routing-rules-else-test",
    name="路由 ELSE 测试模板",
    category="ops",
    steps=[
      {
        "step_key": "step_a",
        "title": "申请提交",
        "default_assignee_rule": {"type": "initiator"},
        "config": {"routing_rules": routing_rules},
      },
      {
        "step_key": "step_b",
        "title": "大额审批",
        "default_assignee_rule": {"type": "department_manager"},
        "depends_on_step_keys": ["step_a"],
      },
      {
        "step_key": "step_c",
        "title": "普通确认",
        "default_assignee_rule": {"type": "department_manager"},
        "depends_on_step_keys": ["step_a"],
      },
    ],
  )

  instantiation = await task_template_service.instantiate_template(
    actor=requester,
    template_id=template.id,
    payload={"department_id": str(department.id), "amount": 3000},
  )
  initial_tasks = instantiation.tasks
  step_a_task = initial_tasks[0]

  for target_status in [TaskStatus.DOING, TaskStatus.REVIEW, TaskStatus.DONE]:
    await task_service.transition_task_status(
      actor=requester,
      task_id=step_a_task.id,
      target_status=target_status,
    )

  all_tasks = await task_service.list_tasks(actor=admin)
  activated_step_keys = {
    task.extra_metadata.get("template_step_key")
    for task in all_tasks
    if task.extra_metadata.get("template_id") == str(template.id)
    and task.id != step_a_task.id
  }

  assert "step_c" in activated_step_keys
  assert "step_b" not in activated_step_keys


@pytest.mark.asyncio
async def test_phase11b_takeover_node_instance_reassigns_and_notifies_previous_assignee(db_session) -> None:
  from app.core.enums import WorkflowGraphTemplateStatus
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  previous_assignee = await user_service.create_user(
    actor=admin,
    email="phase11b-prev@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  next_assignee = await user_service.create_user(
    actor=admin,
    email="phase11b-next@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  template = WorkflowGraphTemplate(
    code="phase11b-takeover-test",
    base_code="phase11b-takeover-test",
    version=1,
    name="Phase11B 接管测试模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="node-a",
    title="待接管节点",
    sort_order=1,
  )
  db_session.add(node)
  await db_session.flush()

  queue = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, queue)
  wg_service = WorkflowGraphService(db_session, notification_service=notification_service)
  result = await wg_service.create_multi_node_instance(
    template_id=template.id,
    initiator_id=admin.id,
  )

  node_instance = result.node_instances[0]
  node_instance.assignee_user_id = previous_assignee.id
  await db_session.flush()

  instance_id = await wg_service.takeover_node_instance(
    node_instance_id=node_instance.id,
    actor_id=admin.id,
    actor_role=UserRole.ADMIN,
    assignee_id=next_assignee.id,
    reason="人员离岗",
  )

  await db_session.refresh(node_instance)

  assert instance_id == result.instance.id
  assert node_instance.assignee_user_id == next_assignee.id
  assert node_instance.engine_state == WorkflowNodeEngineState.ACTIVATED
  assert node_instance.business_state == WorkflowNodeBusinessState.ASSIGNED
  assert node_instance.node_instance_version == 2
  assert node_instance.config["takeover"]["reason"] == "人员离岗"
  assert node_instance.config["takeover"]["from_assignee_user_id"] == str(previous_assignee.id)
  assert node_instance.config["takeover"]["to_assignee_user_id"] == str(next_assignee.id)
  # Phase 11-C: 通知改为写 outbox event，而非直接推队列
  from sqlalchemy import select as _select
  from app.models.workflow_graph import WorkflowOutboxEvent
  from app.core.enums import WorkflowOutboxEventStatus
  outbox_events = list(
    await db_session.scalars(
      _select(WorkflowOutboxEvent)
      .where(WorkflowOutboxEvent.instance_id == result.instance.id)
      .where(WorkflowOutboxEvent.event_type == "workflow_node_taken_over")
    )
  )
  assert len(outbox_events) == 1
  assert outbox_events[0].status == WorkflowOutboxEventStatus.PENDING
  assert outbox_events[0].payload["reason"] == "人员离岗"


@pytest.mark.asyncio
async def test_phase11b_takeover_node_instance_requires_admin_role(db_session) -> None:
  from app.core.enums import WorkflowGraphTemplateStatus
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  employee = await user_service.create_user(
    actor=admin,
    email="phase11b-employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  next_assignee = await user_service.create_user(
    actor=admin,
    email="phase11b-next2@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  template = WorkflowGraphTemplate(
    code="phase11b-authz-test",
    base_code="phase11b-authz-test",
    version=1,
    name="Phase11B 权限测试模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="node-a",
    title="待接管节点",
    sort_order=1,
  )
  db_session.add(node)
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(
    template_id=template.id,
    initiator_id=admin.id,
  )
  node_instance = result.node_instances[0]
  node_instance.assignee_user_id = employee.id
  await db_session.flush()

  with pytest.raises(AuthorizationError, match="仅管理员"):
    await wg_service.takeover_node_instance(
      node_instance_id=node_instance.id,
      actor_id=employee.id,
      actor_role=UserRole.EMPLOYEE,
      assignee_id=next_assignee.id,
      reason="越权接管",
    )


@pytest.mark.asyncio
async def test_phase11d_takeover_syncs_manual_task_projection_for_new_assignee(db_session) -> None:
  settings = Settings(
    jwt_secret_key=TEST_JWT_SECRET,
    workflow_graph_engine_enabled=True,
  )
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  workflow_graph_service = WorkflowGraphService(db_session)
  task_service = TaskService(
    db_session,
    NotificationService(db_session, InMemoryQueuePublisher()),
    settings=settings,
    workflow_graph_service=workflow_graph_service,
  )

  previous_assignee = await user_service.create_user(
    actor=admin,
    email="phase11d-old@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  next_assignee = await user_service.create_user(
    actor=admin,
    email="phase11d-new@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  admin_profile = await profile_service.get_profile(actor=admin, user_id=admin.id)
  await profile_service.create_profile(
    actor=admin,
    user_id=previous_assignee.id,
    employee_no="EMP-011D-OLD",
    real_name="原执行人",
    department_id=admin_profile.department_id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=next_assignee.id,
    employee_no="EMP-011D-NEW",
    real_name="新执行人",
    department_id=admin_profile.department_id,
  )

  task = await task_service.create_task(
    actor=admin,
    title="待管理员接管的图任务",
    assignee_id=previous_assignee.id,
  )
  instance = await db_session.scalar(
    select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == task.id)
  )
  assert instance is not None
  node_instance = await db_session.scalar(
    select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == instance.id)
  )
  assert node_instance is not None

  await workflow_graph_service.takeover_node_instance(
    node_instance_id=node_instance.id,
    actor_id=admin.id,
    actor_role=UserRole.ADMIN,
    assignee_id=next_assignee.id,
    reason="原执行人离岗",
  )
  await db_session.refresh(task)

  previous_inbox = (await task_service.list_task_inbox(actor=previous_assignee)).items
  next_inbox = (await task_service.list_task_inbox(actor=next_assignee)).items

  assert task.assignee_id == next_assignee.id
  assert task.status == TaskStatus.TODO
  assert task.extra_metadata["workflow_handshake_state"] == "assigned"
  assert task.extra_metadata["latest_handshake_action"] == "takeover"
  assert task.extra_metadata["latest_takeover_reason"] == "原执行人离岗"
  assert all(entry.task_id != task.id for entry in previous_inbox)
  assert any(
    entry.task_id == task.id and entry.current_stage_label.endswith("：管理员接管待确认")
    for entry in next_inbox
  )


@pytest.mark.asyncio
async def test_phase11d_delegate_blocks_when_graph_node_is_terminated(db_session) -> None:
  settings = Settings(
    jwt_secret_key=TEST_JWT_SECRET,
    workflow_graph_engine_enabled=True,
  )
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  task_service = TaskService(
    db_session,
    NotificationService(db_session, InMemoryQueuePublisher()),
    settings=settings,
    workflow_graph_service=WorkflowGraphService(db_session),
  )

  employee = await user_service.create_user(
    actor=admin,
    email="phase11d-terminated-owner@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  delegate_target = await user_service.create_user(
    actor=admin,
    email="phase11d-terminated-delegate@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  admin_profile = await profile_service.get_profile(actor=admin, user_id=admin.id)
  for user_id, employee_no, real_name in [
    (employee.id, "EMP-011D-T1", "原执行人"),
    (delegate_target.id, "EMP-011D-T2", "新执行人"),
  ]:
    await profile_service.create_profile(
      actor=admin,
      user_id=user_id,
      employee_no=employee_no,
      real_name=real_name,
      department_id=admin_profile.department_id,
    )

  task = await task_service.create_task(
    actor=admin,
    title="已失效图节点的手动任务",
    assignee_id=employee.id,
  )
  instance = await db_session.scalar(
    select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == task.id)
  )
  assert instance is not None
  node_instance = await db_session.scalar(
    select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == instance.id)
  )
  assert node_instance is not None

  node_instance.engine_state = WorkflowNodeEngineState.TERMINATED
  node_instance.business_state = WorkflowNodeBusinessState.CANCELLED
  node_instance.terminated_at = datetime.now(UTC)
  await db_session.flush()

  with pytest.raises(ConflictError, match="图节点已失效"):
    await task_service.delegate_task_assignment(
      actor=employee,
      task_id=task.id,
      assignee_id=delegate_target.id,
      reason="尝试复活失效节点",
    )


@pytest.mark.asyncio
async def test_phase11d_accept_blocks_when_graph_node_is_terminated(db_session) -> None:
  settings = Settings(
    jwt_secret_key=TEST_JWT_SECRET,
    workflow_graph_engine_enabled=True,
  )
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  task_service = TaskService(
    db_session,
    NotificationService(db_session, InMemoryQueuePublisher()),
    settings=settings,
    workflow_graph_service=WorkflowGraphService(db_session),
  )

  employee = await user_service.create_user(
    actor=admin,
    email="phase11d-accept-owner@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  admin_profile = await profile_service.get_profile(actor=admin, user_id=admin.id)
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-011D-A1",
    real_name="待确认执行人",
    department_id=admin_profile.department_id,
  )

  task = await task_service.create_task(
    actor=admin,
    title="已失效图节点的待确认任务",
    assignee_id=employee.id,
  )
  instance = await db_session.scalar(
    select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == task.id)
  )
  assert instance is not None
  node_instance = await db_session.scalar(
    select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == instance.id)
  )
  assert node_instance is not None

  node_instance.engine_state = WorkflowNodeEngineState.TERMINATED
  node_instance.business_state = WorkflowNodeBusinessState.CANCELLED
  node_instance.terminated_at = datetime.now(UTC)
  await db_session.flush()

  with pytest.raises(ConflictError, match="图节点已失效"):
    await task_service.accept_task_assignment(
      actor=employee,
      task_id=task.id,
    )


@pytest.mark.asyncio
async def test_phase11d_reject_blocks_when_graph_instance_is_completed(db_session) -> None:
  settings = Settings(
    jwt_secret_key=TEST_JWT_SECRET,
    workflow_graph_engine_enabled=True,
  )
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  task_service = TaskService(
    db_session,
    NotificationService(db_session, InMemoryQueuePublisher()),
    settings=settings,
    workflow_graph_service=WorkflowGraphService(db_session),
  )

  employee = await user_service.create_user(
    actor=admin,
    email="phase11d-reject-owner@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  admin_profile = await profile_service.get_profile(actor=admin, user_id=admin.id)
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-011D-R1",
    real_name="待协商执行人",
    department_id=admin_profile.department_id,
  )

  task = await task_service.create_task(
    actor=admin,
    title="实例已结束的图任务",
    assignee_id=employee.id,
  )
  instance = await db_session.scalar(
    select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == task.id)
  )
  assert instance is not None

  instance.status = WorkflowGraphInstanceStatus.COMPLETED
  instance.completed_at = datetime.now(UTC)
  instance.current_node_key = None
  await db_session.flush()

  with pytest.raises(ConflictError, match="图实例已结束"):
    await task_service.reject_task_assignment(
      actor=employee,
      task_id=task.id,
      reason="实例已结束后不应允许协商",
    )


@pytest.mark.asyncio
async def test_phase11d_takeover_blocks_when_node_is_completed(db_session) -> None:
  from app.core.enums import WorkflowGraphTemplateStatus
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  previous_assignee = await user_service.create_user(
    actor=admin,
    email="phase11d-takeover-old@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  next_assignee = await user_service.create_user(
    actor=admin,
    email="phase11d-takeover-new@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  template = WorkflowGraphTemplate(
    code="phase11d-takeover-completed",
    base_code="phase11d-takeover-completed",
    version=1,
    name="Phase11D 接管失效节点测试模板",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="node-a",
    title="已结束节点",
    sort_order=1,
  )
  db_session.add(node)
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(
    template_id=template.id,
    initiator_id=admin.id,
  )
  node_instance = result.node_instances[0]
  node_instance.assignee_user_id = previous_assignee.id
  node_instance.engine_state = WorkflowNodeEngineState.COMPLETED
  node_instance.business_state = WorkflowNodeBusinessState.DONE
  node_instance.completed_at = datetime.now(UTC)
  await db_session.flush()

  with pytest.raises(ConflictError, match="ACTIVATED/ACKNOWLEDGED"):
    await wg_service.takeover_node_instance(
      node_instance_id=node_instance.id,
      actor_id=admin.id,
      actor_role=UserRole.ADMIN,
      assignee_id=next_assignee.id,
      reason="尝试接管已结束节点",
    )


@pytest.mark.asyncio
async def test_phase11d_deep_reject_blocks_replay_from_stale_node_after_clone(db_session) -> None:
  from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode
  from app.core.enums import WorkflowGraphTemplateStatus

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  template = WorkflowGraphTemplate(
    code="phase11d-deep-reject-replay-block",
    base_code="phase11d-deep-reject-replay-block",
    version=1,
    name="Phase 11-D 深度打回重放阻断测试",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()

  node_a = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-a", title="节点 A", sort_order=1)
  node_b = WorkflowGraphTemplateNode(template_id=template.id, node_key="node-b", title="节点 B", sort_order=2)
  db_session.add_all([node_a, node_b])
  await db_session.flush()

  db_session.add(
    WorkflowGraphTemplateEdge(template_id=template.id, from_node_id=node_a.id, to_node_id=node_b.id)
  )
  await db_session.flush()

  wg_service = WorkflowGraphService(db_session)
  result = await wg_service.create_multi_node_instance(template_id=template.id, initiator_id=admin.id)
  node_a_instance = next(ni for ni in result.node_instances if ni.node_key == "node-a")
  node_b_instance = next(ni for ni in result.node_instances if ni.node_key == "node-b")

  await wg_service.complete_node_instance(node_instance_id=node_a_instance.id, actor_id=admin.id)
  await wg_service.deep_reject_to_upstream(
    node_instance_id=node_b_instance.id,
    actor_id=admin.id,
    target_node_key="node-a",
    reason="第一次深度打回",
  )

  with pytest.raises(ConflictError, match="ACTIVATED/ACKNOWLEDGED"):
    await wg_service.deep_reject_to_upstream(
      node_instance_id=node_b_instance.id,
      actor_id=admin.id,
      target_node_key="node-a",
      reason="旧节点不应允许再次深度打回",
    )


@pytest.mark.asyncio
async def test_phase11e_migrate_legacy_tasks_creates_graph_projection_and_deliverable_snapshot(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )
  user_service = UserService(db_session)
  assignee = await user_service.create_user(
    actor=admin,
    email="phase11e-owner@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  manual_task = Task(
    title="历史手动任务",
    description="未接入 graph 的旧任务",
    creator_id=admin.id,
    assignee_id=assignee.id,
    source_type=TaskSourceType.MANUAL,
    status=TaskStatus.TODO,
    priority=TaskPriority.MEDIUM,
    extra_metadata={},
  )
  db_session.add(manual_task)
  await db_session.flush()

  template_task = await _create_legacy_template_backed_task(
    db_session=db_session,
    admin=admin,
    assignee=assignee,
  )

  service = LegacyTaskGraphMigrationService(db_session)
  dry_run_result = await service.migrate_tasks(batch_id="phase11e-dry-run", dry_run=True)
  assert dry_run_result.eligible_count == 2
  assert dry_run_result.migrated_count == 0
  assert await db_session.scalar(select(func.count(WorkflowGraphInstance.id))) == 0

  result = await service.migrate_tasks(batch_id="phase11e-batch")
  await db_session.flush()

  assert result.migrated_count == 2
  assert result.deliverable_count == 1

  manual_instance = await db_session.scalar(
    select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == manual_task.id)
  )
  assert manual_instance is not None
  manual_node = await db_session.scalar(
    select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == manual_instance.id)
  )
  assert manual_node is not None
  assert manual_node.engine_state == WorkflowNodeEngineState.ACKNOWLEDGED
  assert manual_node.business_state == WorkflowNodeBusinessState.ACCEPTED
  assert manual_task.extra_metadata["workflow_graph_instance_id"] == str(manual_instance.id)
  assert manual_task.extra_metadata["legacy_graph_migration_batch_id"] == "phase11e-batch"

  template_instance = await db_session.scalar(
    select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == template_task.id)
  )
  assert template_instance is not None
  template_node = await db_session.scalar(
    select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == template_instance.id)
  )
  assert template_node is not None
  assert template_node.business_state == WorkflowNodeBusinessState.PENDING_REVIEW
  assert template_node.config["template_step_run_id"] == str(template_task.template_step_run_id)

  deliverable = await db_session.scalar(
    select(WorkflowDeliverable).where(WorkflowDeliverable.node_instance_id == template_node.id)
  )
  assert deliverable is not None
  assert deliverable.summary == "历史交付说明"
  assert deliverable.payload["latest_review"]["action"] == "pending_review"


@pytest.mark.asyncio
async def test_phase11e_rollback_removes_graph_projection_and_restores_task_metadata(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )
  user_service = UserService(db_session)
  assignee = await user_service.create_user(
    actor=admin,
    email="phase11e-rollback@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  task = Task(
    title="待回滚的旧任务",
    description="用于验证 rollback",
    creator_id=admin.id,
    assignee_id=assignee.id,
    source_type=TaskSourceType.MANUAL,
    status=TaskStatus.DOING,
    priority=TaskPriority.HIGH,
    extra_metadata={},
  )
  db_session.add(task)
  await db_session.flush()

  service = LegacyTaskGraphMigrationService(db_session)
  migrate_result = await service.migrate_tasks(batch_id="phase11e-rollback-batch")
  assert migrate_result.migrated_count == 1

  rollback_preview = await service.rollback_batch(batch_id="phase11e-rollback-batch", dry_run=True)
  assert rollback_preview.matched_instance_count == 1
  assert rollback_preview.deleted_instance_count == 0

  rollback_result = await service.rollback_batch(batch_id="phase11e-rollback-batch")
  await db_session.flush()

  assert rollback_result.deleted_instance_count == 1
  assert rollback_result.restored_task_count == 1
  assert await db_session.scalar(select(func.count(WorkflowGraphInstance.id))) == 0

  await db_session.refresh(task)
  assert "workflow_graph_instance_id" not in task.extra_metadata
  assert "workflow_node_instance_id" not in task.extra_metadata
  assert "legacy_graph_migration_batch_id" not in task.extra_metadata


@pytest.mark.asyncio
async def test_phase11f_task_center_v2_routes_migrated_review_task_to_creator_inbox(db_session) -> None:
  base_settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, base_settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )
  user_service = UserService(db_session)
  assignee = await user_service.create_user(
    actor=admin,
    email="phase11f-review-owner@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  task = await _create_legacy_template_backed_task(
    db_session=db_session,
    admin=admin,
    assignee=assignee,
  )
  migration_service = LegacyTaskGraphMigrationService(db_session)
  migrate_result = await migration_service.migrate_tasks(batch_id="phase11f-batch")
  assert migrate_result.migrated_count == 1

  legacy_task_service = TaskService(
    db_session,
    NotificationService(db_session, InMemoryQueuePublisher()),
    settings=Settings(jwt_secret_key=TEST_JWT_SECRET, task_center_v2_enabled=False),
  )
  graph_first_task_service = TaskService(
    db_session,
    NotificationService(db_session, InMemoryQueuePublisher()),
    settings=Settings(jwt_secret_key=TEST_JWT_SECRET, task_center_v2_enabled=True),
  )

  creator_inbox_legacy = (await legacy_task_service.list_task_inbox(actor=admin)).items
  assignee_inbox_legacy = (await legacy_task_service.list_task_inbox(actor=assignee)).items
  creator_inbox_graph = (await graph_first_task_service.list_task_inbox(actor=admin)).items
  assignee_inbox_graph = (await graph_first_task_service.list_task_inbox(actor=assignee)).items
  assignee_tracking_graph = (await graph_first_task_service.list_task_tracking(actor=assignee)).items

  assert all(entry.task_id != task.id for entry in creator_inbox_legacy)
  assert any(entry.task_id == task.id for entry in assignee_inbox_legacy)
  assert any(
    entry.task_id == task.id and entry.current_stage_label.endswith("：待验收")
    for entry in creator_inbox_graph
  )
  assert all(entry.task_id != task.id for entry in assignee_inbox_graph)
  tracked_item = next(item for item in assignee_tracking_graph if item.task_id == task.id)
  assert tracked_item.current_stage_label.endswith("：待验收")
  assert tracked_item.current_handler_label.startswith("管理员")
  assert tracked_item.is_pending_review is True


@pytest.mark.asyncio
async def test_phase11f_task_center_v2_history_prefers_graph_completed_state(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )
  user_service = UserService(db_session)
  assignee = await user_service.create_user(
    actor=admin,
    email="phase11f-history-owner@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  task = await _create_legacy_template_backed_task(
    db_session=db_session,
    admin=admin,
    assignee=assignee,
  )
  migration_service = LegacyTaskGraphMigrationService(db_session)
  migrate_result = await migration_service.migrate_tasks(batch_id="phase11f-history-batch")
  assert migrate_result.migrated_count == 1

  instance = await db_session.scalar(
    select(WorkflowGraphInstance).where(WorkflowGraphInstance.source_id == task.id)
  )
  assert instance is not None
  node_instance = await db_session.scalar(
    select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == instance.id)
  )
  assert node_instance is not None

  completed_at = datetime.now(UTC)
  instance.status = WorkflowGraphInstanceStatus.COMPLETED
  instance.current_node_key = None
  instance.completed_at = completed_at
  node_instance.engine_state = WorkflowNodeEngineState.COMPLETED
  node_instance.business_state = WorkflowNodeBusinessState.DONE
  node_instance.completed_at = completed_at
  task.status = TaskStatus.REVIEW
  task.completed_at = None
  await db_session.flush()

  legacy_task_service = TaskService(
    db_session,
    NotificationService(db_session, InMemoryQueuePublisher()),
    settings=Settings(jwt_secret_key=TEST_JWT_SECRET, task_center_v2_enabled=False),
  )
  graph_first_task_service = TaskService(
    db_session,
    NotificationService(db_session, InMemoryQueuePublisher()),
    settings=Settings(jwt_secret_key=TEST_JWT_SECRET, task_center_v2_enabled=True),
  )

  legacy_history = (await legacy_task_service.list_task_history(actor=admin)).items
  graph_history = (await graph_first_task_service.list_task_history(actor=admin)).items

  assert all(entry.task_id != task.id for entry in legacy_history)
  migrated_entry = next(entry for entry in graph_history if entry.task_id == task.id)
  assert migrated_entry.completed_at == completed_at
  assert "流程" in migrated_entry.relation_types
