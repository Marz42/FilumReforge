from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.enums import (
  ApprovalMode,
  AttachmentTargetType,
  CommentFormat,
  DelegationScopeType,
  DelegationStatus,
  DocumentCategory,
  DocumentStatus,
  EmploymentEventType,
  NotificationChannel,
  PushSubscriptionStatus,
  PositionAssignmentType,
  ReportDirection,
  ReportRouteStatus,
  ReportStatus,
  ReportingLineType,
  TaskActionType,
  WorkflowDefinitionStatus,
  WorkflowInstanceStatus,
  WorkflowStepRunStatus,
  WorkflowStepType,
  UserRole,
  UserStatus,
)
from app.models import (
  Announcement,
  AnnouncementArchive,
  Attachment,
  AttachmentLink,
  Base,
  BoardCard,
  BoardCardArchive,
  Delegation,
  Department,
  Document,
  DocumentEmbedding,
  ErrorEvent,
  EmploymentEvent,
  NotificationDelivery,
  NotificationMessage,
  NotificationReceipt,
  Position,
  Profile,
  ProfileFieldDefinition,
  ProfileFieldPermission,
  ProfilePosition,
  PushSubscription,
  Report,
  ReportRoute,
  RefreshToken,
  ReportingLine,
  Task,
  TaskComment,
  TaskDependency,
  TaskLog,
  TaskMemo,
  TaskSchedule,
  TaskTemplate,
  TaskTemplateStep,
  TaskTemplateStepDependency,
  TaskWatcher,
  User,
  WorkflowDefinition,
  WorkflowInstance,
  WorkflowStep,
  WorkflowStepRun,
)


POSTGRES_IDENTIFIER_MAX_LENGTH = 63


def test_metadata_identifier_names_fit_postgresql_limit() -> None:
  invalid_names = {
    name: len(name)
    for table in Base.metadata.tables.values()
    for name in (
      [table.name]
      + [constraint.name for constraint in table.constraints if constraint.name]
      + [index.name for index in table.indexes if index.name]
    )
    if len(name) > POSTGRES_IDENTIFIER_MAX_LENGTH
  }

  assert invalid_names == {}


