from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.exceptions import ConflictError
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
  WorkflowOutboxEventStatus,
  WorkflowStepRunStatus,
  UserRole,
  UserStatus,
)
from app.models import BoardCard, BoardCardArchive, NotificationDelivery, NotificationMessage, Task, TaskSchedule
from app.models import DocumentEmbedding
from app.models.base import Base
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
async def test_run_due_task_schedules_is_noop_after_b12(db_session) -> None:
  executed_count = await run_due_task_schedules(session=db_session)
  assert executed_count == 0


@pytest.mark.asyncio
async def test_run_due_task_schedules_records_failure_state(db_session) -> None:
  """Legacy schedule failure tracking removed with B-12; job remains a no-op."""
  executed_count = await run_due_task_schedules(session=db_session)
  assert executed_count == 0


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
    employee_no="EMP-WORKER-001",
    real_name="自动化失败员工",
    department_id=admin_profile.department_id,
  )

  with pytest.raises(ConflictError, match="B-12"):
    await lifecycle_service.create_event(
      actor=admin,
      user_id=employee.id,
      event_type=EmploymentEventType.OFFBOARD,
      effective_date=date(2025, 5, 2),
      title="办理离职",
      payload={"department_id": str(admin_profile.department_id)},
      task_template_id=employee.id,
    )


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


# ------------------------------------------------------------------ #
# Phase 11-C — Outbox Worker
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_phase11c_outbox_worker_dispatches_pending_event() -> None:
  """PENDING outbox 事件应被 worker 投递并标记为 DISPATCHED。"""
  from app.models.workflow_graph import WorkflowOutboxEvent
  from app.workers.workflow_outbox_worker import process_workflow_outbox_events

  engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
  )
  async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)

  session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

  # 创建基础测试数据：admin 用户、图实例、节点实例、outbox 事件
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  async with session_factory() as session:
    auth_service = AuthService(session, settings)
    admin = await auth_service.bootstrap_admin(
      email="admin@example.com",
      password="StrongPassword123!",
      real_name="管理员",
      employee_no="EMP-ROOT",
    )
    user_service = UserService(session)
    recipient = await user_service.create_user(
      actor=admin,
      email="worker@example.com",
      password="StrongPassword123!",
      role=UserRole.EMPLOYEE,
    )
    await session.commit()

  # 写入 WorkflowGraphInstance 和 WorkflowNodeInstance 以满足外键
  from app.models.workflow_graph import WorkflowGraphInstance, WorkflowNodeInstance
  from app.core.enums import WorkflowGraphInstanceStatus, WorkflowGraphNodeType, WorkflowNodeEngineState, WorkflowNodeBusinessState
  import uuid

  async with session_factory() as session:
    instance = WorkflowGraphInstance(
      initiator_user_id=admin.id,
      source_type="task",
      status=WorkflowGraphInstanceStatus.ACTIVE,
      current_node_key="task-node",
      context={},
      context_version=1,
      max_iterations=5,
    )
    session.add(instance)
    await session.flush()

    node_instance = WorkflowNodeInstance(
      instance_id=instance.id,
      node_key="task-node",
      title="测试节点",
      node_type=WorkflowGraphNodeType.TASK,
      engine_state=WorkflowNodeEngineState.ACTIVATED,
      business_state=WorkflowNodeBusinessState.ASSIGNED,
      assignee_user_id=recipient.id,
      iteration=1,
      node_instance_version=1,
    )
    session.add(node_instance)
    await session.flush()

    outbox_event = WorkflowOutboxEvent(
      instance_id=instance.id,
      node_instance_id=node_instance.id,
      event_type="workflow_node_taken_over",
      status=WorkflowOutboxEventStatus.PENDING,
      attempt_count=0,
      payload={
        "recipient_user_id": str(recipient.id),
        "recipient_email": recipient.email,
        "title": "节点已被管理员接管：测试节点",
        "body_text": "节点「测试节点」已由管理员接管。",
        "node_instance_id": str(node_instance.id),
        "workflow_graph_instance_id": str(instance.id),
        "from_assignee_user_id": str(recipient.id),
        "to_assignee_user_id": str(admin.id),
        "operator_user_id": str(admin.id),
        "reason": "测试接管",
      },
    )
    session.add(outbox_event)
    outbox_event_id = outbox_event.id  # 获取 ID 前需先 flush
    await session.flush()
    outbox_event_id = outbox_event.id
    await session.commit()

  queue_publisher = InMemoryQueuePublisher()
  dispatched_count = await process_workflow_outbox_events(
    session_factory=session_factory,
    queue_publisher=queue_publisher,
  )

  # 验证：投递数量为 1，outbox 事件状态变为 DISPATCHED，NotificationMessage 已写入
  from app.models import NotificationMessage as NotificationMessageModel
  async with session_factory() as session:
    refreshed_event = await session.get(WorkflowOutboxEvent, outbox_event_id)
    notification_count = await session.scalar(
      select(func.count(NotificationMessageModel.id))
    )

  assert dispatched_count == 1
  assert refreshed_event is not None
  assert refreshed_event.status == WorkflowOutboxEventStatus.DISPATCHED
  assert refreshed_event.dispatched_at is not None
  assert refreshed_event.attempt_count == 1
  assert notification_count == 1

  await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.workflow_i4_gate
