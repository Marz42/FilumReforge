from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.core.exceptions import AuthenticationError
from app.integrations.notifications.queue import (
  JobQueuePublisher,
  NotificationQueuePublisher,
  RedisNotificationQueuePublisher,
)
from app.integrations.llm.openai_client import OpenAIClient
from app.integrations.storage.base import StorageAdapter
from app.integrations.storage.local import LocalStorageAdapter
from app.models import User
from app.services.access_control import ensure_management_role
from app.services.attachment_service import AttachmentService
from app.services.auth_service import AuthService
from app.services.browser_push_service import BrowserPushService
from app.services.department_service import DepartmentService
from app.services.delegation_service import DelegationService
from app.services.hr_lifecycle_service import HRLifecycleService
from app.services.document_service import DocumentService
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.llm_router_service import LLMRouterService
from app.services.message_center_service import MessageCenterService
from app.services.notification_service import NotificationService
from app.services.object_storage_service import ObjectStorageService
from app.services.organization_relation_service import OrganizationRelationService
from app.services.profile_field_policy_service import ProfileFieldPolicyService
from app.services.profile_service import ProfileService
from app.services.task_automation_service import TaskAutomationService
from app.services.task_service import TaskService
from app.services.task_template_service import TaskTemplateService
from app.services.tool_registry_service import ToolRegistryService
from app.services.user_service import UserService
from app.services.workflow_engine_service import WorkflowEngineService

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


def get_job_queue_publisher(
  settings: Annotated[Settings, Depends(get_settings)],
) -> JobQueuePublisher:
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


def get_organization_relation_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OrganizationRelationService:
  return OrganizationRelationService(session)


def get_hr_lifecycle_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HRLifecycleService:
  return HRLifecycleService(session)


def get_delegation_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DelegationService:
  return DelegationService(session)


def get_profile_field_policy_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProfileFieldPolicyService:
  return ProfileFieldPolicyService(session)


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
  attachment_service: Annotated[AttachmentService, Depends(get_attachment_service)],
) -> TaskService:
  return TaskService(session, notification_service, attachment_service)


def get_task_template_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
  notification_service: Annotated[NotificationService, Depends(get_notification_service)],
) -> TaskTemplateService:
  return TaskTemplateService(session, task_service, notification_service)


def get_task_automation_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
  task_template_service: Annotated[TaskTemplateService, Depends(get_task_template_service)],
) -> TaskAutomationService:
  return TaskAutomationService(session, task_template_service)


def get_workflow_engine_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
  notification_service: Annotated[NotificationService, Depends(get_notification_service)],
) -> WorkflowEngineService:
  return WorkflowEngineService(session, notification_service)


def get_message_center_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MessageCenterService:
  return MessageCenterService(session)


def get_document_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentService:
  return DocumentService(session)


def get_openai_client(
  settings: Annotated[Settings, Depends(get_settings)],
) -> OpenAIClient:
  return OpenAIClient(settings)


def get_knowledge_retrieval_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
  settings: Annotated[Settings, Depends(get_settings)],
  openai_client: Annotated[OpenAIClient, Depends(get_openai_client)],
) -> KnowledgeRetrievalService:
  return KnowledgeRetrievalService(session, settings, openai_client)


def get_browser_push_service(
  session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BrowserPushService:
  return BrowserPushService(session)


def get_tool_registry_service(
  document_service: Annotated[DocumentService, Depends(get_document_service)],
  retrieval_service: Annotated[KnowledgeRetrievalService, Depends(get_knowledge_retrieval_service)],
  task_service: Annotated[TaskService, Depends(get_task_service)],
  workflow_engine_service: Annotated[
    WorkflowEngineService,
    Depends(get_workflow_engine_service),
  ],
  message_center_service: Annotated[
    MessageCenterService,
    Depends(get_message_center_service),
  ],
  profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ToolRegistryService:
  return ToolRegistryService(
    document_service=document_service,
    retrieval_service=retrieval_service,
    task_service=task_service,
    workflow_engine_service=workflow_engine_service,
    message_center_service=message_center_service,
    profile_service=profile_service,
  )


def get_llm_router_service(
  settings: Annotated[Settings, Depends(get_settings)],
  openai_client: Annotated[OpenAIClient, Depends(get_openai_client)],
  retrieval_service: Annotated[KnowledgeRetrievalService, Depends(get_knowledge_retrieval_service)],
  tool_registry_service: Annotated[ToolRegistryService, Depends(get_tool_registry_service)],
) -> LLMRouterService:
  return LLMRouterService(
    settings=settings,
    openai_client=openai_client,
    retrieval_service=retrieval_service,
    tool_registry_service=tool_registry_service,
  )


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
