# Active Task: Task 2 — Self-review fallback in _activate_template_review

**Status:** in-progress
**Plan:** memory-bank/knowledge/plans/2026-07-21-template-self-review-fix-plan.md
**Depends on:** Task 1 ✅, Task 1-T ✅

## Objective
When all reviewer candidates are excluded solely because they equal assignee_id, allow audited self-review fallback instead of BLOCKED.

## Deliverables
1. Insert ~15 lines after candidate loop in _activate_template_review
   - Re-fetch candidates, check if all exclusions were self-review only
   - If yes: set self_review_fallback=True, reviewer_id=assignee, status=REVIEW, create audit log
   - If no: keep existing BLOCKED path
2. Run tests to verify no regressions

## Acceptance Gate
- Scenario A (sole user): task enters REVIEW with self_review_fallback
- Existing scenarios (B/C): unchanged behavior
- Non-self-review exclusions: still BLOCKED