@pytest.mark.asyncio
async def test_phase1_models_create_schema_and_persist_core_entities() -> None:
  engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
  )
  session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

  async with engine.begin() as connection:
    await connection.run_sync(Base.metadata.create_all)

  user_id = uuid4()
  department_id = uuid4()
  attachment_id = uuid4()
  task_id = uuid4()
  prerequisite_task_id = uuid4()
  token_id = uuid4()

  async with session_factory() as session:
    user = User(
      id=user_id,
      email="admin@example.com",
      password_hash="hashed-password",
      role=UserRole.ADMIN,
      status=UserStatus.ACTIVE,
    )
    department = Department(
      id=department_id,
      name="行政部",
      code="admin-dept",
      manager=user,
    )
    profile = Profile(
      user=user,
      employee_no="EMP-001",
      real_name="管理员",
      department=department,
      custom_fields={"skills": ["coordination"]},
    )
    refresh_token = RefreshToken(
      id=token_id,
      user=user,
      token_id="refresh-token-jti",
      expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    attachment = Attachment(
      id=attachment_id,
      storage_provider="local",
      bucket="filum-dev",
      object_key="tasks/task-1/spec.pdf",
      original_filename="spec.pdf",
      mime_type="application/pdf",
      size_bytes=1024,
      checksum_sha256="a" * 64,
      uploader=user,
    )
    task = Task(
      id=task_id,
      title="初始化基础任务",
      creator=user,
      assignee=user,
      department=department,
    )
    prerequisite_task = Task(
      id=prerequisite_task_id,
      title="准备数据基线",
      creator=user,
      assignee=user,
      department=department,
    )
    task_dependency = TaskDependency(
      task=task,
      depends_on_task=prerequisite_task,
      dependency_type="blocks",
    )
    message = NotificationMessage(
      source_type="task",
      source_id=task_id,
      recipient_user=user,
      message_type="task_assigned",
      title="你有新的任务",
      body_text="请处理初始化基础任务",
    )
    delivery = NotificationDelivery(
      message=message,
      channel=NotificationChannel.EMAIL,
      adapter_name="email",
    )
    attachment_link = AttachmentLink(
      attachment=attachment,
      target_type=AttachmentTargetType.TASK,
      target_id=task_id,
      created_by=user_id,
    )

    session.add_all(
      [
        user,
        department,
        profile,
        refresh_token,
        attachment,
        task,
        prerequisite_task,
        task_dependency,
        message,
        delivery,
        attachment_link,
      ]
    )
    await session.commit()

    stored_profile = await session.scalar(select(Profile).where(Profile.user_id == user_id))
    stored_task = await session.scalar(select(Task).where(Task.id == task_id))
    stored_message = await session.scalar(select(NotificationMessage).where(NotificationMessage.source_id == task_id))

    assert stored_profile is not None
    assert stored_profile.custom_fields["skills"] == ["coordination"]
    assert stored_task is not None
    assert stored_task.title == "初始化基础任务"
    assert stored_message is not None
    assert stored_message.message_type == "task_assigned"

  await engine.dispose()


@pytest.mark.asyncio
async def test_overview_models_persist_board_cards_and_announcements() -> None:
  engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
  )
  session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

  async with engine.begin() as connection:
    await connection.run_sync(Base.metadata.create_all)

  async with session_factory() as session:
    user = User(
      email="admin@example.com",
      password_hash="hashed-password",
      role=UserRole.ADMIN,
      status=UserStatus.ACTIVE,
    )
    department = Department(
      name="财务行政部",
      code="finance-admin",
      capabilities=["publish_announcement"],
    )
    session.add_all([user, department])
    await session.flush()

    board_card = BoardCard(
      scope_department_id=department.id,
      author_user_id=user.id,
      title="本周值班安排",
      content_md="请查看本周值班表。",
      expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    announcement = Announcement(
      publisher_department_id=department.id,
      author_user_id=user.id,
      title="节假日安排",
      content_md="下周一全员放假。",
      published_at=datetime.now(UTC),
    )
    session.add_all([board_card, announcement])
    await session.flush()

    board_archive = BoardCardArchive(
      original_card_id=board_card.id,
      scope_department_id=department.id,
      author_user_id=user.id,
      title=board_card.title,
      content_md=board_card.content_md,
      published_at=board_card.created_at,
      expires_at=board_card.expires_at,
      archived_at=datetime.now(UTC),
    )
    announcement_archive = AnnouncementArchive(
      original_announcement_id=announcement.id,
      publisher_department_id=department.id,
      author_user_id=user.id,
      title=announcement.title,
      content_md=announcement.content_md,
      published_at=announcement.published_at,
      archived_at=datetime.now(UTC),
    )
    session.add_all([board_archive, announcement_archive])
    await session.commit()

    stored_board = await session.scalar(select(BoardCard).where(BoardCard.title == "本周值班安排"))
    stored_announcement = await session.scalar(select(Announcement).where(Announcement.title == "节假日安排"))
    stored_board_archive = await session.scalar(
      select(BoardCardArchive).where(BoardCardArchive.original_card_id == board_card.id)
    )
    stored_announcement_archive = await session.scalar(
      select(AnnouncementArchive).where(AnnouncementArchive.original_announcement_id == announcement.id)
    )

    assert stored_board is not None
    assert stored_announcement is not None
    assert stored_board_archive is not None
    assert stored_announcement_archive is not None

  await engine.dispose()


@pytest.mark.asyncio
async def test_phase2_models_persist_task_comments_and_logs() -> None:
  engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
  )
  session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

  async with engine.begin() as connection:
    await connection.run_sync(Base.metadata.create_all)

  user_id = uuid4()
  department_id = uuid4()
  task_id = uuid4()
  comment_id = uuid4()

  async with session_factory() as session:
    user = User(
      id=user_id,
      email="employee@example.com",
      password_hash="hashed-password",
      role=UserRole.EMPLOYEE,
      status=UserStatus.ACTIVE,
    )
    department = Department(
      id=department_id,
      name="研发部",
      code="engineering",
      manager=user,
    )
    task = Task(
      id=task_id,
      title="完成协同模块设计",
      creator=user,
      assignee=user,
      department=department,
    )
    comment = TaskComment(
      id=comment_id,
      task=task,
      user=user,
      content="已同步设计方案，等待评审。",
      content_format=CommentFormat.MARKDOWN,
      is_internal=True,
    )
    log = TaskLog(
      task=task,
      operator=user,
      action_type=TaskActionType.COMMENTED,
      detail={"comment_id": str(comment_id)},
    )
    attachment = Attachment(
      storage_provider="local",
      bucket="filum-dev",
      object_key="tasks/task-2/comment-1/design.md",
      original_filename="design.md",
      mime_type="text/markdown",
      size_bytes=256,
      checksum_sha256="b" * 64,
      uploader=user,
    )
    comment_attachment_link = AttachmentLink(
      attachment=attachment,
      target_type=AttachmentTargetType.TASK_COMMENT,
      target_id=comment_id,
      created_by=user_id,
      relation="comment_attachment",
    )

    session.add_all([user, department, task, comment, log, attachment, comment_attachment_link])
    await session.commit()

    stored_comment = await session.scalar(select(TaskComment).where(TaskComment.id == comment_id))
    stored_log = await session.scalar(select(TaskLog).where(TaskLog.task_id == task_id))
    stored_comment_link = await session.scalar(
      select(AttachmentLink).where(
        AttachmentLink.target_type == AttachmentTargetType.TASK_COMMENT,
        AttachmentLink.target_id == comment_id,
      )
    )

    assert stored_comment is not None
    assert stored_comment.content_format == CommentFormat.MARKDOWN
    assert stored_comment.is_internal is True
    assert stored_log is not None
    assert stored_log.action_type == TaskActionType.COMMENTED
    assert stored_log.detail["comment_id"] == str(comment_id)
    assert stored_comment_link is not None
    assert stored_comment_link.relation == "comment_attachment"

  await engine.dispose()


