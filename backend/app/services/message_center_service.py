from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
  AttachmentStatus,
  AttachmentTargetType,
  NotificationChannel,
  NotificationDeliveryStatus,
  NotificationReceiptType,
)
from app.core.exceptions import AuthorizationError, NotFoundError
from app.models import Attachment, AttachmentLink, NotificationMessage, NotificationReceipt, User, WorkflowInstance
from app.schemas.attachments import AttachmentRead
from app.services.object_storage_service import ObjectStorageService
from app.services.access_control import ensure_active_user

MessageStateFilter = Literal["all", "unread", "read", "unacknowledged", "acknowledged"]

MODULE_LABELS: dict[str, str] = {
  "announcement": "总览",
  "report": "汇报中心",
  "task": "任务中心",
  "workflow": "流程引擎",
}


@dataclass(slots=True)
class MessageCenterSnapshot:
  items: list[dict[str, Any]]
  total_count: int
  filtered_count: int
  unread_count: int
  unacknowledged_count: int
  source_counts: list[dict[str, Any]]
  applied_source_type: str | None
  applied_state: MessageStateFilter
  applied_channel: NotificationChannel | None
  applied_delivery_status: NotificationDeliveryStatus | None
  applied_created_from: datetime | None
  applied_created_to: datetime | None


