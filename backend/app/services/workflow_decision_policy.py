from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from app.services.workflow_node_handlers import WorkflowDecisionSemantic


@dataclass(frozen=True, slots=True)
class WorkflowDecisionPolicyResult:
  allowed: bool
  code: str
  diagnostics: Mapping[str, object] = field(default_factory=dict)


def evaluate_actor_overlap(
  *,
  semantic: WorkflowDecisionSemantic,
  actor_user_id: str | None,
  contributor_user_ids: list[str],
  decision_maker_user_ids: list[str],
  allow_contributor_cosign: bool = False,
) -> WorkflowDecisionPolicyResult:
  """Evaluate actor overlap against the current decision subject only."""
  contributors = list(dict.fromkeys(contributor_user_ids))
  decision_makers = list(dict.fromkeys(decision_maker_user_ids))
  actor_is_contributor = actor_user_id is not None and actor_user_id in contributors
  non_contributor_decision_makers = [
    user_id for user_id in decision_makers if user_id not in contributors
  ]
  diagnostics: dict[str, object] = {
    "decision_semantic": semantic.value,
    "actor_user_id": actor_user_id,
    "contributor_user_ids": contributors,
    "decision_maker_user_ids": decision_makers,
    "actor_is_contributor": actor_is_contributor,
    "non_contributor_decision_maker_count": len(non_contributor_decision_makers),
  }

  def result(*, allowed: bool, code: str) -> WorkflowDecisionPolicyResult:
    return WorkflowDecisionPolicyResult(
      allowed=allowed,
      code=code,
      diagnostics=MappingProxyType({**diagnostics, "policy_code": code}),
    )

  if actor_user_id is None:
    return result(allowed=False, code="missing_actor")
  if not decision_makers:
    return result(allowed=False, code="no_eligible_decision_maker")
  if actor_user_id not in decision_makers:
    return result(allowed=False, code="actor_not_decision_maker")

  if semantic == WorkflowDecisionSemantic.DELIVERABLE_ACCEPTANCE:
    if actor_is_contributor and not non_contributor_decision_makers:
      return result(allowed=False, code="submitter_cannot_be_only_acceptor")
    return result(allowed=True, code="deliverable_acceptance_allowed")

  if semantic == WorkflowDecisionSemantic.BUSINESS_APPROVAL:
    if actor_is_contributor:
      return result(allowed=False, code="contributor_cannot_approve_business_subject")
    return result(allowed=True, code="business_approval_allowed")

  if semantic == WorkflowDecisionSemantic.COSIGN:
    if actor_is_contributor and not allow_contributor_cosign:
      return result(allowed=False, code="contributor_cosign_not_enabled")
    if actor_is_contributor and not non_contributor_decision_makers:
      return result(allowed=False, code="contributor_cannot_be_only_cosign_decider")
    return result(allowed=True, code="cosign_allowed")

  return result(allowed=True, code="overlap_not_restricted")