async def test_iteration3_outbox_retry_reuses_event_notification_identity() -> None:
  """Simulate crash after notification commit but before outbox dispatch commit."""
  from app.models.workflow_graph import WorkflowGraphInstance, WorkflowOutboxEvent
  from app.workers.workflow_outbox_worker import process_workflow_outbox_events
  from app.core.enums import WorkflowGraphInstanceStatus

  engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
  )
  async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
  session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)

  async with session_factory() as session:
    admin = await AuthService(session, settings).bootstrap_admin(
      email="i3-outbox@example.com",
      password="StrongPassword123!",
      real_name="I3 Outbox",
      employee_no="I3-OUTBOX",
    )
    instance = WorkflowGraphInstance(
      initiator_user_id=admin.id,
      source_type="task",
      status=WorkflowGraphInstanceStatus.ACTIVE,
      context={},
    )
    session.add(instance)
    await session.flush()
    event = WorkflowOutboxEvent(
      instance_id=instance.id,
      event_type="workflow_node_activated",
      status=WorkflowOutboxEventStatus.PENDING,
      payload={
        "recipient_user_id": str(admin.id),
        "recipient_email": admin.email,
        "title": "稳定通知",
        "body_text": "重复消费不得创建第二条通知。",
      },
    )
    session.add(event)
    await session.flush()
    event_id = event.id
    await session.commit()

  queue = InMemoryQueuePublisher()
  assert await process_workflow_outbox_events(session_factory, queue) == 1
  async with session_factory() as session:
    event = await session.get(WorkflowOutboxEvent, event_id)
    assert event is not None
    event.status = WorkflowOutboxEventStatus.RETRYING
    event.dispatched_at = None
    await session.commit()
  assert await process_workflow_outbox_events(session_factory, queue) == 1

  async with session_factory() as session:
    messages = list(await session.scalars(select(NotificationMessage)))
    from app.models import WorkflowOperationalIncident

    duplicate_incident = await session.scalar(
      select(WorkflowOperationalIncident).where(
        WorkflowOperationalIncident.category == "outbox_duplicate"
      )
    )
  assert len(messages) == 1
  assert messages[0].deduplication_key == f"workflow_outbox:{event_id}"
  assert len(queue.payloads) == 2
  assert queue.payloads[0]["message_id"] == queue.payloads[1]["message_id"]
  assert queue.payloads[0]["delivery_ids"] == queue.payloads[1]["delivery_ids"]
  assert duplicate_incident is not None
  assert duplicate_incident.outbox_event_id == event_id
  await engine.dispose()