@pytest.mark.asyncio
async def test_step3_models_persist_task_memos() -> None:
  engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
  )
  session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

  async with engine.begin() as connection:
    await connection.run_sync(Base.metadata.create_all)

  user_id = uuid4()
  department_id = uuid4()
  task_id = uuid4()

  async with session_factory() as session:
    user = User(
      id=user_id,
      email="memo-owner@example.com",
      password_hash="hashed-password",
      role=UserRole.EMPLOYEE,
      status=UserStatus.ACTIVE,
    )
    department = Department(
      id=department_id,
      name="执行部",
      code="delivery",
      manager=user,
    )
    task = Task(
      id=task_id,
      title="整理交付清单",
      creator=user,
      assignee=user,
      department=department,
    )
    memo = TaskMemo(
      owner=user,
      related_task=task,
      content="先和交付负责人确认最终版本。",
      is_pinned=True,
    )
    session.add_all([user, department, task, memo])
    await session.commit()

    stored_memo = await session.scalar(select(TaskMemo).where(TaskMemo.owner_user_id == user_id))
    assert stored_memo is not None
    assert stored_memo.related_task_id == task_id
    assert stored_memo.is_pinned is True

  await engine.dispose()


@pytest.mark.asyncio
async def test_step4_models_persist_reports_and_routes() -> None:
  engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
  )
  session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

  async with engine.begin() as connection:
    await connection.run_sync(Base.metadata.create_all)

  async with session_factory() as session:
    initiator = User(
      email="initiator@example.com",
      password_hash="hashed-password",
      role=UserRole.EMPLOYEE,
      status=UserStatus.ACTIVE,
    )
    manager = User(
      email="manager@example.com",
      password_hash="hashed-password",
      role=UserRole.EMPLOYEE,
      status=UserStatus.ACTIVE,
    )
    target = User(
      email="target@example.com",
      password_hash="hashed-password",
      role=UserRole.ADMIN,
      status=UserStatus.ACTIVE,
    )
    department = Department(
      name="汇报部",
      code="reports",
      manager=target,
    )
    session.add_all([initiator, manager, target, department])
    await session.flush()

    session.add_all(
      [
        Profile(user=initiator, employee_no="EMP-RPT-001", real_name="发起人", department=department),
        Profile(user=manager, employee_no="EMP-RPT-002", real_name="中层经理", department=department),
        Profile(user=target, employee_no="EMP-RPT-003", real_name="最终上级", department=department),
      ]
    )
    report = Report(
      direction=ReportDirection.UPWARD,
      status=ReportStatus.IN_PROGRESS,
      title="阶段汇报",
      content_md="本周完成了关键任务推进。",
      initiator=initiator,
      target=target,
      current_recipient=manager,
      current_route_sequence=1,
    )
    route = ReportRoute(
      report=report,
      sequence_no=1,
      sender=initiator,
      recipient=manager,
      assigned_user=manager,
      status=ReportRouteStatus.PENDING,
    )
    session.add_all([report, route])
    await session.commit()

    stored_report = await session.scalar(select(Report).where(Report.title == "阶段汇报"))
    stored_route = await session.scalar(select(ReportRoute).where(ReportRoute.report_id == report.id))
    raw_report_row = (
      await session.execute(
        text("select direction, status from reports where title = :title"),
        {"title": "阶段汇报"},
      )
    ).one()
    raw_route_row = (
      await session.execute(
        text("select status from report_routes where sequence_no = :sequence_no"),
        {"sequence_no": 1},
      )
    ).one()

    assert stored_report is not None
    assert stored_report.direction == ReportDirection.UPWARD
    assert stored_report.current_recipient_user_id == manager.id
    assert stored_route is not None
    assert stored_route.status == ReportRouteStatus.PENDING
    assert stored_route.assigned_user_id == manager.id
    assert raw_report_row == ("upward", "in_progress")
    assert raw_route_row == ("pending",)

  await engine.dispose()


