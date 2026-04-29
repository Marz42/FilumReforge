from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
  TaskPriority,
  WorkflowGraphInstanceStatus,
  WorkflowGraphNodeType,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.models import WorkflowGraphInstance, WorkflowNodeInstance


@dataclass(slots=True)
class SingleNodeWorkflowSeed:
  title: str
  creator_id: UUID
  assignee_id: UUID
  department_id: UUID | None
  description: str | None
  due_date: datetime | None
  priority: TaskPriority


class WorkflowGraphService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def create_single_node_instance(self, *, seed: SingleNodeWorkflowSeed) -> tuple[WorkflowGraphInstance, WorkflowNodeInstance]:
    now = datetime.now(UTC)
    instance = WorkflowGraphInstance(
      initiator_user_id=seed.creator_id,
      department_id=seed.department_id,
      source_type="task",
      status=WorkflowGraphInstanceStatus.ACTIVE,
      current_node_key="task-node",
      context={
        "title": seed.title,
        "description": seed.description,
        "priority": seed.priority.value,
        "due_date": seed.due_date.isoformat() if seed.due_date is not None else None,
      },
      context_version=1,
      max_iterations=5,
    )
    self._session.add(instance)
    await self._session.flush()

    node_instance = WorkflowNodeInstance(
      instance_id=instance.id,
      node_key="task-node",
      title=seed.title,
      node_type=WorkflowGraphNodeType.TASK,
      engine_state=WorkflowNodeEngineState.ACTIVATED,
      business_state=WorkflowNodeBusinessState.ASSIGNED,
      assignee_user_id=seed.assignee_id,
      iteration=1,
      node_instance_version=1,
      config={
        "description": seed.description,
        "priority": seed.priority.value,
        "due_date": seed.due_date.isoformat() if seed.due_date is not None else None,
      },
      activated_at=now,
    )
    self._session.add(node_instance)
    await self._session.flush()
    return instance, node_instance