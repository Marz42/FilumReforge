from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest
from sqlalchemy import select

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
  PushSubscriptionStatus,
  PositionAssignmentType,
  ReportingLineType,
  TaskActionType,
  TaskStatus,
  UserRole,
  UserStatus,
  WorkflowDefinitionStatus,
  WorkflowInstanceStatus,
)
from app.core.exceptions import AuthorizationError, ConflictError
from app.models import AttachmentLink, NotificationDelivery, NotificationMessage as NotificationMessageModel, TaskDependency, TaskLog, User
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
from app.services.hr_lifecycle_service import HRLifecycleService
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.llm_router_service import LLMRouterService
from app.services.message_center_service import MessageCenterService
from app.services.notification_service import NotificationService
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
from app.services.workflow_engine_service import WorkflowEngineService


class InMemoryQueuePublisher:
  def __init__(self) -> None:
    self.payloads: list[dict[str, str]] = []

  async def publish(self, payload):  # noqa: ANN001
    self.payloads.append(payload)


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
  access_user = await auth_service.get_user_from_access_token(session.access_token)

  assert admin.role == UserRole.ADMIN
  assert session.token_type == "bearer"
  assert refreshed.access_token != session.access_token
  assert access_user.id == admin.id


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
  await user_service.create_user(
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
  assert detail.actions["can_create_profile"] is False
  assert detail.primary_manager_label == "技术负责人"
  assert detail.latest_employment_event is not None
  assert detail.latest_employment_event.event_type == EmploymentEventType.PROMOTION


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
      content=b"pdf-content",
      target_type=AttachmentTargetType.TASK,
      target_id=admin.id,
    )
    deleted = await attachment_service.delete_attachment(actor=admin, attachment_id=attachment.id)

    file_path = Path(tmp_dir) / "filum-test" / attachment.object_key
    assert attachment.original_filename == "spec.pdf"
    assert deleted.status == AttachmentStatus.DELETED
    assert not file_path.exists()


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

  inbox = await task_service.list_task_inbox(actor=employee)
  tracking = await task_service.list_task_tracking(actor=employee)

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
  task_template_service = TaskTemplateService(db_session, task_service, notification_service)
  task_memo_service = TaskMemoService(db_session, task_service)

  template = await task_template_service.create_template(
    actor=manager,
    code="content-publish",
    name="内容发布",
    category="ops",
    steps=[
      {
        "step_key": "draft",
        "title": "内容整理",
        "default_assignee_rule": {"type": "initiator"},
      }
    ],
  )
  with pytest.raises(AuthorizationError):
    await task_template_service.create_template(
      actor=employee,
      code="forbidden-template",
      name="无权限模板",
      category="ops",
      steps=[
        {
          "step_key": "draft",
          "title": "草稿",
          "default_assignee_rule": {"type": "initiator"},
        }
      ],
    )

  tasks = await task_template_service.instantiate_template(
    actor=employee,
    template_id=template.id,
    payload={"department_id": str(department.id)},
  )
  created_task = tasks[0]
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

  history = await task_service.list_task_history(actor=employee)
  assert history[0].task_id == created_task.id
  assert "执行" in history[0].relation_types

  memo = await task_memo_service.create_memo(
    actor=employee,
    content="完成后同步到周报。",
    related_task_id=created_task.id,
    is_pinned=True,
  )
  updated_memo = await task_memo_service.update_memo(
    actor=employee,
    memo_id=memo.id,
    content="完成后同步到周报和群公告。",
  )
  memos = await task_memo_service.list_memos(actor=employee)

  assert updated_memo.related_task_id == created_task.id
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

  tasks = await task_template_service.instantiate_template(
    actor=requester,
    template_id=template.id,
    watcher_user_ids=[watcher.id],
    payload={"department_id": str(department.id)},
  )
  dependency_rows = list(
    await db_session.scalars(
      select(TaskDependency).where(TaskDependency.task_id == tasks[1].id)
    )
  )
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

  assert len(tasks) == 2
  assert tasks[0].source_type.value == "template"
  assert dependency_rows[0].depends_on_task_id == tasks[0].id
  assert [watcher_binding.user_id for watcher_binding in watchers] == [watcher.id]
  assert len([message for message in watcher_messages if message.message_type == "task_cc_added"]) == 2
  assert read_receipt.id == idempotent_receipt.id
  assert executed_count == 1
  assert len(all_tasks) == 4
  assert schedule.next_run_at is not None


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
      content=b"document-attachment",
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

  assert slash_result.mode == "slash_command"
  assert slash_result.command_name == "profile"
  assert slash_result.tool_results[0]["tool_name"] == "get_profile_summary"
  assert "档案摘要" in slash_result.reply_text

  assert mention_result.mode == "mention"
  assert mention_result.tool_results
  assert mention_result.tool_results[0]["tool_name"] == "search_documents"
  assert "入职流程需要先提交材料" in mention_result.reply_text
  assert mention_result.knowledge_hits
