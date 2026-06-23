"""Resolve department_id for graph template projection tasks."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile, WorkflowGraphInstance


async def resolve_projection_department_id(
  session: AsyncSession,
  *,
  instance: WorkflowGraphInstance,
  assignee_id: UUID,
) -> UUID | None:
  """Prefer instance department for same-dept assignees; cross-dept nodes use assignee dept."""
  instance_dept = instance.department_id
  assignee_dept = await session.scalar(
    select(Profile.department_id).where(Profile.user_id == assignee_id)
  )
  if instance_dept is None:
    return assignee_dept
  if assignee_dept is not None and assignee_dept != instance_dept:
    return assignee_dept
  return instance_dept
