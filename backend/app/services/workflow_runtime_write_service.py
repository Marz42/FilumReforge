from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WorkflowGraphInstance, WorkflowNodeInstance


class WorkflowRuntimeWriteService:
  """Single production write port for graph Runtime state."""

  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  def create_instance(self, **values: Any) -> WorkflowGraphInstance:
    instance = WorkflowGraphInstance(**values)
    self._session.add(instance)
    return instance

  def create_node(self, **values: Any) -> WorkflowNodeInstance:
    node = WorkflowNodeInstance(**values)
    self._session.add(node)
    return node

  @staticmethod
  def update_instance(
    instance: WorkflowGraphInstance,
    **changes: Any,
  ) -> WorkflowGraphInstance:
    for field_name, value in changes.items():
      if not hasattr(WorkflowGraphInstance, field_name):
        raise AttributeError(f"WorkflowGraphInstance 不存在可写字段：{field_name}")
      setattr(instance, field_name, value)
    return instance

  @staticmethod
  def update_node(node: WorkflowNodeInstance, **changes: Any) -> WorkflowNodeInstance:
    for field_name, value in changes.items():
      if not hasattr(WorkflowNodeInstance, field_name):
        raise AttributeError(f"WorkflowNodeInstance 不存在可写字段：{field_name}")
      setattr(node, field_name, value)
    return node

  @staticmethod
  def patch_node_config(node: WorkflowNodeInstance, patch: dict[str, Any]) -> WorkflowNodeInstance:
    node.config = {**dict(node.config or {}), **patch}
    return node
