from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PushSubscriptionStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.models import NotificationMessage, PushSubscription, User
from app.services.access_control import ensure_active_user


class BrowserPushService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def list_subscriptions(self, *, actor: User) -> list[PushSubscription]:
    ensure_active_user(actor)
    return list(
      await self._session.scalars(
        select(PushSubscription)
        .where(PushSubscription.user_id == actor.id)
        .order_by(PushSubscription.created_at.desc())
      )
    )

  async def upsert_subscription(
    self,
    *,
    actor: User,
    endpoint: str,
    p256dh_key: str,
    auth_key: str,
    user_agent: str | None = None,
  ) -> PushSubscription:
    ensure_active_user(actor)

    normalized_endpoint = endpoint.strip()
    if not normalized_endpoint:
      raise ConflictError("推送端点不能为空。")

    subscription = await self._session.scalar(
      select(PushSubscription).where(PushSubscription.endpoint == normalized_endpoint)
    )
    if subscription is None:
      subscription = PushSubscription(
        user_id=actor.id,
        endpoint=normalized_endpoint,
        p256dh_key=p256dh_key.strip(),
        auth_key=auth_key.strip(),
        user_agent=user_agent.strip() if user_agent else None,
        last_seen_at=datetime.now(UTC),
      )
      self._session.add(subscription)
    else:
      if subscription.user_id != actor.id:
        raise ConflictError("该浏览器订阅已绑定其他账号。")
      subscription.p256dh_key = p256dh_key.strip()
      subscription.auth_key = auth_key.strip()
      subscription.user_agent = user_agent.strip() if user_agent else None
      subscription.status = PushSubscriptionStatus.ACTIVE
      subscription.last_seen_at = datetime.now(UTC)

    await self._session.commit()
    await self._session.refresh(subscription)
    return subscription

  async def revoke_subscription(self, *, actor: User, subscription_id: UUID) -> PushSubscription:
    ensure_active_user(actor)

    subscription = await self._session.get(PushSubscription, subscription_id)
    if subscription is None or subscription.user_id != actor.id:
      raise NotFoundError("推送订阅不存在。")
    subscription.status = PushSubscriptionStatus.REVOKED
    subscription.last_seen_at = datetime.now(UTC)
    await self._session.commit()
    await self._session.refresh(subscription)
    return subscription

  @staticmethod
  def build_payload(*, message: NotificationMessage) -> dict[str, object]:
    return {
      "title": message.title,
      "body": message.body_text,
      "message_id": str(message.id),
      "message_type": message.message_type,
      "source_type": message.source_type,
      "source_id": str(message.source_id) if message.source_id is not None else None,
      "payload": message.payload,
    }
