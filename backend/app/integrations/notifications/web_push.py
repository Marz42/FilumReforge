from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from functools import partial
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.notifications.base import NotificationSendResult
from app.core.config import Settings
from app.core.enums import PushSubscriptionStatus
from app.core.exceptions import ConfigurationError, ConflictError, NotFoundError
from app.models import NotificationDelivery, NotificationMessage, PushSubscription
from app.services.browser_push_service import BrowserPushService

try:  # pragma: no cover - dependency is optional in tests when sender is injected
  from pywebpush import webpush
except ImportError:  # pragma: no cover - exercised only when dependency is missing
  webpush = None


class WebPushSender(Protocol):
  def __call__(
    self,
    *,
    subscription_info: dict[str, Any],
    data: str,
    vapid_private_key: str,
    vapid_claims: dict[str, str],
  ) -> Any: ...


class WebPushNotificationAdapter:
  def __init__(
    self,
    *,
    session: AsyncSession,
    settings: Settings,
    browser_push_service: BrowserPushService | None = None,
    sender: WebPushSender | None = None,
  ) -> None:
    self._session = session
    self._settings = settings
    self._browser_push_service = browser_push_service or BrowserPushService(session)
    self._sender = sender

  async def send(
    self,
    *,
    message: NotificationMessage,
    delivery: NotificationDelivery,
  ) -> NotificationSendResult:
    if message.recipient_user_id is None:
      raise ConflictError("Web Push 需要 recipient_user_id。")
    if not all(value and value.strip() for value in (self._settings.web_push_private_key, self._settings.web_push_subject)):
      raise ConfigurationError("缺少 Web Push VAPID 配置。")

    sender = self._sender or (partial(webpush, timeout=10) if webpush is not None else None)
    if sender is None:
      raise ConfigurationError("当前环境未安装 pywebpush，无法发送浏览器推送。")

    subscriptions = list(
      await self._session.scalars(
        select(PushSubscription).where(
          PushSubscription.user_id == message.recipient_user_id,
          PushSubscription.status == PushSubscriptionStatus.ACTIVE,
        )
      )
    )
    if not subscriptions:
      raise NotFoundError("当前用户没有活跃的浏览器推送订阅。")

    payload = json.dumps(
      self._browser_push_service.build_payload(message=message),
      ensure_ascii=False,
    )
    success_count = 0
    expired_count = 0
    failed_count = 0

    for subscription in subscriptions:
      subscription_info = {
        "endpoint": subscription.endpoint,
        "keys": {
          "p256dh": subscription.p256dh_key,
          "auth": subscription.auth_key,
        },
      }
      try:
        await asyncio.to_thread(
          sender,
          subscription_info=subscription_info,
          data=payload,
          vapid_private_key=self._settings.web_push_private_key,
          vapid_claims={"sub": self._settings.web_push_subject},
        )
      except Exception as exc:  # provider/transport failures are isolated per device
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None) or getattr(exc, "status_code", None)
        if status_code in {404, 410}:
          subscription.status = PushSubscriptionStatus.EXPIRED
          expired_count += 1
        failed_count += 1
      else:
        subscription.last_seen_at = datetime.now(UTC)
        success_count += 1

    await self._session.flush()
    total = len(subscriptions)
    detail = f"推送服务已受理 {success_count}/{total} 个设备；失败 {failed_count} 个，其中失效订阅 {expired_count} 个。"
    if success_count == 0:
      raise ConflictError(detail + " 请检查推送配置或重新启用本浏览器推送。")
    return NotificationSendResult(
      external_message_id=f"web_push:{message.id}:{delivery.id}:{success_count}",
      warning=detail if failed_count else None,
    )
