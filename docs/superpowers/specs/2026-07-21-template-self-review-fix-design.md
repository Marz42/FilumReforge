# Spec: Template Task Self-Review Deadlock Fix

**Date:** 2026-07-21  
**Status:** Draft  
**Scope:** `backend/app/services/task_service.py`

---

## Problem Statement

When a template graph task is submitted, `_activate_template_review` walks a fallback candidate chain to find a non-assignee reviewer. If **every** candidate equals `assignee_id` (or is inactive/missing), the task enters `BLOCKED (no_eligible_reviewer)`. This is Scenario A:

> `creator == assignee`, no supervisor, no dept head, no distinct workflow admin, no system admins.

The assignee cannot self-recover. The only exit is an admin calling `reassign_task_reviewer` — but if there *are* no admins, the task is permanently stuck.

A related but distinct problem (Scenario B-edge): even when a non-assignee reviewer is found and the task reaches `REVIEW`, `_ensure_task_reviewer` at line 2445 unconditionally raises `ConflictError("Self-review is not permitted for template tasks")` for `actor.id == assignee_id` **before** checking whether that actor also happens to be the designated `reviewer_id`. The check at 2449 is never reached for the assignee. This means that if somehow `assignee_id == reviewer_id` (data inconsistency), review is permanently blocked.

---

## Flow Trace

```
submit_deliverable
  └─ line 3332-3333: initial_reviewer_ids defaults to [task.creator_id]
  └─ _activate_template_review
        └─ _review_fallback_candidates → ordered list:
             1. configured_reviewer  (initial_reviewer_ids)
             2. supervisor           (ReportingLine SOLID primary)
             3. department_head      (Department.manager_id)
             4. workflow_admin       (template.created_by or instance.initiator_user_id)
             5. system_admins        (User.role == ADMIN, asc created_at)
        └─ for each candidate:
             • candidate_id == assignee_id  → excluded (self-review log, continue)
             • candidate missing / inactive → excluded (log, continue)
             • first surviving candidate   → selected; task → REVIEW
        └─ if selected is None → task → BLOCKED (no_eligible_reviewer)

review_task_deliverable
  └─ _ensure_task_reviewer
        └─ line 2444-2446: if template task AND actor == assignee → ConflictError (EARLY EXIT)
        └─ line 2449:       if actor == reviewer_id → OK
        └─ else             → AuthorizationError
```

### Scenario Matrix

| Scenario | creator | assignee | Candidates surviving | Outcome |
|----------|---------|----------|----------------------|---------|
| A | == assignee | — | none | BLOCKED — **deadlock** |
| B | == assignee | — | supervisor (≠ assignee) | REVIEW; supervisor reviews — **correct** |
| C | ≠ assignee | — | creator | REVIEW; creator reviews — **correct** |
| D | == assignee | — | no admin; reassign by admin impossible | permanent deadlock |

---

## Options Considered

### Option 1 — Admin bypass in `_ensure_task_reviewer`

Add a role check *before* the self-review guard: any `ADMIN`-role actor may review any template task regardless of `assignee_id`.

```python
# _ensure_task_reviewer (line 2439)
if self._is_template_graph_task(task):
    if actor.role == UserRole.ADMIN:          # ← NEW: admin bypass
        return
    if actor.id == task.assignee_id:
        raise ConflictError("Self-review is not permitted for template tasks")
    ...
```

**Pros:** Single-line insertion; no change to activation logic; consistent with the existing `MANAGEMENT_ROLES` bypass for non-template tasks (line 2452).  
**Cons:** Does not resolve Scenario A (BLOCKED) — admins still need to manually reassign first, then review. Only widens *who* can review once the task is in REVIEW; does not prevent blocking.

---

### Option 2 — Audited self-review fallback in `_activate_template_review`

After exhausting all candidates, if `assignee_id` was the *only reason* every candidate was excluded (i.e., all candidates map to the same person), allow the assignee to self-review, writing an explicit audit log entry.

