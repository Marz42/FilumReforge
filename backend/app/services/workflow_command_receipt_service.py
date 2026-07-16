from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models import WorkflowCommandReceipt


class CommandPayloadConflictError(ConflictError):
  def __init__(
    self,
    *,
    receipt: WorkflowCommandReceipt,
    attempted_payload_hash: str,
  ) -> None:
    super().__init__("同一 command id 不能携带不同 payload。")
    self.receipt = receipt
    self.attempted_payload_hash = attempted_payload_hash


def _canonical_json_default(value: object) -> str:
  if isinstance(value, UUID):
    return str(value)
  if isinstance(value, datetime):
    normalized = value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.isoformat().replace("+00:00", "Z")
  if isinstance(value, date):
    return value.isoformat()
  if isinstance(value, Enum):
    return str(value.value)
  raise TypeError(f"不支持的 command payload 类型：{type(value).__name__}")


def canonical_command_payload(payload: dict[str, Any]) -> str:
  return json.dumps(
    payload,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
    default=_canonical_json_default,
  )


def command_payload_hash(payload: dict[str, Any]) -> str:
  return hashlib.sha256(canonical_command_payload(payload).encode("utf-8")).hexdigest()


@dataclass(slots=True, frozen=True)
class CommandReceiptClaim:
  receipt: WorkflowCommandReceipt
  is_replay: bool

  @property
  def is_terminal(self) -> bool:
    return self.receipt.status in {"succeeded", "failed"}


class WorkflowCommandReceiptService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  @staticmethod
  def actor_key(*, actor_user_id: UUID | None, system_actor: str | None = None) -> str:
    if actor_user_id is not None:
      return f"user:{actor_user_id}"
    normalized = (system_actor or "").strip().lower()
    if not normalized:
      raise ConflictError("系统命令必须提供稳定的 system_actor。")
    key = f"system:{normalized}"
    if len(key) > 64:
      raise ConflictError("system_actor 过长。")
    return key

  async def _find(
    self,
    *,
    actor_key: str,
    command_type: str,
    command_id: str,
  ) -> WorkflowCommandReceipt | None:
    return await self._session.scalar(
      select(WorkflowCommandReceipt).where(
        WorkflowCommandReceipt.actor_key == actor_key,
        WorkflowCommandReceipt.command_type == command_type,
        WorkflowCommandReceipt.command_id == command_id,
      )
    )

  @staticmethod
  def _assert_same_payload(receipt: WorkflowCommandReceipt, payload_hash: str) -> None:
    if receipt.payload_hash != payload_hash:
      raise CommandPayloadConflictError(
        receipt=receipt,
        attempted_payload_hash=payload_hash,
      )

  async def claim(
    self,
    *,
    command_id: str,
    command_type: str,
    payload: dict[str, Any],
    actor_user_id: UUID | None = None,
    system_actor: str | None = None,
    aggregate_type: str | None = None,
    aggregate_id: UUID | None = None,
  ) -> CommandReceiptClaim:
    normalized_command_id = command_id.strip()
    normalized_command_type = command_type.strip()
    if not normalized_command_id or len(normalized_command_id) > 128:
      raise ConflictError("command_id 不能为空且不得超过 128 个字符。")
    if not normalized_command_type or len(normalized_command_type) > 64:
      raise ConflictError("command_type 不能为空且不得超过 64 个字符。")

    resolved_actor_key = self.actor_key(
      actor_user_id=actor_user_id,
      system_actor=system_actor,
    )
    payload_hash = command_payload_hash(payload)
    existing = await self._find(
      actor_key=resolved_actor_key,
      command_type=normalized_command_type,
      command_id=normalized_command_id,
    )
    if existing is not None:
      self._assert_same_payload(existing, payload_hash)
      return CommandReceiptClaim(existing, True)

    receipt = WorkflowCommandReceipt(
      command_id=normalized_command_id,
      command_type=normalized_command_type,
      actor_key=resolved_actor_key,
      actor_user_id=actor_user_id,
      payload_hash=payload_hash,
      status="processing",
      aggregate_type=aggregate_type,
      aggregate_id=aggregate_id,
      result={},
      error={},
    )
    try:
      async with self._session.begin_nested():
        self._session.add(receipt)
        await self._session.flush()
    except IntegrityError:
      existing = await self._find(
        actor_key=resolved_actor_key,
        command_type=normalized_command_type,
        command_id=normalized_command_id,
      )
      if existing is None:
        raise
      self._assert_same_payload(existing, payload_hash)
      return CommandReceiptClaim(existing, True)
    return CommandReceiptClaim(receipt, False)

  async def complete(
    self,
    *,
    receipt: WorkflowCommandReceipt,
    result: dict[str, Any],
    aggregate_type: str | None = None,
    aggregate_id: UUID | None = None,
  ) -> WorkflowCommandReceipt:
    if receipt.status == "succeeded":
      return receipt
    if receipt.status == "failed":
      raise ConflictError("已失败的 command receipt 不能改写为成功。")
    receipt.status = "succeeded"
    receipt.result = dict(result)
    receipt.error = {}
    receipt.aggregate_type = aggregate_type or receipt.aggregate_type
    receipt.aggregate_id = aggregate_id or receipt.aggregate_id
    receipt.completed_at = datetime.now(UTC)
    await self._session.flush()
    return receipt

  async def fail(
    self,
    *,
    receipt: WorkflowCommandReceipt,
    error: dict[str, Any],
  ) -> WorkflowCommandReceipt:
    if receipt.status == "failed":
      return receipt
    if receipt.status == "succeeded":
      raise ConflictError("已成功的 command receipt 不能改写为失败。")
    receipt.status = "failed"
    receipt.result = {}
    receipt.error = dict(error)
    receipt.completed_at = datetime.now(UTC)
    await self._session.flush()
    return receipt
