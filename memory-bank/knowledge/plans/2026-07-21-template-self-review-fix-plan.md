# Implementation Plan: Template Self-Review Deadlock Fix

**Date:** 2026-07-21  
**Spec:** `docs/superpowers/specs/2026-07-21-template-self-review-fix-design.md`  
**Target file:** `backend/app/services/task_service.py`  
**Test file:** `backend/tests/test_p1_10_template_review_safety.py`

---

## Task 1 — Add ADMIN bypass guard in `_ensure_task_reviewer`

**File:** `backend/app/services/task_service.py`  
**Lines affected:** Insert 1 line before line 2445  
**Estimated time:** 2 minutes

### Change

Current code (lines 2444–2451):

```python
    if self._is_template_graph_task(task):
      if actor.id == task.assignee_id:
        raise ConflictError("Self-review is not permitted for template tasks")
      metadata = self._copy_task_metadata(task)
      reviewer_id = self._read_uuid_metadata(metadata, "reviewer_id")
      if reviewer_id is not None and actor.id == reviewer_id:
        return
      raise AuthorizationError("当前账号不是该模板任务的指定验收人。")
```

Replace with:

```python
    if self._is_template_graph_task(task):
      if actor.role == UserRole.ADMIN:
        return
      if actor.id == task.assignee_id:
        raise ConflictError("Self-review is not permitted for template tasks")
      metadata = self._copy_task_metadata(task)
      reviewer_id = self._read_uuid_metadata(metadata, "reviewer_id")
      if reviewer_id is not None and actor.id == reviewer_id:
        return
      raise AuthorizationError("当前账号不是该模板任务的指定验收人。")
```

### Verification

```bash
cd backend && python -m pytest tests/test_p1_10_template_review_safety.py -x -q
```

Expected: all existing tests pass (no regressions). New test added in Task 1-T below will also pass.

---

## Task 1-T — Test: ADMIN bypass in `_ensure_task_reviewer`

**File:** `backend/tests/test_p1_10_template_review_safety.py`  
**Estimated time:** 3 minutes

### Change

Append this test to the file:

```python
@pytest.mark.asyncio
async def test_admin_can_review_any_template_task(db_session) -> None:
    """An ADMIN-role actor must bypass the self-review guard even when actor == assignee_id."""
    admin = await _user(db_session, email="admin-reviewer@example.com", role=UserRole.ADMIN)
    task = await _template_review_task(
        db_session,
        assignee=admin,
        creator=admin,
        workflow_admin=admin,
        department=None,
    )
    # Manually set reviewer_id to a different user so the task is formally in REVIEW
    # but we are testing that ADMIN bypasses the self-review guard regardless.
    other = await _user(db_session, email="other@example.com")
    task.extra_metadata = {
        **task.extra_metadata,
        "reviewer_id": str(other.id),
        "reviewer_ids": [str(other.id)],
        "reviewer_source": "configured_reviewer",
    }
    await db_session.flush()

    service = TaskService(db_session)
    # Must not raise ConflictError or AuthorizationError
    reviewed = await service.review_task_deliverable(
        actor=admin,
        task_id=task.id,
        approve=True,
    )
    assert reviewed.status == TaskStatus.DONE
```

### Verification

```bash
cd backend && python -m pytest tests/test_p1_10_template_review_safety.py::test_admin_can_review_any_template_task -x -v
```

Expected output contains: `PASSED`

---

## Task 2 — Self-review fallback in `_activate_template_review`

**File:** `backend/app/services/task_service.py`  
**Lines affected:** ~15 lines inserted after line 2391 (after the `break` at end of candidate loop), before the existing `selected is None` BLOCKED branch  
**Estimated time:** 5 minutes

### Change

Current code (lines 2393–2413):

```python
    metadata = self._copy_task_metadata(task)
    metadata["latest_review_state"] = "pending_review"
    if selected is None:
      metadata.pop("reviewer_id", None)
      metadata["reviewer_ids"] = []
      metadata["review_blocked_reason"] = "no_eligible_reviewer"
      task.extra_metadata = metadata
      task.status = TaskStatus.BLOCKED
      task.blocked_reason = "no_eligible_reviewer"
      await self._create_task_log(
        task_id=task.id,
        operator_id=operator_id,
        action_type=TaskActionType.STATUS_CHANGED,
        from_status=TaskStatus.REVIEW,
        to_status=TaskStatus.BLOCKED,
        detail={
          "action": "review_activation_blocked",
          "reason": "no_eligible_reviewer",
        },
      )
      return None
```

Replace with:

```python
    metadata = self._copy_task_metadata(task)
    metadata["latest_review_state"] = "pending_review"
    if selected is None:
      # Check whether every exclusion was solely due to self-review (candidate == assignee_id).
      # If so, allow an audited self-review fallback instead of hard-blocking the task.
      all_candidates = await self._review_fallback_candidates(
        task=task,
        initial_reviewer_ids=initial_reviewer_ids,
      )
      all_excluded_as_self = bool(all_candidates) and all(
        cid == task.assignee_id for _, cid in all_candidates
      )
      if all_excluded_as_self:
        metadata["reviewer_id"] = str(task.assignee_id)
        metadata["reviewer_ids"] = [str(task.assignee_id)]
        metadata["reviewer_source"] = "self_review_fallback"
        metadata["self_review_fallback"] = True
        metadata.pop("review_blocked_reason", None)
        task.extra_metadata = metadata
        task.status = TaskStatus.REVIEW
        task.blocked_reason = None
        await self._create_task_log(
          task_id=task.id,
          operator_id=operator_id,
          action_type=TaskActionType.STATUS_CHANGED,
          from_status=TaskStatus.BLOCKED,
          to_status=TaskStatus.REVIEW,
          detail={
            "action": "self_review_fallback_activated",
            "reviewer_user_id": str(task.assignee_id),
            "reason": "all_candidates_excluded_as_self_review",
          },
        )
        return task.assignee_id
      metadata.pop("reviewer_id", None)
      metadata["reviewer_ids"] = []
      metadata["review_blocked_reason"] = "no_eligible_reviewer"
      task.extra_metadata = metadata
      task.status = TaskStatus.BLOCKED
      task.blocked_reason = "no_eligible_reviewer"
      await self._create_task_log(
        task_id=task.id,
        operator_id=operator_id,
        action_type=TaskActionType.STATUS_CHANGED,
        from_status=TaskStatus.REVIEW,
        to_status=TaskStatus.BLOCKED,
        detail={
          "action": "review_activation_blocked",
          "reason": "no_eligible_reviewer",
        },
      )
      return None
```

**Key invariant:** `all_excluded_as_self` is `False` if `all_candidates` is empty (zero candidates returned — no admins, no supervisor, no dept head, no configured reviewer). In that case the existing BLOCKED path fires as before. The fallback only triggers when every candidate in the list maps to `assignee_id`.

### Verification

```bash
cd backend && python -m pytest tests/test_p1_10_template_review_safety.py -x -q
```

Expected: all existing tests pass. New test added in Task 2-T below also passes.

---

## Task 2-T — Test: self-review fallback activates for sole-self-review scenario

**File:** `backend/tests/test_p1_10_template_review_safety.py`  
**Estimated time:** 4 minutes

### Change

Append this test to the file:

```python
@pytest.mark.asyncio
async def test_self_review_fallback_activated_when_only_candidate_is_assignee(db_session) -> None:
    """Scenario A: creator == assignee, no supervisor, no dept head, no other admins.
    _activate_template_review must set self_review_fallback=True and return assignee_id,
    allowing the assignee to later call review_task_deliverable without error.
    """
    # Single user: both creator and assignee; also the workflow admin (template.created_by).
    # No other users exist, so system_admins list is also empty after excluding self.
    sole_user = await _user(db_session, email="sole@example.com")
    task = await _template_review_task(
        db_session,
        assignee=sole_user,
        creator=sole_user,
        workflow_admin=sole_user,
        department=None,
    )
    # Reset status to DOING so activate can transition to REVIEW
    task.status = TaskStatus.DOING
    await db_session.flush()

    service = TaskService(db_session)
    reviewer_id = await service.activate_template_review_projection(
        actor=sole_user,
        task=task,
        initial_reviewer_ids=[sole_user.id],
    )

    assert reviewer_id == sole_user.id
    assert task.status == TaskStatus.REVIEW
    assert task.blocked_reason is None
    assert task.extra_metadata["reviewer_id"] == str(sole_user.id)
    assert task.extra_metadata["reviewer_source"] == "self_review_fallback"
    assert task.extra_metadata["self_review_fallback"] is True

    fallback_log = await db_session.scalar(
        select(TaskLog).where(
            TaskLog.task_id == task.id,
            TaskLog.detail["action"].as_string() == "self_review_fallback_activated",
        )
    )
    assert fallback_log is not None
    assert fallback_log.detail["reviewer_user_id"] == str(sole_user.id)

    # Assignee must now be able to review their own task
    reviewed = await service.review_task_deliverable(
        actor=sole_user,
        task_id=task.id,
        approve=True,
    )
    assert reviewed.status == TaskStatus.DONE


@pytest.mark.asyncio
async def test_self_review_fallback_does_not_fire_when_inactive_candidate_exists(db_session) -> None:
    """Spec criterion 5: if a candidate is excluded for *non-self-review* reasons
    (inactive account), the task must still BLOCK, not fall back to self-review.
    """
    assignee = await _user(db_session, email="assignee2@example.com")
    inactive_reviewer = await _user(db_session, email="inactive@example.com")
    inactive_reviewer.status = UserStatus.INACTIVE
    await db_session.flush()

    task = await _template_review_task(
        db_session,
        assignee=assignee,
        creator=assignee,
        workflow_admin=assignee,
        department=None,
    )
    task.status = TaskStatus.DOING
    await db_session.flush()

    service = TaskService(db_session)
    reviewer_id = await service.activate_template_review_projection(
        actor=assignee,
        task=task,
        # inactive_reviewer is in the configured list but excluded as inactive
        initial_reviewer_ids=[assignee.id, inactive_reviewer.id],
    )

    assert reviewer_id is None
    assert task.status == TaskStatus.BLOCKED
    assert task.blocked_reason == "no_eligible_reviewer"
```

