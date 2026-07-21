# Active Task: Task 1-T — Test ADMIN bypass

**Status:** in-progress
**Plan:** memory-bank/knowledge/plans/2026-07-21-template-self-review-fix-plan.md
**Depends on:** Task 1 ✅

## Objective
Write test to verify ADMIN can review template tasks they are assignee of.

## Deliverables
1. Append test_admin_can_review_any_template_task to test_p1_10_template_review_safety.py
2. Run test, verify PASS

## Acceptance Gate
- Test passes: ADMIN reviews template task where actor == assignee_id → status DONE