@pytest.mark.asyncio
async def test_observability_models_persist_error_events() -> None:
  engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
  )
  session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

  async with engine.begin() as connection:
    await connection.run_sync(Base.metadata.create_all)

  actor_id = uuid4()
  async with session_factory() as session:
    actor = User(
      id=actor_id,
      email="observer@example.com",
      password_hash="hashed-password",
      role=UserRole.EMPLOYEE,
      status=UserStatus.ACTIVE,
    )
    session.add(actor)
    await session.flush()

    error_event = ErrorEvent(
      request_id="req-observability-1",
      scope="report_center.create_report",
      actor_user_id=actor_id,
      source_type="report",
      source_id=uuid4(),
      http_method="POST",
      path="/api/v1/report-center/reports",
      error_type="RuntimeError",
      error_message="boom",
      error_code="internal_error",
      stage="serialize_response",
      context_json={"direction": "upward", "target_user_id": "target-1"},
    )
    session.add(error_event)
    await session.commit()

    stored_event = await session.scalar(select(ErrorEvent).where(ErrorEvent.request_id == "req-observability-1"))

    assert stored_event is not None
    assert stored_event.scope == "report_center.create_report"
    assert stored_event.actor_user_id == actor_id
    assert stored_event.context_json["direction"] == "upward"

  await engine.dispose()


@pytest.mark.asyncio
async def test_phase3_models_persist_hr_governance_entities() -> None:
  engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
  )
  session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

  async with engine.begin() as connection:
    await connection.run_sync(Base.metadata.create_all)

  manager_id = uuid4()
  employee_id = uuid4()
  delegate_id = uuid4()
  department_id = uuid4()
  position_id = uuid4()

  async with session_factory() as session:
    manager = User(
      id=manager_id,
      email="manager@example.com",
      password_hash="hashed-password",
      role=UserRole.EMPLOYEE,
      status=UserStatus.ACTIVE,
    )
    employee = User(
      id=employee_id,
      email="employee@example.com",
      password_hash="hashed-password",
      role=UserRole.EMPLOYEE,
      status=UserStatus.ACTIVE,
    )
    delegate = User(
      id=delegate_id,
      email="delegate@example.com",
      password_hash="hashed-password",
      role=UserRole.EMPLOYEE,
      status=UserStatus.ACTIVE,
    )
    department = Department(
      id=department_id,
      name="运营部",
      code="ops",
      manager=manager,
    )
    profile = Profile(
      user=employee,
      employee_no="EMP-OPS-001",
      real_name="运营同学",
      department=department,
      custom_fields={
        "salary": 25000,
        "performance": "A",
      },
    )
    position = Position(
      id=position_id,
      code="ops-manager",
      name="运营经理",
      extra_metadata={"band": "P6"},
    )
    profile_position = ProfilePosition(
      user=employee,
      position=position,
      department=department,
      assignment_type=PositionAssignmentType.PRIMARY,
      is_primary=True,
      starts_at=date(2025, 1, 1),
    )
    reporting_line = ReportingLine(
      user=employee,
      manager=manager,
      department=department,
      line_type=ReportingLineType.SOLID,
      is_primary=True,
      starts_at=date(2025, 1, 1),
    )
    field_definition = ProfileFieldDefinition(
      field_key="performance",
      label="绩效评估",
      field_type="text",
      storage_target="custom",
      is_sensitive=True,
    )
    field_permission = ProfileFieldPermission(
      field_definition=field_definition,
      subject_type="reporting_line",
      subject_value=ReportingLineType.SOLID.value,
      can_view=True,
      can_edit=True,
    )
    employment_event = EmploymentEvent(
      user=employee,
      event_type=EmploymentEventType.PROMOTION,
      effective_date=date(2025, 2, 1),
      title="晋升为运营经理",
      payload={"position_id": str(position_id)},
      creator=manager,
    )
    delegation = Delegation(
      delegator=manager,
      delegate=delegate,
      scope_type=DelegationScopeType.DATA_ACCESS,
      status=DelegationStatus.ACTIVE,
      starts_at=datetime.now(UTC),
      ends_at=datetime.now(UTC) + timedelta(days=7),
      creator=manager,
    )

    session.add_all(
      [
        manager,
        employee,
        delegate,
        department,
        profile,
        position,
        profile_position,
        reporting_line,
        field_definition,
        field_permission,
        employment_event,
        delegation,
      ]
    )
    await session.commit()

    stored_position = await session.scalar(select(Position).where(Position.id == position_id))
    stored_reporting_line = await session.scalar(
      select(ReportingLine).where(ReportingLine.manager_user_id == manager_id)
    )
    stored_delegation = await session.scalar(
      select(Delegation).where(Delegation.delegate_user_id == delegate_id)
    )

    assert stored_position is not None
    assert stored_position.extra_metadata["band"] == "P6"
    assert stored_reporting_line is not None
    assert stored_reporting_line.line_type == ReportingLineType.SOLID
    assert stored_delegation is not None
    assert stored_delegation.scope_type == DelegationScopeType.DATA_ACCESS

  await engine.dispose()