### Verification

```bash
cd backend && python -m pytest tests/test_p1_10_template_review_safety.py::test_self_review_fallback_activated_when_only_candidate_is_assignee tests/test_p1_10_template_review_safety.py::test_self_review_fallback_does_not_fire_when_inactive_candidate_exists -x -v
```

Expected output: both tests `PASSED`.

---

## Task 3 — Honour `self_review_fallback` in `_ensure_task_reviewer`

**File:** `backend/app/services/task_service.py`  
**Lines affected:** ~3 lines inserted before the `actor.id == task.assignee_id` check (current line 2445), after the ADMIN bypass added in Task 1  
**Estimated time:** 2 minutes

### Change

After Task 1's ADMIN bypass, the `_is_template_graph_task` block reads:

```python
    if self._is_template_graph_task(task):
      if actor.role == UserRole.ADMIN:
        return
      if actor.id == task.assignee_id:
        raise ConflictError("Self-review is not permitted for template tasks")
      metadata = self._copy_task_metadata(task)
      reviewer_id = self._read_uuid_metadata(metadata, "reviewer_id")
      if reviewer_id is not None and actor.id == reviewer_id:
        return
      raise AuthorizationError("当前账号不是该模板任务的指定验收人。")
```

Replace with (adds 3 lines between ADMIN bypass and assignee guard):

```python
    if self._is_template_graph_task(task):
      if actor.role == UserRole.ADMIN:
        return
      metadata = self._copy_task_metadata(task)
      if metadata.get("self_review_fallback") is True and actor.id == task.assignee_id:
        return
      if actor.id == task.assignee_id:
        raise ConflictError("Self-review is not permitted for template tasks")
      reviewer_id = self._read_uuid_metadata(metadata, "reviewer_id")
      if reviewer_id is not None and actor.id == reviewer_id:
        return
      raise AuthorizationError("当前账号不是该模板任务的指定验收人。")
```

**Note:** `_copy_task_metadata` is now called once and reused for both the `self_review_fallback` check and the subsequent `reviewer_id` read. The `metadata` variable previously defined inside the block is moved up before the assignee guard; the later `metadata = self._copy_task_metadata(task)` call on the original line is removed (it becomes the same variable).

### Verification

```bash
cd backend && python -m pytest tests/test_p1_10_template_review_safety.py -x -v
```

Expected: all tests pass, including the `test_self_review_fallback_activated_when_only_candidate_is_assignee` test which calls `review_task_deliverable` as the assignee after fallback.

---

## Task 3-T — Test: `self_review_fallback` flag is honoured

**File:** `backend/tests/test_p1_10_template_review_safety.py`  
**Estimated time:** 3 minutes

### Change

Append this test to the file (verifies the guard in isolation via direct metadata injection, without going through `activate_template_review_projection`):