@pytest.mark.asyncio
async def test_phase11c_outbox_worker_retries_on_notification_failure() -> None:
  """投递失败时应递增 attempt_count，状态退回 RETRYING；达上限后标记 FAILED。"""
  from app.models.workflow_graph import WorkflowOutboxEvent
  from app.workers.workflow_outbox_worker import process_workflow_outbox_events, MAX_ATTEMPTS

  engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
  )
  async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)

  session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  async with session_factory() as session:
    auth_service = AuthService(session, settings)
    admin = await auth_service.bootstrap_admin(
      email="admin@example.com",
      password="StrongPassword123!",
      real_name="管理员",
      employee_no="EMP-ROOT",
    )
    await session.commit()

  from app.models.workflow_graph import WorkflowGraphInstance, WorkflowNodeInstance
  from app.core.enums import WorkflowGraphInstanceStatus, WorkflowGraphNodeType, WorkflowNodeEngineState, WorkflowNodeBusinessState

  async with session_factory() as session:
    instance = WorkflowGraphInstance(
      initiator_user_id=admin.id,
      source_type="task",
      status=WorkflowGraphInstanceStatus.ACTIVE,
      current_node_key="task-node",
      context={},
      context_version=1,
      max_iterations=5,
    )
    session.add(instance)
    await session.flush()

    # 写入一条 payload 缺失 recipient_user_id 的事件，必然会失败
    bad_event = WorkflowOutboxEvent(
      instance_id=instance.id,
      node_instance_id=None,
      event_type="workflow_node_taken_over",
      status=WorkflowOutboxEventStatus.PENDING,
      attempt_count=MAX_ATTEMPTS - 1,  # 再失败一次就应 FAILED
      payload={},  # 缺少 recipient_user_id / recipient_email → 投递必然报错
    )
    session.add(bad_event)
    await session.flush()
    bad_event_id = bad_event.id
    await session.commit()

  queue_publisher = InMemoryQueuePublisher()
  dispatched_count = await process_workflow_outbox_events(
    session_factory=session_factory,
    queue_publisher=queue_publisher,
  )

  async with session_factory() as session:
    refreshed = await session.get(WorkflowOutboxEvent, bad_event_id)

  assert dispatched_count == 1  # 计为"处理了"，即使最终失败
  assert refreshed is not None
  assert refreshed.status == WorkflowOutboxEventStatus.FAILED
  assert refreshed.last_error is not None
  assert refreshed.attempt_count == MAX_ATTEMPTS

  await engine.dispose()


@pytest.mark.asyncio
async def test_phase11c_outbox_worker_skips_non_pending_events(db_session) -> None:
  """DISPATCHED 或 FAILED 的事件不应被 worker 重复处理。"""
  from app.models.workflow_graph import WorkflowOutboxEvent
  from app.workers.workflow_outbox_worker import process_workflow_outbox_events

  engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
  )
  async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)

  session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)

  async with session_factory() as session:
    auth_service = AuthService(session, settings)
    admin = await auth_service.bootstrap_admin(
      email="admin@example.com",
      password="StrongPassword123!",
      real_name="管理员",
      employee_no="EMP-ROOT",
    )
    await session.commit()

  from app.models.workflow_graph import WorkflowGraphInstance
  from app.core.enums import WorkflowGraphInstanceStatus

  async with session_factory() as session:
    instance = WorkflowGraphInstance(
      initiator_user_id=admin.id,
      source_type="task",
      status=WorkflowGraphInstanceStatus.ACTIVE,
      current_node_key="task-node",
      context={},
      context_version=1,
      max_iterations=5,
    )
    session.add(instance)
    await session.flush()

    dispatched_event = WorkflowOutboxEvent(
      instance_id=instance.id,
      node_instance_id=None,
      event_type="workflow_node_taken_over",
      status=WorkflowOutboxEventStatus.DISPATCHED,
      attempt_count=1,
      payload={},
    )
    failed_event = WorkflowOutboxEvent(
      instance_id=instance.id,
      node_instance_id=None,
      event_type="workflow_node_taken_over",
      status=WorkflowOutboxEventStatus.FAILED,
      attempt_count=5,
      payload={},
    )
    session.add(dispatched_event)
    session.add(failed_event)
    await session.commit()

  queue_publisher = InMemoryQueuePublisher()
  result = await process_workflow_outbox_events(
    session_factory=session_factory,
    queue_publisher=queue_publisher,
  )

  assert result == 0

  await engine.dispose()
