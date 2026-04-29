from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_current_user, get_workflow_graph_service
from app.core.enums import WorkflowNodeEngineState
from app.models import User, WorkflowGraphInstance, WorkflowNodeInstance
from app.schemas.workflow_graph import (
  WorkflowGraphInstanceDetailRead,
  WorkflowGraphInstanceRead,
  WorkflowNodeCompleteRequest,
  WorkflowNodeInstanceRead,
)
from app.services.workflow_graph_service import WorkflowGraphService

router = APIRouter(prefix="/workflow-graph")


def _build_node_instance_read(ni: WorkflowNodeInstance) -> WorkflowNodeInstanceRead:
  return WorkflowNodeInstanceRead.model_validate(ni)


def _build_instance_detail(
  instance: WorkflowGraphInstance,
  node_instances: list[WorkflowNodeInstance],
) -> WorkflowGraphInstanceDetailRead:
  total = len(node_instances)
  completed = sum(1 for ni in node_instances if ni.engine_state == WorkflowNodeEngineState.COMPLETED)
  active = sum(1 for ni in node_instances if ni.engine_state == WorkflowNodeEngineState.ACTIVATED)
  pending = sum(1 for ni in node_instances if ni.engine_state == WorkflowNodeEngineState.PENDING)
  progress = int((completed / total) * 100) if total else 0

  return WorkflowGraphInstanceDetailRead.model_validate(instance).model_copy(
    update={
      "node_instances": [_build_node_instance_read(ni) for ni in node_instances],
      "total_node_count": total,
      "completed_node_count": completed,
      "active_node_count": active,
      "pending_node_count": pending,
      "progress_percent": progress,
    }
  )


@router.get(
  "/templates/{template_id}/instances",
  response_model=list[WorkflowGraphInstanceRead],
  tags=["workflow-graph"],
)
async def list_graph_instances_for_template(
  template_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
  limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[WorkflowGraphInstanceRead]:
  instances = await workflow_graph_service.list_instances_for_template(
    template_id=template_id,
    limit=limit,
  )
  results: list[WorkflowGraphInstanceRead] = []
  for instance in instances:
    node_instances = await workflow_graph_service.list_node_instances_for_graph(
      instance_id=instance.id,
    )
    results.append(
      WorkflowGraphInstanceRead.model_validate(instance).model_copy(
        update={"node_instances": [_build_node_instance_read(ni) for ni in node_instances]}
      )
    )
  return results


@router.get(
  "/instances/{instance_id}",
  response_model=WorkflowGraphInstanceDetailRead,
  tags=["workflow-graph"],
)
async def get_graph_instance(
  instance_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
) -> WorkflowGraphInstanceDetailRead:
  instance = await workflow_graph_service.get_instance(instance_id=instance_id)
  node_instances = await workflow_graph_service.list_node_instances_for_graph(instance_id=instance_id)
  return _build_instance_detail(instance, node_instances)


@router.post(
  "/node-instances/{node_instance_id}/complete",
  response_model=WorkflowGraphInstanceDetailRead,
  tags=["workflow-graph"],
)
async def complete_node_instance(
  node_instance_id: UUID,
  payload: WorkflowNodeCompleteRequest,
  actor: Annotated[User, Depends(get_current_user)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
) -> WorkflowGraphInstanceDetailRead:
  await workflow_graph_service.complete_node_instance(
    node_instance_id=node_instance_id,
    actor_id=actor.id,
  )
  # 重新查询实例以返回最新快照
  node_instance: WorkflowNodeInstance | None = await workflow_graph_service._session.get(
    WorkflowNodeInstance, node_instance_id
  )
  if node_instance is None:
    from app.core.exceptions import NotFoundError
    raise NotFoundError("节点实例不存在。")
  instance = await workflow_graph_service.get_instance(instance_id=node_instance.instance_id)
  node_instances = await workflow_graph_service.list_node_instances_for_graph(
    instance_id=node_instance.instance_id
  )
  return _build_instance_detail(instance, node_instances)
