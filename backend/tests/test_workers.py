from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import json

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.enums import (
  DEFAULT_USER_NOTIFICATION_CHANNELS,
  DepartmentCapability,
  DocumentCategory,
  DocumentStatus,
  EmploymentEventType,
  NotificationChannel,
  NotificationDeliveryStatus,
  NotificationMessageStatus,
  WorkflowDefinitionStatus,
  WorkflowStepRunStatus,
  UserRole,
  UserStatus,
)
from app.models import BoardCard, BoardCardArchive, NotificationDelivery, NotificationMessage, Task, TaskSchedule
from app.models import DocumentEmbedding
from app.integrations.notifications.web_push import WebPushNotificationAdapter
from app.services.auth_service import AuthService
from app.services.browser_push_service import BrowserPushService
from app.services.department_service import DepartmentService
from app.services.document_service import DocumentService
from app.services.hr_lifecycle_service import HRLifecycleService, PROCESS_EMPLOYMENT_EVENT_JOB
from app.services.notification_service import NotificationService
from app.services.profile_service import ProfileService
from app.services.task_automation_service import TaskAutomationService
from app.services.task_service import TaskService
from app.services.task_template_service import TaskTemplateService
from app.services.user_service import UserService
from app.services.workflow_engine_service import WorkflowEngineService
from app.workers.jobs import (
  archive_expired_board_cards,
  enqueue_overdue_task_reminders,
  enqueue_pending_workflow_reminders,
  process_employment_event_automation,
  process_notification_message_payload,
  rebuild_all_document_embeddings,
  rebuild_document_embeddings,
  run_due_task_schedules,
)
from app.schemas.messages import NotificationMessage as NotificationMessageSchema


class InMemoryQueuePublisher:
  def __init__(self) -> None:
    self.payloads: list[dict[str, object]] = []
    self.jobs: list[tuple[str, tuple[object, ...]]] = []

  async def publish(self, payload: dict[str, object]) -> None:
    self.payloads.append(payload)

  async def enqueue(self, job_name: str, *args: object) -> None:
    self.jobs.append((job_name, args))


class FakeOpenAIClient:
  async def create_embeddings(self, *, inputs, model=None):  # noqa: ANN001
    return [
      [float(index + 1), float(len(str(text))), 1.0]
      for index, text in enumerate(inputs)
    ]


class FakeWebPushSender:
  def __init__(self) -> None:
    self.payloads: list[dict[str, object]] = []

  def __call__(
    self,
    *,
    subscription_info: dict[str, object],
    data: str,
    vapid_private_key: str,
    vapid_claims: dict[str, str],
  ) -> None:
    self.payloads.append(
      {
        "subscription_info": subscription_info,
        "data": data,
        "vapid_private_key": vapid_private_key,
        "vapid_claims": vapid_claims,
      }
    )


TEST_JWT_SECRET = "test-secret-key-with-32-bytes-minimum!!"


@pytest.mark.asyncio
async def test_process_notification_message_payload_marks_deliveries_sent(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  queue_publisher = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, queue_publisher)
  message = await notification_service.send(
    NotificationMessageSchema(
      source_type="task",
      source_id=admin.id,
      recipient_user_id=admin.id,
      recipient_email=admin.email,
      message_type="task_assigned",
      title="收到任务",
      body_text="请处理任务。",
      channels=[NotificationChannel.EMAIL, NotificationChannel.WEBSOCKET],
    )
  )
  processed_message = await process_notification_message_payload(
    session=db_session,
    payload=queue_publisher.payloads[0],
  )
  deliveries = list(
    await db_session.scalars(
      select(NotificationDelivery)
      .where(NotificationDelivery.message_id == message.id)
      .order_by(NotificationDelivery.created_at.asc())
    )
  )

  assert processed_message is not None
  assert processed_message.status == NotificationMessageStatus.COMPLETED
  assert len(deliveries) == 2
  assert all(delivery.status == NotificationDeliveryStatus.SENT for delivery in deliveries)
  assert all(delivery.attempt_count == 1 for delivery in deliveries)


