from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
  AppValidationError,
  AuthenticationError,
  AuthorizationError,
  ConfigurationError,
  ConflictError,
  NotFoundError,
)
from app.services.workflow_command_receipt_service import (
  CommandPayloadConflictError,
  WorkflowCommandReceiptService,
)
from app.services.workflow_event_context import bind_workflow_event_context
from app.services.workflow_operational_incident_service import WorkflowOperationalIncidentService


CommandOperation = Callable[[], Awaitable[dict[str, Any]]]
_REPLAYABLE_ERRORS = {
  error_type.__name__: error_type
  for error_type in (
    AppValidationError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    ConflictError,
    NotFoundError,
  )
}


class WorkflowCommandExecutor:
  """Run a workflow command and its receipt in one database transaction."""

  def __init__(self, session: AsyncSession) -> None:
    self._session = session
    self._receipts = WorkflowCommandReceiptService(session)

  async def execute(
    self,
    *,
    command_id: str,
    command_type: str,
    payload: dict[str, Any],
    operation: CommandOperation,
    actor_user_id: UUID | None = None,
    system_actor: str | None = None,
    aggregate_type: str | None = None,
    aggregate_id: UUID | None = None,
  ) -> dict[str, Any]:
    try:
      claim = await self._receipts.claim(
        command_id=command_id,
        command_type=command_type,
        payload=payload,
        actor_user_id=actor_user_id,
        system_actor=system_actor,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
      )
    except CommandPayloadConflictError as exc:
      receipt_id = exc.receipt.id
      actor_key = exc.receipt.actor_key
      receipt_command_type = exc.receipt.command_type
      receipt_command_id = exc.receipt.command_id
      original_payload_hash = exc.receipt.payload_hash
      await self._session.rollback()
      await WorkflowOperationalIncidentService(self._session).record(
        category="receipt_conflict",
        identity={
          "actor_key": actor_key,
          "command_type": receipt_command_type,
          "command_id": receipt_command_id,
        },
        severity="error",
        command_receipt_id=receipt_id,
        details={
          "original_payload_hash": original_payload_hash,
          "attempted_payload_hash": exc.attempted_payload_hash,
        },
      )
      await self._session.commit()
      raise ConflictError(str(exc)) from exc
    if claim.is_replay:
      if claim.receipt.status == "succeeded":
        return dict(claim.receipt.result or {})
      if claim.receipt.status == "failed":
        message = str((claim.receipt.error or {}).get("message") or "命令首次执行失败。")
        error_type = str((claim.receipt.error or {}).get("type") or "")
        error_class = _REPLAYABLE_ERRORS.get(error_type)
        if error_class is not None:
          raise error_class(message)
        raise ConflictError(f"该 command 已失败，不能重复执行：{message}")
      raise ConflictError("相同 command 正在处理中，请稍后重试。")

    try:
      with bind_workflow_event_context(command_id=command_id):
        result = await operation()
      resolved_aggregate_id = aggregate_id
      if resolved_aggregate_id is None and result.get("instance_id"):
        try:
          resolved_aggregate_id = UUID(str(result["instance_id"]))
        except ValueError:
          resolved_aggregate_id = None
      await self._receipts.complete(
        receipt=claim.receipt,
        result=result,
        aggregate_type=aggregate_type,
        aggregate_id=resolved_aggregate_id,
      )
      await self._session.commit()
      return result
    except Exception as exc:
      await self._session.rollback()
      failure_claim = await self._receipts.claim(
        command_id=command_id,
        command_type=command_type,
        payload=payload,
        actor_user_id=actor_user_id,
        system_actor=system_actor,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
      )
      if not failure_claim.is_replay or failure_claim.receipt.status == "processing":
        await self._receipts.fail(
          receipt=failure_claim.receipt,
          error={"type": type(exc).__name__, "message": str(exc)},
        )
        if type(exc).__name__ not in _REPLAYABLE_ERRORS:
          await WorkflowOperationalIncidentService(self._session).record(
            category="coordinator_failure",
            identity={
              "command_type": command_type,
              "command_id": command_id,
              "actor_key": failure_claim.receipt.actor_key,
            },
            severity="error",
            node_instance_id=(
              aggregate_id if aggregate_type == "workflow_node" else None
            ),
            command_receipt_id=failure_claim.receipt.id,
            details={
              "aggregate_type": aggregate_type,
              "aggregate_id": str(aggregate_id) if aggregate_id is not None else None,
              "error_type": type(exc).__name__,
              "error_message": str(exc)[:500],
            },
          )
        await self._session.commit()
      raise
