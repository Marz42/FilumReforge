from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from app.core.enums import (
  NotificationDeliveryStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.services.workflow_node_handlers import (
  WorkflowCapabilityOperationError,
  WorkflowCapabilityOutcome,
  WorkflowCapabilityResult,
)


class NotificationCompletionPolicy(StrEnum):
  QUEUED = "queued"
  SENT = "sent"
  ALL_CHANNELS_SUCCESS = "all_channels_success"


def _result(
  *,
  capability_key: str,
  outcome: WorkflowCapabilityOutcome,
  engine_state: WorkflowNodeEngineState,
  business_state: WorkflowNodeBusinessState,
  result: Mapping[str, object] | None = None,
  diagnostics: Mapping[str, object] | None = None,
  side_effects: tuple[str, ...] = (),
) -> WorkflowCapabilityResult:
  return WorkflowCapabilityResult(
    capability_key=capability_key,
    outcome=outcome,
    engine_state=engine_state,
    business_state=business_state,
    result=MappingProxyType(dict(result or {})),
    diagnostics=MappingProxyType(dict(diagnostics or {})),
    side_effects=side_effects,
  )


class DeliverableCapabilityHandler:
  """Pure version/review policy for the single-row Deliverable projection."""

  capability_key = "deliverable"
  compensation = "preserve_deliverable_history"

  @staticmethod
  def _submission_history(
    payload: Mapping[str, object],
    *,
    current_signature: str | None,
  ) -> list[dict[str, object]]:
    raw_history = payload.get("submission_history")
    history = (
      [deepcopy(dict(item)) for item in raw_history if isinstance(item, Mapping)]
      if isinstance(raw_history, list)
      else []
    )
    if not history and isinstance(payload.get("latest_submission"), Mapping):
      history = [deepcopy(dict(payload["latest_submission"]))]
    for index, item in enumerate(history, start=1):
      item.setdefault("version", index)
    if history and current_signature and not history[-1].get("signature"):
      history[-1]["signature"] = current_signature
    return history

  @staticmethod
  def _review_history(payload: Mapping[str, object]) -> list[dict[str, object]]:
    raw_history = payload.get("review_history")
    if isinstance(raw_history, list):
      return [deepcopy(dict(item)) for item in raw_history if isinstance(item, Mapping)]
    latest_review = payload.get("latest_review")
    if isinstance(latest_review, Mapping):
      return [deepcopy(dict(latest_review))]
    return []

  def submit(
    self,
    *,
    payload: Mapping[str, object],
    submitted_by_user_id: str,
    submitted_at: datetime,
    summary: str | None,
    attachment_ids: list[str],
    signature_prefix: str,
    current_signature: str | None = None,
    auto_accept: bool = False,
  ) -> WorkflowCapabilityResult:
    next_payload = deepcopy(dict(payload))
    history = self._submission_history(
      next_payload,
      current_signature=current_signature,
    )
    version = max(
      [int(item.get("version", 0)) for item in history if str(item.get("version", "")).isdigit()],
      default=0,
    ) + 1
    signature = f"{signature_prefix}:submission:{version}"
    submission: dict[str, object] = {
      "version": version,
      "signature": signature,
      "submitted_at": submitted_at.isoformat(),
      "submitted_by_user_id": submitted_by_user_id,
      "summary": summary,
      "attachment_ids": list(attachment_ids),
    }
    history.append(submission)
    next_payload.update(
      {
        "schema_version": 2,
        "current_submission_version": version,
        "latest_submission": deepcopy(submission),
        "submission_history": history,
      }
    )

    review_history = self._review_history(next_payload)
    if auto_accept:
      review = {
        "action": "auto_accept_submission",
        "submission_version": version,
        "submission_signature": signature,
        "comment": None,
        "quality_score": None,
        "reviewed_at": submitted_at.isoformat(),
        "reviewed_by_user_id": submitted_by_user_id,
      }
      review_history.append(review)
      next_payload.update(
        {
          "latest_review": review,
          "review_history": review_history,
          "accepted_submission_version": version,
          "accepted_submission_signature": signature,
          "accepted_submission": deepcopy(submission),
        }
      )
      outcome = WorkflowCapabilityOutcome.SUCCEEDED
      engine_state = WorkflowNodeEngineState.COMPLETED
      business_state = WorkflowNodeBusinessState.DONE
    else:
      next_payload["review_history"] = review_history
      outcome = WorkflowCapabilityOutcome.WAITING
      engine_state = WorkflowNodeEngineState.ACKNOWLEDGED
      business_state = WorkflowNodeBusinessState.PENDING_REVIEW

    return _result(
      capability_key=self.capability_key,
      outcome=outcome,
      engine_state=engine_state,
      business_state=business_state,
      result={
        "deliverable_payload": next_payload,
        "current_submission": submission,
        "current_submission_version": version,
        "current_submission_signature": signature,
      },
      diagnostics={"auto_accept": auto_accept},
    )

  def review(
    self,
    *,
    payload: Mapping[str, object],
    reviewed_by_user_id: str,
    reviewed_at: datetime,
    approve: bool,
    comment: str | None,
    quality_score: int | None = None,
    rework_count: int | None = None,
    current_signature: str | None = None,
  ) -> WorkflowCapabilityResult:
    if approve and quality_score is not None and quality_score not in {1, 2, 3, 4, 5}:
      raise WorkflowCapabilityOperationError("Deliverable 质量评分必须在 1 到 5 之间。")
    if not approve and not (comment or "").strip():
      raise WorkflowCapabilityOperationError("Deliverable 打回返工必须填写原因。")
    next_payload = deepcopy(dict(payload))
    current_submission = next_payload.get("latest_submission")
    if not isinstance(current_submission, Mapping):
      raise WorkflowCapabilityOperationError("Deliverable 缺少可评审的当前提交版本。")
    history = self._submission_history(
      next_payload,
      current_signature=current_signature,
    )
    submission = deepcopy(history[-1] if history else dict(current_submission))
    version = int(submission.get("version") or next_payload.get("current_submission_version") or 1)
    submission.setdefault("version", version)
    if current_signature and not submission.get("signature"):
      submission["signature"] = current_signature
    signature = str(submission.get("signature") or "") or None
    next_payload["latest_submission"] = deepcopy(submission)
    next_payload["submission_history"] = history or [deepcopy(submission)]
    next_payload["current_submission_version"] = version
    action = "approve_completion" if approve else "return_for_rework"
    review: dict[str, object] = {
      "action": action,
      "submission_version": version,
      "submission_signature": signature,
      "comment": comment,
      "quality_score": quality_score,
      "reviewed_at": reviewed_at.isoformat(),
      "reviewed_by_user_id": reviewed_by_user_id,
    }
    if rework_count is not None:
      review["rework_count"] = rework_count
      next_payload["rework_count"] = rework_count
    review_history = self._review_history(next_payload)
    review_history.append(review)
    next_payload.update(
      {
        "schema_version": 2,
        "latest_review": review,
        "review_history": review_history,
      }
    )
    if approve:
      next_payload.update(
        {
          "accepted_submission_version": version,
          "accepted_submission_signature": signature,
          "accepted_submission": submission,
        }
      )
      outcome = WorkflowCapabilityOutcome.SUCCEEDED
      engine_state = WorkflowNodeEngineState.COMPLETED
      business_state = WorkflowNodeBusinessState.DONE
    else:
      outcome = WorkflowCapabilityOutcome.WAITING
      engine_state = WorkflowNodeEngineState.ACTIVATED
      business_state = WorkflowNodeBusinessState.RETURNED_FOR_REWORK

    return _result(
      capability_key=self.capability_key,
      outcome=outcome,
      engine_state=engine_state,
      business_state=business_state,
      result={
        "deliverable_payload": next_payload,
        "review": review,
        "reviewed_submission_version": version,
        "reviewed_submission_signature": signature,
      },
    )

  def fail(self, *, payload: Mapping[str, object], code: str) -> WorkflowCapabilityResult:
    return _result(
      capability_key=self.capability_key,
      outcome=WorkflowCapabilityOutcome.FAILED,
      engine_state=WorkflowNodeEngineState.FAILED,
      business_state=WorkflowNodeBusinessState.PENDING_REVIEW,
      result={"deliverable_payload": deepcopy(dict(payload))},
      diagnostics={"failure_code": code},
    )

  def retry(self, *, payload: Mapping[str, object]) -> WorkflowCapabilityResult:
    return _result(
      capability_key=self.capability_key,
      outcome=WorkflowCapabilityOutcome.WAITING,
      engine_state=WorkflowNodeEngineState.ACTIVATED,
      business_state=WorkflowNodeBusinessState.RETURNED_FOR_REWORK,
      result={"deliverable_payload": deepcopy(dict(payload))},
    )

  def cancel(self, *, payload: Mapping[str, object]) -> WorkflowCapabilityResult:
    return _result(
      capability_key=self.capability_key,
      outcome=WorkflowCapabilityOutcome.CANCELLED,
      engine_state=WorkflowNodeEngineState.TERMINATED,
      business_state=WorkflowNodeBusinessState.CANCELLED,
      result={"deliverable_payload": deepcopy(dict(payload))},
      side_effects=(self.compensation,),
    )


class NotificationCapabilityHandler:
  """Pure completion policy for a notification message and all its deliveries."""

  capability_key = "notification"
  compensation = "cancel_pending_deliveries"

  @staticmethod
  def resolve_policy(payload: Mapping[str, object]) -> NotificationCompletionPolicy:
    raw_policy = payload.get("completion_policy")
    if raw_policy is None:
      return NotificationCompletionPolicy.ALL_CHANNELS_SUCCESS
    try:
      return NotificationCompletionPolicy(str(raw_policy))
    except ValueError as exc:
      raise WorkflowCapabilityOperationError(
        f"Notification 使用了未知 completion_policy={raw_policy}。"
      ) from exc

  def evaluate(
    self,
    *,
    policy: NotificationCompletionPolicy,
    enqueued: bool,
    delivery_statuses: list[NotificationDeliveryStatus],
  ) -> WorkflowCapabilityResult:
    counts = {
      status.value: sum(1 for current in delivery_statuses if current == status)
      for status in NotificationDeliveryStatus
    }
    diagnostics: dict[str, object] = {
      "completion_policy": policy.value,
      "enqueued": enqueued,
      "delivery_count": len(delivery_statuses),
      "delivery_counts": counts,
    }

    if policy == NotificationCompletionPolicy.QUEUED:
      succeeded = enqueued
    elif policy == NotificationCompletionPolicy.SENT:
      succeeded = NotificationDeliveryStatus.SENT in delivery_statuses
    else:
      succeeded = bool(delivery_statuses) and all(
        status == NotificationDeliveryStatus.SENT for status in delivery_statuses
      )

    if succeeded:
      return _result(
        capability_key=self.capability_key,
        outcome=WorkflowCapabilityOutcome.SUCCEEDED,
        engine_state=WorkflowNodeEngineState.COMPLETED,
        business_state=WorkflowNodeBusinessState.DONE,
        diagnostics=diagnostics,
      )

    failed = NotificationDeliveryStatus.FAILED in delivery_statuses
    terminal_failure = failed and (
      policy == NotificationCompletionPolicy.ALL_CHANNELS_SUCCESS
      or not any(
        status in {NotificationDeliveryStatus.PENDING, NotificationDeliveryStatus.RETRYING}
        for status in delivery_statuses
      )
    )
    if terminal_failure:
      return _result(
        capability_key=self.capability_key,
        outcome=WorkflowCapabilityOutcome.FAILED,
        engine_state=WorkflowNodeEngineState.FAILED,
        business_state=WorkflowNodeBusinessState.ASSIGNED,
        diagnostics=diagnostics,
      )
    return _result(
      capability_key=self.capability_key,
      outcome=WorkflowCapabilityOutcome.WAITING,
      engine_state=WorkflowNodeEngineState.ACTIVATED,
      business_state=WorkflowNodeBusinessState.ASSIGNED,
      diagnostics=diagnostics,
    )

  def retry(
    self,
    *,
    delivery_statuses: list[NotificationDeliveryStatus],
  ) -> WorkflowCapabilityResult:
    if NotificationDeliveryStatus.FAILED not in delivery_statuses:
      raise WorkflowCapabilityOperationError("Notification 只有失败投递可以重试。")
    return _result(
      capability_key=self.capability_key,
      outcome=WorkflowCapabilityOutcome.WAITING,
      engine_state=WorkflowNodeEngineState.ACTIVATED,
      business_state=WorkflowNodeBusinessState.ASSIGNED,
      side_effects=("retry_failed_deliveries",),
    )

  def cancel(self) -> WorkflowCapabilityResult:
    return _result(
      capability_key=self.capability_key,
      outcome=WorkflowCapabilityOutcome.CANCELLED,
      engine_state=WorkflowNodeEngineState.TERMINATED,
      business_state=WorkflowNodeBusinessState.CANCELLED,
      side_effects=(self.compensation,),
    )