@pytest.mark.asyncio
async def test_enqueue_overdue_task_reminders_is_idempotent(db_session) -> None:
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
  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="研发部",
    code="engineering",
    manager_id=admin.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-001",
    real_name="研发工程师",
    department_id=department.id,
  )
  push_service = BrowserPushService(db_session)
  await push_service.upsert_subscription(
    actor=employee,
    endpoint="https://push.example.com/subscriptions/overdue",
    p256dh_key="p256dh",
    auth_key="auth",
    user_agent="Mozilla/5.0",
  )

  task_service = TaskService(db_session)
  overdue_task = await task_service.create_task(
    actor=admin,
    title="补发逾期提醒",
    assignee_id=employee.id,
    department_id=department.id,
    due_date=datetime.now(UTC) - timedelta(hours=2),
  )

  queue_publisher = InMemoryQueuePublisher()
  first_created_count = await enqueue_overdue_task_reminders(
    session=db_session,
    queue_publisher=queue_publisher,
  )
  second_created_count = await enqueue_overdue_task_reminders(
    session=db_session,
    queue_publisher=queue_publisher,
  )
  reminder_count = await db_session.scalar(
    select(func.count(NotificationMessage.id)).where(
      NotificationMessage.source_id == overdue_task.id,
      NotificationMessage.message_type == "task_overdue_reminder",
    )
  )
  employee_message = await db_session.scalar(
    select(NotificationMessage).where(
      NotificationMessage.source_id == overdue_task.id,
      NotificationMessage.message_type == "task_overdue_reminder",
      NotificationMessage.recipient_user_id == employee.id,
    )
  )
  manager_message = await db_session.scalar(
    select(NotificationMessage).where(
      NotificationMessage.source_id == overdue_task.id,
      NotificationMessage.message_type == "task_overdue_reminder",
      NotificationMessage.recipient_user_id == admin.id,
    )
  )
  assert employee_message is not None
  assert manager_message is not None
  employee_deliveries = list(
    await db_session.scalars(
      select(NotificationDelivery)
      .where(NotificationDelivery.message_id == employee_message.id)
      .order_by(NotificationDelivery.created_at.asc())
    )
  )
  manager_deliveries = list(
    await db_session.scalars(
      select(NotificationDelivery)
      .where(NotificationDelivery.message_id == manager_message.id)
      .order_by(NotificationDelivery.created_at.asc())
    )
  )

  assert first_created_count == 2
  assert second_created_count == 0
  assert reminder_count == 2
  assert len(queue_publisher.payloads) == 2
  assert {delivery.channel for delivery in employee_deliveries} == set(DEFAULT_USER_NOTIFICATION_CHANNELS)
  assert {delivery.channel for delivery in manager_deliveries} == {
    NotificationChannel.WEBSOCKET,
    NotificationChannel.EMAIL,
  }


@pytest.mark.asyncio
async def test_run_due_task_schedules_creates_tasks_and_recomputes_next_run(db_session) -> None:
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
    employee_no="EMP-SCHEDULE-001",
    real_name="调度员工",
    department_id=admin_profile.department_id,
  )

  queue_publisher = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, queue_publisher)
  task_service = TaskService(db_session, notification_service)
  task_template_service = TaskTemplateService(db_session, task_service, notification_service)
  task_automation_service = TaskAutomationService(db_session, task_template_service)

  template = await task_template_service.create_template(
    actor=admin,
    code="scheduled-template",
    name="周期模板",
    category="ops",
    steps=[
      {
        "step_key": "scheduled-task",
        "title": "执行巡检",
        "default_assignee_rule": {"type": "user", "user_id": str(employee.id)},
      }
    ],
  )
  schedule = await task_automation_service.create_schedule(
    actor=admin,
    template_id=template.id,
    cron_expr="*/5 * * * *",
    payload={"department_id": str(admin_profile.department_id)},
  )
  schedule.next_run_at = datetime.now(UTC) - timedelta(minutes=1)
  await db_session.commit()

  executed_count = await run_due_task_schedules(
    session=db_session,
    queue_publisher=queue_publisher,
  )
  tasks = await task_service.list_tasks(actor=admin)
  refreshed_schedule = await db_session.get(TaskSchedule, schedule.id)

  assert executed_count == 1
  assert len(tasks) == 1
  assert tasks[0].source_type.value == "template"
  assert refreshed_schedule is not None and refreshed_schedule.next_run_at is not None
  assert refreshed_schedule.last_run_status == "success"
  assert refreshed_schedule.last_run_task_count == 1
  assert refreshed_schedule.last_run_message is not None
  assert len(queue_publisher.payloads) >= 1