@pytest.mark.asyncio
async def test_phase4_models_persist_workflow_and_messaging_entities() -> None:
  engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
  )
  session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

  async with engine.begin() as connection:
    await connection.run_sync(Base.metadata.create_all)

  creator_id = uuid4()
  approver_id = uuid4()
  department_id = uuid4()

  async with session_factory() as session:
    creator = User(
      id=creator_id,
      email="creator@example.com",
      password_hash="hashed-password",
      role=UserRole.ADMIN,
      status=UserStatus.ACTIVE,
    )
    approver = User(
      id=approver_id,
      email="approver@example.com",
      password_hash="hashed-password",
      role=UserRole.EMPLOYEE,
      status=UserStatus.ACTIVE,
    )
    department = Department(
      id=department_id,
      name="流程部",
      code="workflow",
      manager=creator,
    )
    task = Task(
      title="采购申请",
      creator=creator,
      assignee=approver,
      department=department,
    )
    template = TaskTemplate(
      code="procurement-template",
      base_code="procurement-template",
      version=1,
      name="采购模板",
      category="procurement",
      created_by=creator_id,
    )
    template_step = TaskTemplateStep(
      template=template,
      step_key="submit",
      title="提交申请",
      default_assignee_rule={"type": "initiator"},
      sort_order=1,
    )
    review_step = TaskTemplateStep(
      template=template,
      step_key="review",
      title="主管审批",
      step_type="approval",
      default_assignee_rule={"type": "user", "user_ids": [str(approver_id)]},
      default_due_offset_hours=24,
      sort_order=2,
    )
    step_dependency = TaskTemplateStepDependency(
      step=review_step,
      depends_on_step=template_step,
    )
    workflow_definition = WorkflowDefinition(
      code="procurement-approval",
      name="采购审批流",
      scope_type="procurement",
      status=WorkflowDefinitionStatus.ACTIVE,
      created_by=creator_id,
    )
    workflow_step = WorkflowStep(
      definition=workflow_definition,
      step_key="manager-approval",
      name="主管审批",
      step_type=WorkflowStepType.APPROVAL,
      approval_mode=ApprovalMode.SINGLE,
      assignee_rule={"type": "user_ids", "user_ids": [str(approver_id)]},
      sort_order=1,
    )
    workflow_instance = WorkflowInstance(
      definition=workflow_definition,
      source_type="task",
      source_id=task.id,
      initiator_user_id=creator_id,
      status=WorkflowInstanceStatus.IN_PROGRESS,
      current_step_key=workflow_step.step_key,
    )
    workflow_step_run = WorkflowStepRun(
      instance=workflow_instance,
      step=workflow_step,
      assignee_user_id=approver_id,
      status=WorkflowStepRunStatus.PENDING,
    )
    task_watcher = TaskWatcher(
      task=task,
      user_id=creator_id,
      relation="cc",
      created_by=creator_id,
    )
    task_schedule = TaskSchedule(
      template=template,
      owner_user_id=creator_id,
      cron_expr="0 9 * * 1",
      payload={"department_id": str(department_id)},
      last_run_status=None,
      last_run_message=None,
      last_run_task_count=None,
    )
    message = NotificationMessage(
      source_type="workflow",
      source_id=workflow_instance.id,
      recipient_user=approver,
      message_type="workflow_action_required",
      title="待审批",
      body_text="你有一条待审批流程。",
    )
    delivery = NotificationDelivery(
      message=message,
      channel=NotificationChannel.WEBSOCKET,
      adapter_name="websocket",
    )
    receipt = NotificationReceipt(
      message=message,
      user=approver,
      receipt_type="read",
    )

    session.add_all(
      [
        creator,
        approver,
        department,
        task,
        template,
        template_step,
        review_step,
        step_dependency,
        workflow_definition,
        workflow_step,
        workflow_instance,
        workflow_step_run,
        task_watcher,
        task_schedule,
        message,
        delivery,
        receipt,
      ]
    )
    await session.commit()

    stored_template = await session.scalar(select(TaskTemplate).where(TaskTemplate.code == "procurement-template"))
    stored_workflow_instance = await session.scalar(
      select(WorkflowInstance).where(WorkflowInstance.current_step_key == "manager-approval")
    )
    stored_receipt = await session.scalar(
      select(NotificationReceipt).where(NotificationReceipt.receipt_type == "read")
    )

    assert stored_template is not None
    assert len(stored_template.steps) == 2
    assert stored_workflow_instance is not None
    assert stored_workflow_instance.status == WorkflowInstanceStatus.IN_PROGRESS
    assert stored_receipt is not None
    assert stored_receipt.user_id == approver_id

  await engine.dispose()


