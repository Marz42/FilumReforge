from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_browser_push_service, get_current_user
from app.models import User
from app.schemas.push import PushSubscriptionCreateRequest, PushSubscriptionRead
from app.services.browser_push_service import BrowserPushService

router = APIRouter(prefix="/push-subscriptions")


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