@pytest.mark.asyncio
async def test_run_due_task_schedules_records_failure_state(db_session) -> None:
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
    employee_no="EMP-SCHEDULE-FAIL-001",
    real_name="调度员工",
    department_id=admin_profile.department_id,
  )

  queue_publisher = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, queue_publisher)
  task_service = TaskService(db_session, notification_service)
  task_template_service = TaskTemplateService(db_session, task_service, notification_service)
  task_automation_service = TaskAutomationService(db_session, task_template_service)

  template = await task_template_service.create_template(
    actor=admin,
    code="scheduled-template-failure",
    name="周期模板失败",
    category="ops",
    steps=[
      {
        "step_key": "scheduled-task",
        "title": "执行巡检",
        "default_assignee_rule": {"type": "user", "user_id": str(employee.id)},
      }
    ],
  )
  schedule = await task_automation_service.create_schedule(
    actor=admin,
    template_id=template.id,
    cron_expr="*/5 * * * *",
    payload={"department_id": str(admin_profile.department_id)},
  )
  schedule.next_run_at = datetime.now(UTC) - timedelta(minutes=1)
  admin.status = UserStatus.INACTIVE
  await db_session.commit()

  executed_count = await run_due_task_schedules(
    session=db_session,
    queue_publisher=queue_publisher,
  )
  refreshed_schedule = await db_session.get(TaskSchedule, schedule.id)
  task_count = await db_session.scalar(select(func.count(Task.id)))

  assert executed_count == 0
  assert refreshed_schedule is not None and refreshed_schedule.next_run_at is not None
  assert refreshed_schedule.last_run_status == "failed"
  assert refreshed_schedule.last_run_task_count == 0
  assert refreshed_schedule.last_run_message == "当前账号不可用。"
  assert task_count == 0


@pytest.mark.asyncio
async def test_archive_expired_board_cards_moves_cards_to_archive(db_session) -> None:
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
  department = await department_service.create_department(
    actor=admin,
    name="财务行政部",
    code="finance-admin",
    capabilities=[DepartmentCapability.PUBLISH_ANNOUNCEMENT],
  )
  await profile_service.update_profile(
    actor=admin,
    user_id=admin.id,
    department_id=department.id,
  )

  card = BoardCard(
    scope_department_id=department.id,
    author_user_id=admin.id,
    title="过期看板",
    content_md="需要归档。",
    expires_at=datetime.now(UTC) - timedelta(minutes=1),
  )
  db_session.add(card)
  await db_session.commit()

  archived_count = await archive_expired_board_cards(session=db_session)
  remaining_cards = list(await db_session.scalars(select(BoardCard)))
  archives = list(await db_session.scalars(select(BoardCardArchive)))

  assert archived_count == 1
  assert remaining_cards == []
  assert len(archives) == 1
  assert archives[0].title == "过期看板"


@pytest.mark.asyncio
async def test_enqueue_pending_workflow_reminders_is_idempotent(db_session) -> None:
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
    email="requester@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="提醒部",
    code="reminder-dept",
    manager_id=manager.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=manager.id,
    employee_no="EMP-MGR-003",
    real_name="提醒经理",
    department_id=department.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=requester.id,
    employee_no="EMP-REQ-003",
    real_name="提醒申请人",
    department_id=department.id,
  )

  queue_publisher = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, queue_publisher)
  workflow_engine_service = WorkflowEngineService(db_session, notification_service)
  definition = await workflow_engine_service.create_definition(
    actor=admin,
    code="expense-approval",
    name="报销审批",
    scope_type="expense",
    status=WorkflowDefinitionStatus.ACTIVE,
    steps=[
      {
        "step_key": "approve",
        "name": "经理审批",
        "step_type": "approval",
        "assignee_rule": {"type": "department_manager"},
        "config": {"reminder_after_hours": 1},
      }
    ],
  )
  instance = await workflow_engine_service.start_workflow(
    actor=requester,
    definition_id=definition.id,
    source_type="expense",
    payload={"department_id": str(department.id)},
  )
  queue_publisher.payloads.clear()
  pending_step_run = next(
    step_run
    for step_run in instance.step_runs
    if step_run.status == WorkflowStepRunStatus.PENDING
  )
  pending_step_run.created_at = datetime.now(UTC) - timedelta(hours=2)
  await db_session.commit()

  first_created_count = await enqueue_pending_workflow_reminders(
    session=db_session,
    queue_publisher=queue_publisher,
  )
  second_created_count = await enqueue_pending_workflow_reminders(
    session=db_session,
    queue_publisher=queue_publisher,
  )
  reminder_count = await db_session.scalar(
    select(func.count(NotificationMessage.id)).where(
      NotificationMessage.source_type == "workflow_step_run",
      NotificationMessage.source_id == pending_step_run.id,
      NotificationMessage.message_type == "workflow_pending_reminder",
    )
  )

  assert first_created_count == 1
  assert second_created_count == 0
  assert reminder_count == 1
  assert len(queue_publisher.payloads) == 1


