from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import NotificationReceiptType
from app.core.exceptions import AuthorizationError, NotFoundError
from app.models import NotificationMessage, NotificationReceipt, User
from app.services.access_control import MANAGEMENT_ROLES, ensure_active_user


class MessageCenterService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  def _message_statement(self):
    return select(NotificationMessage).options(
      selectinload(NotificationMessage.deliveries),
      selectinload(NotificationMessage.receipts).selectinload(NotificationReceipt.user),
      selectinload(NotificationMessage.recipient_user),
    )

  async def _get_message_or_raise(self, *, actor: User, message_id: UUID) -> NotificationMessage:
    statement = self._message_statement().where(NotificationMessage.id == message_id)
    if actor.role not in MANAGEMENT_ROLES:
      statement = statement.where(NotificationMessage.recipient_user_id == actor.id)
    message = await self._session.scalar(statement)
    if message is None:
      raise NotFoundError("消息不存在。")
    return message

  async def list_messages(self, *, actor: User) -> list[NotificationMessage]:
    ensure_active_user(actor)
    statement = self._message_statement().order_by(NotificationMessage.created_at.desc())
    if actor.role not in MANAGEMENT_ROLES:
      statement = statement.where(NotificationMessage.recipient_user_id == actor.id)
    return list(await self._session.scalars(statement))

  async def get_message(self, *, actor: User, message_id: UUID) -> NotificationMessage:
    ensure_active_user(actor)
    return await self._get_message_or_raise(actor=actor, message_id=message_id)

  async def create_receipt(
    self,
    *,
    actor: User,
    message_id: UUID,
    receipt_type: NotificationReceiptType,
    note: str | None = None,
  ) -> NotificationReceipt:
    ensure_active_user(actor)
    message = await self._get_message_or_raise(actor=actor, message_id=message_id)
    if message.recipient_user_id not in {None, actor.id} and actor.role not in MANAGEMENT_ROLES:
      raise AuthorizationError("当前账号不能回执该消息。")

    existing_receipt = await self._session.scalar(
      select(NotificationReceipt).where(
        NotificationReceipt.message_id == message.id,
        NotificationReceipt.user_id == actor.id,
        NotificationReceipt.receipt_type == receipt_type,
      )
    )
    if existing_receipt is not None:
      return existing_receipt

    receipt = NotificationReceipt(
      message_id=message.id,
      user_id=actor.id,
      receipt_type=receipt_type,
      note=note.strip() if note else None,
    )
    self._session.add(receipt)
    await self._session.commit()
    await self._session.refresh(receipt)
    return receipt

  async def list_receipts(self, *, actor: User, message_id: UUID) -> list[NotificationReceipt]:
    ensure_active_user(actor)
    await self._get_message_or_raise(actor=actor, message_id=message_id)
    return list(
      await self._session.scalars(
        select(NotificationReceipt)
        .options(selectinload(NotificationReceipt.user))
        .where(NotificationReceipt.message_id == message_id)
        .order_by(NotificationReceipt.created_at.asc())
      )
    )
