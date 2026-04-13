from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.core.exceptions import AuthenticationError
from app.integrations.notifications.queue import (
  NotificationQueuePublisher,
  RedisNotificationQueuePublisher,
)
from app.integrations.storage.base import StorageAdapter
from app.integrations.storage.local import LocalStorageAdapter
from app.models import User
from app.services.access_control import ensure_management_role
from app.services.attachment_service import AttachmentService
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.notification_service import NotificationService
from app.services.object_storage_service import ObjectStorageService
from app.services.profile_service import ProfileService
from app.services.task_service import TaskService
from app.services.user_service import UserService

bearer_scheme = HTTPBearer(auto_error=False)


def get_storage_adapter(
  settings: Annotated[Settings, Depends(get_settings)],
) -> StorageAdapter:
  if settings.storage_provider != "local":
    raise ValueError(f"暂不支持对象存储提供方：{settings.storage_provider}")
  return LocalStorageAdapter(
    base_path=settings.storage_base_path,
    bucket=settings.storage_bucket,
  )


def get_object_storage_service(
  adapter: Annotated[StorageAdapter, Depends(get_storage_adapter)],
) -> ObjectStorageService:
  return ObjectStorageService(adapter)


def get_notification_queue_publisher(
  settings: Annotated[Settings, Depends(get_settings)],
) -> NotificationQueuePublisher | None:
  return RedisNotificationQueuePublisher(
    redis_dsn=settings.redis_dsn,
    queue_name=settings.redis_notification_queue,
  )


def get_auth_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
  settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
  return AuthService(session, settings)


def get_user_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserService:
  return UserService(session)


def get_department_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DepartmentService:
  return DepartmentService(session)


def get_profile_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProfileService:
  return ProfileService(session)


def get_notification_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
  queue_publisher: Annotated[
    NotificationQueuePublisher | None,
    Depends(get_notification_queue_publisher),
  ],
) -> NotificationService:
  return NotificationService(session, queue_publisher)


def get_attachment_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
  object_storage_service: Annotated[ObjectStorageService, Depends(get_object_storage_service)],
) -> AttachmentService:
  return AttachmentService(session, object_storage_service)


def get_task_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
  notification_service: Annotated[NotificationService, Depends(get_notification_service)],
) -> TaskService:
  return TaskService(session, notification_service)


async def get_current_user(
  credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
  session: Annotated[AsyncSession, Depends(get_db_session)],
  settings: Annotated[Settings, Depends(get_settings)],
) -> User:
  if credentials is None or credentials.scheme.lower() != "bearer":
    raise AuthenticationError("缺少访问令牌。")

  auth_service = AuthService(session, settings)
  return await auth_service.get_user_from_access_token(credentials.credentials)


def get_management_user(
  current_user: Annotated[User, Depends(get_current_user)],
) -> User:
  ensure_management_role(current_user)
  return current_user