@pytest.mark.asyncio
async def test_process_notification_message_payload_dispatches_web_push(db_session) -> None:
  settings = Settings(
    jwt_secret_key=TEST_JWT_SECRET,
    web_push_private_key="test-private-key",
    web_push_subject="mailto:test@example.com",
  )
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  push_service = BrowserPushService(db_session)
  await push_service.upsert_subscription(
    actor=admin,
    endpoint="https://push.example.com/subscriptions/worker",
    p256dh_key="p256dh",
    auth_key="auth",
    user_agent="Mozilla/5.0",
  )

  queue_publisher = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, queue_publisher)
  message = await notification_service.send(
    NotificationMessageSchema(
      source_type="knowledge",
      source_id=None,
      recipient_user_id=admin.id,
      recipient_email=admin.email,
      message_type="knowledge_published",
      title="知识库已更新",
      body_text="员工入职 SOP 已重新发布。",
      channels=[NotificationChannel.WEB_PUSH],
      payload={"document_slug": "employee-onboarding-sop"},
    )
  )

  fake_sender = FakeWebPushSender()
  adapter = WebPushNotificationAdapter(
    session=db_session,
    settings=settings,
    sender=fake_sender,
  )
  processed_message = await process_notification_message_payload(
    session=db_session,
    payload=queue_publisher.payloads[0],
    settings=settings,
    adapters={NotificationChannel.WEB_PUSH: adapter},
  )
  delivery = await db_session.scalar(
    select(NotificationDelivery).where(NotificationDelivery.message_id == message.id)
  )
  subscriptions = await push_service.list_subscriptions(actor=admin)

  assert processed_message is not None
  assert processed_message.status == NotificationMessageStatus.COMPLETED
  assert delivery is not None
  assert delivery.status == NotificationDeliveryStatus.SENT
  assert len(fake_sender.payloads) == 1
  assert json.loads(fake_sender.payloads[0]["data"])["message_type"] == "knowledge_published"
  assert subscriptions[0].last_seen_at is not None


@pytest.mark.asyncio
async def test_process_employment_event_automation_records_failure_and_requeues(db_session) -> None:
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
  task_service = TaskService(db_session, notification_service)
  task_template_service = TaskTemplateService(db_session, task_service, notification_service)
  workflow_engine_service = WorkflowEngineService(db_session, notification_service)
  lifecycle_service = HRLifecycleService(
    db_session,
    task_template_service=task_template_service,
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
    employee_no="EMP-WORKER-001",
    real_name="自动化失败员工",
    department_id=admin_profile.department_id,
  )

  broken_template = await task_template_service.create_template(
    actor=admin,
    code="broken-lifecycle-template",
    name="失效负责人模板",
    category="hr",
    steps=[
      {
        "step_key": "handover",
        "title": "办理交接",
        "default_assignee_rule": {"type": "user", "user_id": str(employee.id)},
      }
    ],
  )
  event = await lifecycle_service.create_event(
    actor=admin,
    user_id=employee.id,
    event_type=EmploymentEventType.OFFBOARD,
    effective_date=date(2025, 5, 2),
    title="办理离职",
    payload={"department_id": str(admin_profile.department_id)},
    task_template_id=broken_template.id,
  )

  queue_publisher.jobs.clear()
  processed = await process_employment_event_automation(
    session=db_session,
    event_id=event.id,
    queue_publisher=queue_publisher,
  )
  refreshed_event = await db_session.get(type(event), event.id)

  assert processed is False
  assert refreshed_event is not None
  assert refreshed_event.trigger_status.value == "failed"
  assert refreshed_event.trigger_attempt_count == 1
  assert refreshed_event.trigger_error == "当前账号不可用。"
  assert queue_publisher.jobs == [(PROCESS_EMPLOYMENT_EVENT_JOB, (str(event.id),))]


@pytest.mark.asyncio
async def test_rebuild_document_embedding_jobs_index_documents(db_session) -> None:
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
  onboarding_document = await document_service.create_document(
    actor=admin,
    title="员工入职 SOP",
    slug="employee-onboarding-sop",
    category=DocumentCategory.SOP,
    content_md="入职 提交材料 开通账号",
    status=DocumentStatus.PUBLISHED,
  )
  policy_document = await document_service.create_document(
    actor=admin,
    title="采购审批规范",
    slug="procurement-policy",
    category=DocumentCategory.POLICY,
    content_md="采购 审批 预算",
    status=DocumentStatus.DRAFT,
  )

  first_count = await rebuild_document_embeddings(
    session=db_session,
    document_id=onboarding_document.id,
    settings=settings,
    openai_client=FakeOpenAIClient(),
  )
  rebuilt_documents = await rebuild_all_document_embeddings(
    session=db_session,
    settings=settings,
    openai_client=FakeOpenAIClient(),
  )
  embedding_count = await db_session.scalar(select(func.count(DocumentEmbedding.id)))

  assert first_count >= 1
  assert rebuilt_documents == 2
  assert embedding_count is not None and embedding_count >= 2
