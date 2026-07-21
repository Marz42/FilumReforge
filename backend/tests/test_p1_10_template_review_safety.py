from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.core.enums import (
  ReportingLineType,
  TaskPriority,
  TaskSourceType,
  TaskStatus,
  UserRole,
  UserStatus,
  WorkflowGraphInstanceStatus,
  WorkflowGraphTemplateStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.core.exceptions import ConflictError
from app.models import (
  Department,
  Profile,
  ReportingLine,
  Task,
  TaskLog,
  User,
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateNode,
  WorkflowNodeInstance,
)
from app.services.task_service import TaskService


async def _user(db_session, *, email: str, role: UserRole = UserRole.EMPLOYEE) -> User:
  user = User(
    email=email,
    password_hash="hashed",
    role=role,
    status=UserStatus.ACTIVE,
  )
  db_session.add(user)
  await db_session.flush()
  return user


async def _template_review_task(
  db_session,
  *,
  assignee: User,
  creator: User,
  workflow_admin: User,
  department: Department | None,
) -> Task:
  template = WorkflowGraphTemplate(
    code=f"p1-10-{assignee.id}",
    base_code=f"p1-10-{assignee.id}",
    version=1,
    name="P1-10",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    created_by=workflow_admin.id,
  )
  db_session.add(template)
  await db_session.flush()
  template_node = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="REVIEW",
    title="Review",
    config={"completion_policy": "on_review_approved"},
  )
  db_session.add(template_node)
  await db_session.flush()
  instance = WorkflowGraphInstance(
    template_id=template.id,
    initiator_user_id=creator.id,
    department_id=department.id if department else None,
    status=WorkflowGraphInstanceStatus.ACTIVE,
    current_node_key="REVIEW",
  )
  db_session.add(instance)
  await db_session.flush()
  node = WorkflowNodeInstance(
    instance_id=instance.id,
    template_node_id=template_node.id,
    node_key="REVIEW",
    title="Review",
    assignee_user_id=assignee.id,
    engine_state=WorkflowNodeEngineState.ACKNOWLEDGED,
    business_state=WorkflowNodeBusinessState.PENDING_REVIEW,
  )
  db_session.add(node)
  await db_session.flush()
  task = Task(
    title="Template review",
    creator_id=creator.id,
    assignee_id=assignee.id,
    department_id=department.id if department else None,
    status=TaskStatus.REVIEW,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.TEMPLATE,
    extra_metadata={
      "workflow_graph_instance_id": str(instance.id),
      "workflow_node_instance_id": str(node.id),
    },
  )
  db_session.add(task)
  await db_session.flush()
  return task


@pytest.mark.asyncio
async def test_template_review_excludes_assignee_and_uses_supervisor(db_session) -> None:
  admin = await _user(db_session, email="admin@example.com", role=UserRole.ADMIN)
  assignee = await _user(db_session, email="assignee@example.com")
  supervisor = await _user(db_session, email="supervisor@example.com")
  department = Department(name="Content", code="content", manager_id=admin.id)
  db_session.add(department)
  await db_session.flush()
  db_session.add(
    Profile(
      user_id=assignee.id,
      employee_no="P1-10-A",
      real_name="Assignee",
      department_id=department.id,
      custom_fields={},
    )
  )
  db_session.add(
    ReportingLine(
      user_id=assignee.id,
      manager_user_id=supervisor.id,
      department_id=department.id,
      line_type=ReportingLineType.SOLID,
      is_primary=True,
      starts_at=date.today(),
    )
  )
  task = await _template_review_task(
    db_session,
    assignee=assignee,
    creator=assignee,
    workflow_admin=admin,
    department=department,
  )
  service = TaskService(db_session)

  reviewer_id = await service.activate_template_review_projection(
    actor=assignee,
    task=task,
    initial_reviewer_ids=[assignee.id],
  )

  assert reviewer_id == supervisor.id
  assert task.status == TaskStatus.REVIEW
  assert task.blocked_reason is None
  assert task.extra_metadata["reviewer_id"] == str(supervisor.id)
  exclusion = await db_session.scalar(
    select(TaskLog).where(
      TaskLog.task_id == task.id,
      TaskLog.detail["action"].as_string() == "reviewer_candidate_excluded",
    )
  )
  assert exclusion is not None
  assert exclusion.detail["reason"] == "excluded: self-review not permitted"

  assignee_context = await service.resolve_task_action_context(actor=assignee, task=task)
  reviewer_context = await service.resolve_task_action_context(actor=supervisor, task=task)
  assert assignee_context.available_actions == []
  assert {item.action for item in reviewer_context.available_actions} == {
    "approve_deliverable",
    "return_for_rework",
  }
  with pytest.raises(ConflictError, match="Self-review is not permitted for template tasks"):
    await service.review_task_deliverable(
      actor=assignee,
      task_id=task.id,
      approve=True,
    )
  reviewed = await service.review_task_deliverable(
    actor=supervisor,
    task_id=task.id,
    approve=True,
  )
  assert reviewed.status == TaskStatus.DONE


@pytest.mark.asyncio
async def test_no_eligible_reviewer_blocks_until_admin_reassignment(db_session) -> None:
  admin_assignee = await _user(db_session, email="only-admin@example.com", role=UserRole.ADMIN)
  task = await _template_review_task(
    db_session,
    assignee=admin_assignee,
    creator=admin_assignee,
    workflow_admin=admin_assignee,
    department=None,
  )
  service = TaskService(db_session)

  reviewer_id = await service.activate_template_review_projection(
    actor=admin_assignee,
    task=task,
    initial_reviewer_ids=[admin_assignee.id],
  )

  assert reviewer_id is not None
  assert reviewer_id == admin_assignee.id
  assert task.status == TaskStatus.REVIEW
  assert task.blocked_reason is None
  assert task.extra_metadata["self_review_fallback"] is True


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