```python
# _activate_template_review — after the for-loop, before the BLOCKED branch
if selected is None:
    all_excluded_as_self = all(
        cid == task.assignee_id
        for _, cid in await self._review_fallback_candidates(...)
    )
    if all_excluded_as_self:
        # logged self-review fallback
        metadata["reviewer_id"] = str(task.assignee_id)
        metadata["reviewer_ids"] = [str(task.assignee_id)]
        metadata["reviewer_source"] = "self_review_fallback"
        metadata["self_review_fallback"] = True
        task.extra_metadata = metadata
        task.status = TaskStatus.REVIEW
        task.blocked_reason = None
        await self._create_task_log(...)
        return task.assignee_id
```

`_ensure_task_reviewer` must also be patched to allow self-review when `metadata["self_review_fallback"] is True`.

**Pros:** Keeps tasks moving without admin intervention; fully auditable; preserves the stricter path for tasks where other reviewers exist.  
**Cons:** Two-site change (activation + guard); semantically weakens the "no self-review" invariant — even if only in a logged fallback path; may require policy documentation update.

---

### Option 3 — Seed `initial_reviewer_ids` with system admins at submit time

At line 3332-3333, instead of falling back only to `[task.creator_id]`, also append all `ADMIN`-role user IDs. `_review_fallback_candidates` then ranks them in the standard priority order.

```python
# submit_deliverable, line 3332-3333
if not initial_reviewer_ids:
    admin_ids = list(await self._session.scalars(
        select(User.id).where(User.role == UserRole.ADMIN)
        .order_by(User.created_at.asc())
    ))
    initial_reviewer_ids = [task.creator_id] + admin_ids
```

**Pros:** No change to `_activate_template_review` or `_ensure_task_reviewer`; admin-seeded candidates appear early in the priority chain and displace the creator-as-assignee problem naturally.  
**Cons:** `_review_fallback_candidates` already appends `system_admins` at position 5 (line 2344-2351); duplicating them at position 1 is redundant and adds an extra query at submit time. Does not help when there are genuinely zero admins (Scenario D).

---

## Recommendation

**Option 1 + targeted amendment to Option 2's fallback condition.**

### Rationale

The root issue has two independent failure modes that need separate fixes:

1. **BLOCKED state (Scenario A/D)** — no candidate survives; task is stuck.  
   Fix: implement the `self_review_fallback` path from Option 2, activated **only** when `_review_fallback_candidates` returns an empty surviving set *and* the exclusion cause is exclusively self-review (not inactive accounts or missing users). This is narrow, audited, and reversible by an admin reassign if desired.

2. **REVIEW state but admin wants to unblock manually** — fix: Option 1's admin bypass in `_ensure_task_reviewer`. This is already consistent with non-template task behaviour and has zero blast radius outside template tasks.

Option 3 is redundant because `system_admins` are already last in the fallback chain; seeding them into `initial_reviewer_ids` only creates duplicate DB queries.

### Minimal Change Surface

| Site | Change | Lines affected |
|------|--------|---------------|
| `_ensure_task_reviewer` | Add `actor.role == ADMIN → return` before self-review guard | ~1 line before 2445 |
| `_activate_template_review` | After loop, if `selected is None` and all exclusions were self-review, set `self_review_fallback=True` and select assignee | ~15 lines after 2391 |
| `_ensure_task_reviewer` | Allow actor == assignee when `metadata["self_review_fallback"] is True` | ~3 lines, reorder guard |

Total: ~19 lines, all within `task_service.py`. No schema changes, no new endpoints.

---

## Acceptance Criteria

1. Scenario A: task reaches `REVIEW` with `reviewer_source = "self_review_fallback"`; assignee can call `review_task_deliverable` without error.
2. Scenario B/C: unchanged behaviour — non-assignee reviewer is selected as before.
3. An ADMIN-role actor can always call `review_task_deliverable` on any template task in REVIEW, regardless of `assignee_id`.
4. Audit log entry with `action: "self_review_fallback_activated"` is written whenever the fallback path is taken.
5. If candidates are excluded for reasons *other than* self-review (inactive, missing), task still enters BLOCKED — the fallback only fires for the pure single-user scenario.

---

## Out of Scope

- Changing the `reassign_task_reviewer` endpoint.
- Modifying `_review_fallback_candidates` candidate order.
- Any frontend / notification changes.
