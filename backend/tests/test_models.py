from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.enums import (
  AttachmentTargetType,
  NotificationChannel,
  UserRole,
  UserStatus,
)
from app.models import (
  Attachment,
  AttachmentLink,
  Base,
  Department,
  NotificationDelivery,
  NotificationMessage,
  Profile,
  RefreshToken,
  Task,
  TaskDependency,
  User,
)


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
