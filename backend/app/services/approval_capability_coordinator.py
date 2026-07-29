from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import WorkflowGraphNodeType
from app.core.exceptions import ConflictError, NotFoundError
from app.models import User, WorkflowGraphInstance, WorkflowInstance, WorkflowNodeInstance
from app.services.workflow_engine_service import WorkflowEngineService
from app.services.workflow_runtime_write_service import WorkflowRuntimeWriteService


APPROVAL_GRAPH_SOURCE_TYPE = "workflow_graph_node"


@dataclass(frozen=True, slots=True)
class ApprovalCapabilityBinding:
  instance: WorkflowInstance
  created: bool
  correlation_key: str


class ApprovalCapabilityCoordinator:
  """Bridge a graph Approval node to the existing approval engine."""

  def __init__(self, session: AsyncSession) -> None:
    self._session = session
    self._runtime = WorkflowRuntimeWriteService(session)

  @staticmethod
  def is_managed_node(node_instance: WorkflowNodeInstance) -> bool:
    config = dict(node_instance.config or {})
    return (
      node_instance.node_type == WorkflowGraphNodeType.APPROVAL
      and bool(str(config.get("decision_semantic") or "").strip())
    )

  @staticmethod
  def _definition_id(node_instance: WorkflowNodeInstance) -> UUID:
    raw_definition_id = (node_instance.config or {}).get("workflow_definition_id")
    if raw_definition_id is None:
      raise ConflictError("Approval 节点缺少 workflow_definition_id。")
    try:
      return UUID(str(raw_definition_id))
    except ValueError as exc:
      raise ConflictError("Approval 节点的 workflow_definition_id 无效。") from exc

  async def ensure_instance(
    self,
    *,
    graph_instance: WorkflowGraphInstance,
    node_instance: WorkflowNodeInstance,
  ) -> ApprovalCapabilityBinding | None:
    if not self.is_managed_node(node_instance):
      return None

    definition_id = self._definition_id(node_instance)
    correlation_key = f"{APPROVAL_GRAPH_SOURCE_TYPE}:{node_instance.id}"
    existing_instances = list(
      await self._session.scalars(
        select(WorkflowInstance)
        .where(
          WorkflowInstance.source_type == APPROVAL_GRAPH_SOURCE_TYPE,
          WorkflowInstance.source_id == node_instance.id,
        )
        .order_by(WorkflowInstance.started_at.asc())
        .limit(2)
      )
    )
    if len(existing_instances) > 1:
      raise ConflictError("Approval 节点关联了多个审批实例，已停止自动修复。")
    if existing_instances:
      approval_instance = existing_instances[0]
      if approval_instance.definition_id != definition_id:
        raise ConflictError("Approval 节点关联的审批定义与当前配置不一致。")
      self._patch_binding(
        node_instance=node_instance,
        approval_instance=approval_instance,
        correlation_key=correlation_key,
      )
      return ApprovalCapabilityBinding(
        instance=approval_instance,
        created=False,
        correlation_key=correlation_key,
      )

    initiator = await self._session.get(User, graph_instance.initiator_user_id)
    if initiator is None:
      raise NotFoundError("Approval 节点对应的图运行发起人不存在。")
    config = dict(node_instance.config or {})
    decision_subject = config.get("decision_subject")
    approval_instance = await WorkflowEngineService(self._session).start_workflow(
      actor=initiator,
      definition_id=definition_id,
      source_type=APPROVAL_GRAPH_SOURCE_TYPE,
      source_id=node_instance.id,
      payload={
        "workflow_graph_instance_id": str(graph_instance.id),
        "workflow_node_instance_id": str(node_instance.id),
        "approval_correlation_key": correlation_key,
        "decision_semantic": str(config.get("decision_semantic")),
        "decision_subject": (
          dict(decision_subject) if isinstance(decision_subject, dict) else {}
        ),
      },
      commit=False,
    )
    self._patch_binding(
      node_instance=node_instance,
      approval_instance=approval_instance,
      correlation_key=correlation_key,
    )
    await self._session.flush()
    return ApprovalCapabilityBinding(
      instance=approval_instance,
      created=True,
      correlation_key=correlation_key,
    )

  def _patch_binding(
    self,
    *,
    node_instance: WorkflowNodeInstance,
    approval_instance: WorkflowInstance,
    correlation_key: str,
  ) -> None:
    self._runtime.patch_node_config(
      node_instance,
      {
        "approval_instance_id": str(approval_instance.id),
        "approval_correlation_key": correlation_key,
      },
    )
