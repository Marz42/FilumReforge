from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.enums import NotificationChannel
from app.integrations.notifications.base import NotificationAdapter
from app.integrations.notifications.email import EmailNotificationAdapter
from app.integrations.notifications.web_push import WebPushNotificationAdapter
from app.integrations.notifications.websocket import WebSocketNotificationAdapter


def build_notification_adapters(
  *,
  session: AsyncSession,
  settings: Settings,
) -> dict[NotificationChannel, NotificationAdapter]:
  return {
    NotificationChannel.EMAIL: EmailNotificationAdapter(),
    NotificationChannel.WEBSOCKET: WebSocketNotificationAdapter(),
    NotificationChannel.WEB_PUSH: WebPushNotificationAdapter(
      session=session,
      settings=settings,
    ),
  }