class MessageCenterService:
  def __init__(
    self,
    session: AsyncSession,
    *,
    object_storage_service: ObjectStorageService | None = None,
  ) -> None:
    self._session = session
    self._object_storage_service = object_storage_service

  def _message_statement(self):
    return select(NotificationMessage).options(
      selectinload(NotificationMessage.deliveries),
      selectinload(NotificationMessage.receipts).selectinload(NotificationReceipt.user),
      selectinload(NotificationMessage.recipient_user),
    )

  async def _get_message_or_raise(self, *, actor: User, message_id: UUID) -> NotificationMessage:
    statement = self._message_statement().where(
      NotificationMessage.id == message_id,
      NotificationMessage.recipient_user_id == actor.id,
    )
    message = await self._session.scalar(statement)
    if message is None:
      raise NotFoundError("消息不存在。")
    return message

  async def list_messages(self, *, actor: User) -> list[NotificationMessage]:
    ensure_active_user(actor)
    statement = (
      self._message_statement()
      .where(NotificationMessage.recipient_user_id == actor.id)
      .order_by(NotificationMessage.created_at.desc())
    )
    return list(await self._session.scalars(statement))

  async def get_message(self, *, actor: User, message_id: UUID) -> NotificationMessage:
    ensure_active_user(actor)
    return await self._get_message_or_raise(actor=actor, message_id=message_id)

  async def get_message_view(self, *, actor: User, message_id: UUID) -> dict[str, Any]:
    ensure_active_user(actor)
    message = await self._get_message_or_raise(actor=actor, message_id=message_id)
    workflow_instances = await self._load_workflow_instances(messages=[message])
    attachments_by_message_id = await self._load_message_attachments(message_ids=[message.id])
    return self._build_message_read(
      actor=actor,
      message=message,
      workflow_instances=workflow_instances,
      attachments_by_message_id=attachments_by_message_id,
    )

  async def get_message_center_snapshot(
    self,
    *,
    actor: User,
    source_type: str | None = None,
    state: MessageStateFilter = "all",
    channel: NotificationChannel | None = None,
    delivery_status: NotificationDeliveryStatus | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
  ) -> MessageCenterSnapshot:
    ensure_active_user(actor)
    messages = await self.list_messages(actor=actor)
    workflow_instances = await self._load_workflow_instances(messages=messages)
    attachments_by_message_id = await self._load_message_attachments(message_ids=[message.id for message in messages])
    items = [
      self._build_message_read(
        actor=actor,
        message=message,
        workflow_instances=workflow_instances,
        attachments_by_message_id=attachments_by_message_id,
      )
      for message in messages
    ]
    filtered_items = [
      item for item in items
      if self._matches_source_type(item=item, source_type=source_type)
      and self._matches_state(item=item, state=state)
      and self._matches_channel(item=item, channel=channel)
      and self._matches_delivery_status(item=item, delivery_status=delivery_status)
      and self._matches_created_at(item=item, created_from=created_from, created_to=created_to)
    ]
    unread_count = sum(1 for item in items if not item["receipt_state"]["is_read"])
    unacknowledged_count = sum(1 for item in items if not item["receipt_state"]["is_acknowledged"])
    return MessageCenterSnapshot(
      items=filtered_items,
      total_count=len(items),
      filtered_count=len(filtered_items),
      unread_count=unread_count,
      unacknowledged_count=unacknowledged_count,
      source_counts=self._build_source_counts(items),
      applied_source_type=source_type,
      applied_state=state,
      applied_channel=channel,
      applied_delivery_status=delivery_status,
      applied_created_from=created_from,
      applied_created_to=created_to,
    )

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
    if message.recipient_user_id not in {None, actor.id}:
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
        .where(
          NotificationReceipt.message_id == message_id,
          NotificationReceipt.user_id == actor.id,
        )
        .order_by(NotificationReceipt.created_at.asc())
      )
    )

  async def _load_workflow_instances(
    self,
    *,
    messages: list[NotificationMessage],
  ) -> dict[UUID, WorkflowInstance]:
    workflow_ids = [
      message.source_id
      for message in messages
      if message.source_type == "workflow" and message.source_id is not None
    ]
    if not workflow_ids:
      return {}
    instances = await self._session.scalars(
      select(WorkflowInstance).where(WorkflowInstance.id.in_(workflow_ids))
    )
    return {instance.id: instance for instance in instances}

  async def _build_attachment_read(self, *, attachment: Attachment) -> AttachmentRead:
    from app.api.attachment_serializers import serialize_attachment_read

    return await serialize_attachment_read(attachment, self._object_storage_service)

  async def _load_message_attachments(self, *, message_ids: list[UUID]) -> dict[UUID, list[AttachmentRead]]:
    if not message_ids:
      return {}

    rows = (await self._session.execute(
      select(AttachmentLink.target_id, Attachment)
      .join(Attachment, Attachment.id == AttachmentLink.attachment_id)
      .where(
        AttachmentLink.target_type == AttachmentTargetType.NOTIFICATION_MESSAGE,
        AttachmentLink.target_id.in_(message_ids),
        Attachment.status != AttachmentStatus.DELETED,
      )
      .order_by(Attachment.created_at.asc())
    )).all()

    attachments_by_message_id: dict[UUID, list[AttachmentRead]] = {message_id: [] for message_id in message_ids}
    for message_id, attachment in rows:
      attachments_by_message_id.setdefault(message_id, []).append(
        await self._build_attachment_read(attachment=attachment)
      )
    return attachments_by_message_id

  def _build_message_read(
    self,
    *,
    actor: User,
    message: NotificationMessage,
    workflow_instances: dict[UUID, WorkflowInstance],
    attachments_by_message_id: dict[UUID, list[AttachmentRead]],
  ) -> dict[str, Any]:
    actor_receipts = [
      receipt
      for receipt in sorted(message.receipts, key=lambda item: item.created_at)
      if receipt.user_id == actor.id
    ]
    return {
      "id": message.id,
      "source_type": message.source_type,
      "source_id": message.source_id,
      "recipient_user_id": message.recipient_user_id,
      "recipient_email": message.recipient_email,
      "message_type": message.message_type,
      "title": message.title,
      "body_text": message.body_text,
      "body_html": message.body_html,
      "payload": dict(message.payload),
      "status": message.status,
      "scheduled_at": message.scheduled_at,
      "enqueued_at": message.enqueued_at,
      "completed_at": message.completed_at,
      "created_at": message.created_at,
      "delivery_state": self._resolve_delivery_state(message=message),
      "source": self._build_source_read(
        message=message,
        workflow_instance=workflow_instances.get(message.source_id) if message.source_id else None,
      ),
      "receipt_state": self._build_receipt_state(actor_receipts),
      "attachments": attachments_by_message_id.get(message.id, []),
      "deliveries": list(message.deliveries),
      "receipts": actor_receipts,
    }

  def _resolve_delivery_state(self, *, message: NotificationMessage) -> NotificationDeliveryStatus | None:
    statuses = {delivery.status for delivery in message.deliveries}
    if not statuses:
      return None
    if NotificationDeliveryStatus.FAILED in statuses:
      return NotificationDeliveryStatus.FAILED
    if NotificationDeliveryStatus.RETRYING in statuses:
      return NotificationDeliveryStatus.RETRYING
    if NotificationDeliveryStatus.PENDING in statuses:
      return NotificationDeliveryStatus.PENDING
    return NotificationDeliveryStatus.SENT

  def _build_receipt_state(self, receipts: list[NotificationReceipt]) -> dict[str, datetime | bool | None]:
    read_at = next(
      (
        receipt.created_at
        for receipt in receipts
        if receipt.receipt_type in {NotificationReceiptType.READ, NotificationReceiptType.ACKNOWLEDGED}
      ),
      None,
    )
    acknowledged_at = next(
      (
        receipt.created_at
        for receipt in receipts
        if receipt.receipt_type == NotificationReceiptType.ACKNOWLEDGED
      ),
      None,
    )
    return {
      "is_read": read_at is not None,
      "is_acknowledged": acknowledged_at is not None,
      "read_at": read_at if read_at is not None else acknowledged_at,
      "acknowledged_at": acknowledged_at,
    }

  def _build_source_read(
    self,
    *,
    message: NotificationMessage,
    workflow_instance: WorkflowInstance | None,
  ) -> dict[str, Any]:
    payload = dict(message.payload or {})
    module_key = self._read_payload_str(payload, "source_module")
    module_label = self._read_payload_str(payload, "source_module_label")
    object_type = self._read_payload_str(payload, "source_object_type")
    object_label = self._read_payload_str(payload, "source_object_label")
    object_id = self._coerce_uuid(payload.get("source_object_id"))
    route_name = self._read_payload_str(payload, "source_route_name")
    route_query = self._read_route_query(payload.get("source_route_query"))

    if message.source_type == "workflow" and workflow_instance is not None:
      if module_key is None and workflow_instance.source_type in MODULE_LABELS:
        module_key = workflow_instance.source_type
      if route_name is None and workflow_instance.source_type == "report" and workflow_instance.source_id is not None:
        route_name = "reports"
        route_query = {"selected": str(workflow_instance.source_id)}
      if route_name is None and workflow_instance.source_type == "task" and workflow_instance.source_id is not None:
        route_name = "task-center"
        route_query = {"tab": "tracking", "selected": str(workflow_instance.source_id)}
      if object_id is None:
        object_id = workflow_instance.source_id or message.source_id

    if module_key is None:
      module_key = message.source_type
    if module_label is None:
      module_label = MODULE_LABELS.get(module_key, "系统消息")
    if object_type is None:
      object_type = message.source_type
    if object_id is None:
      object_id = message.source_id
    if object_label is None:
      object_label = message.title

    if route_name is None and message.source_id is not None:
      if message.source_type == "task":
        route_name = "task-center"
        route_query = {"tab": "tracking", "selected": str(message.source_id)}
      elif message.source_type == "report":
        route_name = "reports"
        route_query = {"selected": str(message.source_id)}
      elif message.source_type == "announcement":
        route_name = "overview"
        route_query = {"announcement": str(message.source_id)}

    return {
      "module_key": module_key,
      "module_label": module_label,
      "object_type": object_type,
      "object_id": object_id,
      "object_label": object_label,
      "target": {
        "route_name": route_name,
        "route_query": route_query,
        "can_navigate": route_name is not None,
      },
    }

  def _build_source_counts(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter = Counter(item["source"]["module_key"] for item in items)
    labels = {
      item["source"]["module_key"]: item["source"]["module_label"]
      for item in items
    }
    return [
      {
        "source_type": source_type,
        "label": labels.get(source_type, MODULE_LABELS.get(source_type, source_type)),
        "count": counter[source_type],
      }
      for source_type in sorted(counter)
    ]

  def _matches_source_type(self, *, item: dict[str, Any], source_type: str | None) -> bool:
    if source_type is None:
      return True
    return item["source"]["module_key"] == source_type

  def _matches_state(self, *, item: dict[str, Any], state: MessageStateFilter) -> bool:
    receipt_state = item["receipt_state"]
    if state == "all":
      return True
    if state == "unread":
      return not receipt_state["is_read"]
    if state == "read":
      return receipt_state["is_read"]
    if state == "unacknowledged":
      return not receipt_state["is_acknowledged"]
    return receipt_state["is_acknowledged"]

  def _matches_channel(self, *, item: dict[str, Any], channel: NotificationChannel | None) -> bool:
    if channel is None:
      return True
    return any(delivery.channel == channel for delivery in item["deliveries"])

  def _matches_delivery_status(
    self,
    *,
    item: dict[str, Any],
    delivery_status: NotificationDeliveryStatus | None,
  ) -> bool:
    if delivery_status is None:
      return True
    return item["delivery_state"] == delivery_status

  def _matches_created_at(
    self,
    *,
    item: dict[str, Any],
    created_from: datetime | None,
    created_to: datetime | None,
  ) -> bool:
    created_at = item["created_at"]
    if created_from is not None and created_at < created_from:
      return False
    if created_to is not None and created_at > created_to:
      return False
    return True

  def _read_payload_str(self, payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None

  def _read_route_query(self, value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
      return {}
    return {
      str(key): str(raw_value)
      for key, raw_value in value.items()
      if raw_value is not None
    }

  def _coerce_uuid(self, value: Any) -> UUID | None:
    if value is None or isinstance(value, UUID):
      return value
    try:
      return UUID(str(value))
    except (TypeError, ValueError):
      return None
