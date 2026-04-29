from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user, get_message_center_service
from app.core.enums import NotificationChannel, NotificationDeliveryStatus
from app.models import User
from app.schemas.message_center import (
  MessageCenterSnapshotRead,
  MessageRead,
  MessageReceiptCreateRequest,
  NotificationReceiptRead,
)
from app.services.message_center_service import MessageCenterService

router = APIRouter(prefix="/messages")


@router.get("", response_model=MessageCenterSnapshotRead)
async def list_messages(
  actor: Annotated[User, Depends(get_current_user)],
  message_center_service: Annotated[MessageCenterService, Depends(get_message_center_service)],
  source_type: str | None = None,
  state: Literal["all", "unread", "read", "unacknowledged", "acknowledged"] = "all",
  channel: NotificationChannel | None = None,
  delivery_status: NotificationDeliveryStatus | None = None,
  created_from: datetime | None = None,
  created_to: datetime | None = None,
) -> MessageCenterSnapshotRead:
  snapshot = await message_center_service.get_message_center_snapshot(
    actor=actor,
    source_type=source_type,
    state=state,
    channel=channel,
    delivery_status=delivery_status,
    created_from=created_from,
    created_to=created_to,
  )
  return MessageCenterSnapshotRead.model_validate(asdict(snapshot))


@router.get("/{message_id}", response_model=MessageRead)
async def read_message(
  message_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  message_center_service: Annotated[MessageCenterService, Depends(get_message_center_service)],
) -> MessageRead:
  message = await message_center_service.get_message_view(actor=actor, message_id=message_id)
  return MessageRead.model_validate(message)


@router.get("/{message_id}/receipts", response_model=list[NotificationReceiptRead])
async def list_message_receipts(
  message_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  message_center_service: Annotated[MessageCenterService, Depends(get_message_center_service)],
) -> list[NotificationReceiptRead]:
  receipts = await message_center_service.list_receipts(actor=actor, message_id=message_id)
  return [NotificationReceiptRead.model_validate(receipt) for receipt in receipts]


@router.post("/{message_id}/receipts", response_model=NotificationReceiptRead, status_code=status.HTTP_201_CREATED)
async def create_message_receipt(
  message_id: UUID,
  payload: MessageReceiptCreateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  message_center_service: Annotated[MessageCenterService, Depends(get_message_center_service)],
) -> NotificationReceiptRead:
  receipt = await message_center_service.create_receipt(
    actor=actor,
    message_id=message_id,
    receipt_type=payload.receipt_type,
    note=payload.note,
  )
  return NotificationReceiptRead.model_validate(receipt)
