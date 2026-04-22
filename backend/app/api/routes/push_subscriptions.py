from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_browser_push_service, get_current_user
from app.api.dependencies import get_notification_service
from app.core.config import Settings, get_settings
from app.core.enums import NotificationChannel, PushSubscriptionStatus
from app.core.exceptions import ConflictError
from app.models import User
from app.schemas.messages import NotificationMessage
from app.schemas.push import (
  PushSubscriptionConfigRead,
  PushSubscriptionCreateRequest,
  PushSubscriptionRead,
  PushTestNotificationRead,
)
from app.services.browser_push_service import BrowserPushService
from app.services.notification_service import NotificationService
from app.services.notification_source import build_notification_source_payload

router = APIRouter(prefix="/push-subscriptions")


@router.get("/config", response_model=PushSubscriptionConfigRead)
async def get_push_subscription_config(
  _: Annotated[User, Depends(get_current_user)],
  settings: Annotated[Settings, Depends(get_settings)],
) -> PushSubscriptionConfigRead:
  is_enabled = bool(
    settings.web_push_public_key
    and settings.web_push_private_key
    and settings.web_push_subject
  )
  return PushSubscriptionConfigRead(
    public_key=settings.web_push_public_key,
    is_enabled=is_enabled,
  )


@router.get("", response_model=list[PushSubscriptionRead])
async def list_push_subscriptions(
  actor: Annotated[User, Depends(get_current_user)],
  browser_push_service: Annotated[BrowserPushService, Depends(get_browser_push_service)],
) -> list[PushSubscriptionRead]:
  subscriptions = await browser_push_service.list_subscriptions(actor=actor)
  return [PushSubscriptionRead.model_validate(subscription) for subscription in subscriptions]


@router.post("", response_model=PushSubscriptionRead, status_code=status.HTTP_201_CREATED)
async def create_push_subscription(
  payload: PushSubscriptionCreateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  browser_push_service: Annotated[BrowserPushService, Depends(get_browser_push_service)],
) -> PushSubscriptionRead:
  subscription = await browser_push_service.upsert_subscription(
    actor=actor,
    endpoint=payload.endpoint,
    p256dh_key=payload.p256dh_key,
    auth_key=payload.auth_key,
    user_agent=payload.user_agent,
  )
  return PushSubscriptionRead.model_validate(subscription)


@router.delete("/{subscription_id}", response_model=PushSubscriptionRead)
async def delete_push_subscription(
  subscription_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  browser_push_service: Annotated[BrowserPushService, Depends(get_browser_push_service)],
) -> PushSubscriptionRead:
  subscription = await browser_push_service.revoke_subscription(
    actor=actor,
    subscription_id=subscription_id,
  )
  return PushSubscriptionRead.model_validate(subscription)


@router.post("/test", response_model=PushTestNotificationRead, status_code=status.HTTP_202_ACCEPTED)
async def send_test_push_notification(
  actor: Annotated[User, Depends(get_current_user)],
  browser_push_service: Annotated[BrowserPushService, Depends(get_browser_push_service)],
  notification_service: Annotated[NotificationService, Depends(get_notification_service)],
) -> PushTestNotificationRead:
  subscriptions = await browser_push_service.list_subscriptions(actor=actor)
  if not any(subscription.status == PushSubscriptionStatus.ACTIVE for subscription in subscriptions):
    raise ConflictError("当前账号没有活跃的浏览器推送订阅。")

  message = await notification_service.send(
    NotificationMessage(
      source_type="system",
      source_id=None,
      recipient_user_id=actor.id,
      recipient_email=actor.email,
      message_type="web_push_test",
      title="浏览器推送测试",
      body_text="如果你看到了这条通知，说明当前账号的 Web Push 链路已打通。",
      channels=[NotificationChannel.WEB_PUSH],
      payload=build_notification_source_payload(
        source_module="system",
        source_module_label="系统消息",
        source_object_type="push_test",
        source_object_id=None,
        source_object_label="浏览器推送测试",
        route_name="messages",
        extra_payload={"test_push": True},
      ),
    )
  )
  return PushTestNotificationRead(
    message_id=message.id,
    status=message.status,
    detail="测试推送已入队，请留意浏览器通知。",
  )
