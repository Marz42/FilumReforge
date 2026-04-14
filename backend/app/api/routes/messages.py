from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user, get_message_center_service
from app.models import User
from app.schemas.message_center import MessageRead, MessageReceiptCreateRequest, NotificationReceiptRead
from app.services.message_center_service import MessageCenterService

router = APIRouter(prefix="/messages")


@router.get("", response_model=list[MessageRead])
async def list_messages(
  actor: Annotated[User, Depends(get_current_user)],
  message_center_service: Annotated[MessageCenterService, Depends(get_message_center_service)],
) -> list[MessageRead]:
  messages = await message_center_service.list_messages(actor=actor)
  return [MessageRead.model_validate(message) for message in messages]


@router.get("/{message_id}", response_model=MessageRead)
async def read_message(
  message_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  message_center_service: Annotated[MessageCenterService, Depends(get_message_center_service)],
) -> MessageRead:
  message = await message_center_service.get_message(actor=actor, message_id=message_id)
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