@pytest.mark.asyncio
async def test_phase5_models_persist_knowledge_and_push_entities() -> None:
  engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
  )
  session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

  async with engine.begin() as connection:
    await connection.run_sync(Base.metadata.create_all)

  author_id = uuid4()

  async with session_factory() as session:
    author = User(
      id=author_id,
      email="knowledge-owner@example.com",
      password_hash="hashed-password",
      role=UserRole.HR,
      status=UserStatus.ACTIVE,
    )
    document = Document(
      title="员工入职 SOP",
      slug="employee-onboarding-sop",
      category=DocumentCategory.SOP,
      status=DocumentStatus.PUBLISHED,
      content_md="# 入职流程\n\n1. 提交材料\n2. 创建账号",
      author=author,
      version=2,
      published_at=datetime.now(UTC),
    )
    embedding = DocumentEmbedding(
      document=document,
      chunk_index=0,
      chunk_text="提交材料 创建账号",
      token_count=8,
      embedding_model="text-embedding-3-small",
      embedding=[0.01, 0.02, 0.03],
    )
    subscription = PushSubscription(
      user=author,
      endpoint="https://push.example.com/subscriptions/abc",
      p256dh_key="p256dh-key",
      auth_key="auth-key",
      status=PushSubscriptionStatus.ACTIVE,
      user_agent="Mozilla/5.0",
      last_seen_at=datetime.now(UTC),
    )

    session.add_all([author, document, embedding, subscription])
    await session.commit()

    stored_document = await session.scalar(
      select(Document).where(Document.slug == "employee-onboarding-sop")
    )
    stored_embedding = await session.scalar(
      select(DocumentEmbedding).where(DocumentEmbedding.document_id == document.id)
    )
    stored_subscription = await session.scalar(
      select(PushSubscription).where(
        PushSubscription.endpoint == "https://push.example.com/subscriptions/abc"
      )
    )

    assert stored_document is not None
    assert stored_document.category == DocumentCategory.SOP
    assert stored_document.status == DocumentStatus.PUBLISHED
    assert stored_embedding is not None
    assert stored_embedding.embedding_model == "text-embedding-3-small"
    assert stored_subscription is not None
    assert stored_subscription.status == PushSubscriptionStatus.ACTIVE

  await engine.dispose()