```python
@pytest.mark.asyncio
async def test_self_review_fallback_flag_allows_assignee_to_review(db_session) -> None:
    """Unit-level: if extra_metadata already contains self_review_fallback=True,
    _ensure_task_reviewer must allow actor == assignee without raising.
    """
    assignee = await _user(db_session, email="fallback-assignee@example.com")
    task = await _template_review_task(
        db_session,
        assignee=assignee,
        creator=assignee,
        workflow_admin=assignee,
        department=None,
    )
    task.extra_metadata = {
        **task.extra_metadata,
        "reviewer_id": str(assignee.id),
        "reviewer_ids": [str(assignee.id)],
        "reviewer_source": "self_review_fallback",
        "self_review_fallback": True,
    }
    task.status = TaskStatus.REVIEW
    await db_session.flush()

    service = TaskService(db_session)
    # Must not raise ConflictError
    reviewed = await service.review_task_deliverable(
        actor=assignee,
        task_id=task.id,
        approve=True,
    )
    assert reviewed.status == TaskStatus.DONE


@pytest.mark.asyncio
async def test_without_self_review_fallback_flag_assignee_still_blocked(db_session) -> None:
    """Regression: without the flag, actor == assignee must still raise ConflictError."""
    assignee = await _user(db_session, email="no-flag-assignee@example.com")
    supervisor = await _user(db_session, email="no-flag-sup@example.com")
    task = await _template_review_task(
        db_session,
        assignee=assignee,
        creator=assignee,
        workflow_admin=assignee,
        department=None,
    )
    task.extra_metadata = {
        **task.extra_metadata,
        "reviewer_id": str(supervisor.id),
        "reviewer_ids": [str(supervisor.id)],
        "reviewer_source": "supervisor",
        # self_review_fallback absent intentionally
    }
    task.status = TaskStatus.REVIEW
    await db_session.flush()

    service = TaskService(db_session)
    with pytest.raises(ConflictError, match="Self-review is not permitted for template tasks"):
        await service.review_task_deliverable(
            actor=assignee,
            task_id=task.id,
            approve=True,
        )
```

### Verification

```bash
cd backend && python -m pytest tests/test_p1_10_template_review_safety.py -x -v 2>&1 | tail -20
```

Expected: all tests `PASSED`, zero failures or errors.

---

## Full suite smoke test (run after all 6 tasks complete)

```bash
cd backend && python -m pytest tests/test_p1_10_template_review_safety.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR"
```

Expected lines (all PASSED):

```
tests/test_p1_10_template_review_safety.py::test_template_review_excludes_assignee_and_uses_supervisor PASSED
tests/test_p1_10_template_review_safety.py::test_no_eligible_reviewer_blocks_until_admin_reassignment PASSED
tests/test_p1_10_template_review_safety.py::test_admin_can_review_any_template_task PASSED
tests/test_p1_10_template_review_safety.py::test_self_review_fallback_activated_when_only_candidate_is_assignee PASSED
tests/test_p1_10_template_review_safety.py::test_self_review_fallback_does_not_fire_when_inactive_candidate_exists PASSED
tests/test_p1_10_template_review_safety.py::test_self_review_fallback_flag_allows_assignee_to_review PASSED
tests/test_p1_10_template_review_safety.py::test_without_self_review_fallback_flag_assignee_still_blocked PASSED
```

---

## Spec coverage matrix

| Acceptance criterion | Covered by |
|---|---|
| 1. Scenario A → REVIEW with `reviewer_source=self_review_fallback`; assignee can review | Task 2, Task 2-T (`test_self_review_fallback_activated_when_only_candidate_is_assignee`) |
| 2. Scenario B/C unchanged | Existing `test_template_review_excludes_assignee_and_uses_supervisor` (regression) |
| 3. ADMIN can always review any template task in REVIEW | Task 1, Task 1-T (`test_admin_can_review_any_template_task`) |
| 4. Audit log `action: "self_review_fallback_activated"` | Task 2 code + Task 2-T assertion on `TaskLog` |
| 5. Non-self-review exclusions still BLOCK | Task 2-T (`test_self_review_fallback_does_not_fire_when_inactive_candidate_exists`) |

---

## Self-review checklist

- [ ] No placeholders (TBD / TODO / "add error handling") — confirmed absent.
- [ ] Types consistent: `task.assignee_id` is `UUID` throughout; `metadata.get("self_review_fallback")` returns `bool | None`; comparison `is True` is safe for both `None` and `False`.
- [ ] `_copy_task_metadata` called once per guard block after Task 3 refactor — no double call.
- [ ] `all_excluded_as_self` is `False` for empty candidate list — guarded by `bool(all_candidates) and all(...)`.
- [ ] `initial_reviewer_ids` is passed correctly to the second `_review_fallback_candidates` call inside Task 2 (same variable in scope from method signature).
- [ ] All test functions are `async def` with `@pytest.mark.asyncio` and take `db_session` fixture — consistent with existing test file pattern.
- [ ] `AuthorizationError` import not needed in tests (tests only catch `ConflictError`) — consistent with existing imports.
- [ ] Task order preserves guard priority: ADMIN bypass → self_review_fallback → assignee block → reviewer_id check.
