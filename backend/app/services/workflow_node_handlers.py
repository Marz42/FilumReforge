from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping, Protocol

from app.core.enums import (
  WorkflowGraphNodeType,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)


class WorkflowCapabilityOutcome(StrEnum):
  WAITING = "waiting"
  SUCCEEDED = "succeeded"
  FAILED = "failed"
  CANCELLED = "cancelled"


class WorkflowCapabilityCommand(StrEnum):
  COMPLETE = "complete"


class WorkflowNodeHandlerRegistrationError(RuntimeError):
  pass


class WorkflowNodeHandlerNotFoundError(LookupError):
  pass


class WorkflowCapabilityOperationError(RuntimeError):
  pass


@dataclass(frozen=True, slots=True)
class WorkflowCapabilityContext:
  node_type: WorkflowGraphNodeType
  node_key: str
  engine_state: WorkflowNodeEngineState
  business_state: WorkflowNodeBusinessState
  config: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorkflowCapabilityResult:
  capability_key: str
  outcome: WorkflowCapabilityOutcome
  engine_state: WorkflowNodeEngineState
  business_state: WorkflowNodeBusinessState
  result: Mapping[str, object] = field(default_factory=dict)
  diagnostics: Mapping[str, object] = field(default_factory=dict)
  side_effects: tuple[str, ...] = ()


class WorkflowNodeHandler(Protocol):
  capability_key: str
  node_type: WorkflowGraphNodeType
  interruptible: bool
  compensation: str
  declared_side_effects: tuple[str, ...]

  def validate_definition(self, config: Mapping[str, object]) -> tuple[str, ...]: ...

  def activate(self, context: WorkflowCapabilityContext) -> WorkflowCapabilityResult: ...

  def command(
    self,
    context: WorkflowCapabilityContext,
    *,
    command: WorkflowCapabilityCommand,
    payload: Mapping[str, object] | None = None,
  ) -> WorkflowCapabilityResult: ...

  def cancel(self, context: WorkflowCapabilityContext) -> WorkflowCapabilityResult: ...

  def retry(self, context: WorkflowCapabilityContext) -> WorkflowCapabilityResult: ...

  def map_result(self, result: WorkflowCapabilityResult) -> Mapping[str, object]: ...


class _BaseWorkflowNodeHandler:
  capability_key: str
  node_type: WorkflowGraphNodeType
  interruptible: bool
  compensation: str
  declared_side_effects: tuple[str, ...]

  def validate_definition(self, config: Mapping[str, object]) -> tuple[str, ...]:
    del config
    return ()

  def _result(
    self,
    *,
    outcome: WorkflowCapabilityOutcome,
    engine_state: WorkflowNodeEngineState,
    business_state: WorkflowNodeBusinessState,
    result: Mapping[str, object] | None = None,
    diagnostics: Mapping[str, object] | None = None,
    side_effects: tuple[str, ...] | None = None,
  ) -> WorkflowCapabilityResult:
    return WorkflowCapabilityResult(
      capability_key=self.capability_key,
      outcome=outcome,
      engine_state=engine_state,
      business_state=business_state,
      result=MappingProxyType(dict(result or {})),
      diagnostics=MappingProxyType(dict(diagnostics or {})),
      side_effects=self.declared_side_effects if side_effects is None else side_effects,
    )

  def map_result(self, result: WorkflowCapabilityResult) -> Mapping[str, object]:
    return MappingProxyType(
      {
        "capability_key": result.capability_key,
        "outcome": result.outcome.value,
        "result": dict(result.result),
        "diagnostics": dict(result.diagnostics),
        "side_effects": list(result.side_effects),
      }
    )


class HumanTaskNodeHandler(_BaseWorkflowNodeHandler):
  capability_key = "human_task"
  node_type = WorkflowGraphNodeType.TASK
  interruptible = True
  compensation = "terminate_work_item"
  declared_side_effects = ("ensure_work_item",)

  def activate(self, context: WorkflowCapabilityContext) -> WorkflowCapabilityResult:
    del context
    return self._result(
      outcome=WorkflowCapabilityOutcome.WAITING,
      engine_state=WorkflowNodeEngineState.ACTIVATED,
      business_state=WorkflowNodeBusinessState.ASSIGNED,
    )

  def command(
    self,
    context: WorkflowCapabilityContext,
    *,
    command: WorkflowCapabilityCommand,
    payload: Mapping[str, object] | None = None,
  ) -> WorkflowCapabilityResult:
    del context
    if command != WorkflowCapabilityCommand.COMPLETE:
      raise WorkflowCapabilityOperationError(
        f"HumanTask Handler 不支持命令：{command.value}。"
      )
    return self._result(
      outcome=WorkflowCapabilityOutcome.SUCCEEDED,
      engine_state=WorkflowNodeEngineState.COMPLETED,
      business_state=WorkflowNodeBusinessState.DONE,
      result=payload,
      side_effects=(),
    )

  def cancel(self, context: WorkflowCapabilityContext) -> WorkflowCapabilityResult:
    del context
    return self._result(
      outcome=WorkflowCapabilityOutcome.CANCELLED,
      engine_state=WorkflowNodeEngineState.TERMINATED,
      business_state=WorkflowNodeBusinessState.CANCELLED,
      side_effects=("terminate_work_item",),
    )

  def retry(self, context: WorkflowCapabilityContext) -> WorkflowCapabilityResult:
    if context.engine_state not in {
      WorkflowNodeEngineState.FAILED,
      WorkflowNodeEngineState.SUSPENDED,
    }:
      raise WorkflowCapabilityOperationError("HumanTask 只有 FAILED/SUSPENDED 状态可以重试。")
    return self.activate(context)


class NoticeNodeHandler(_BaseWorkflowNodeHandler):
  capability_key = "notice"
  node_type = WorkflowGraphNodeType.NOTICE
  interruptible = False
  compensation = "none"
  declared_side_effects: tuple[str, ...] = ()

  def activate(self, context: WorkflowCapabilityContext) -> WorkflowCapabilityResult:
    del context
    return self._result(
      outcome=WorkflowCapabilityOutcome.WAITING,
      engine_state=WorkflowNodeEngineState.ACTIVATED,
      business_state=WorkflowNodeBusinessState.ASSIGNED,
    )

  def command(
    self,
    context: WorkflowCapabilityContext,
    *,
    command: WorkflowCapabilityCommand,
    payload: Mapping[str, object] | None = None,
  ) -> WorkflowCapabilityResult:
    del context
    if command != WorkflowCapabilityCommand.COMPLETE:
      raise WorkflowCapabilityOperationError(f"Notice Handler 不支持命令：{command.value}。")
    return self._result(
      outcome=WorkflowCapabilityOutcome.SUCCEEDED,
      engine_state=WorkflowNodeEngineState.COMPLETED,
      business_state=WorkflowNodeBusinessState.DONE,
      result=payload,
      side_effects=(),
    )

  def cancel(self, context: WorkflowCapabilityContext) -> WorkflowCapabilityResult:
    del context
    raise WorkflowCapabilityOperationError("Notice 为自动能力，不支持人工取消。")

  def retry(self, context: WorkflowCapabilityContext) -> WorkflowCapabilityResult:
    if context.engine_state not in {
      WorkflowNodeEngineState.FAILED,
      WorkflowNodeEngineState.SUSPENDED,
    }:
      raise WorkflowCapabilityOperationError("Notice 只有 FAILED/SUSPENDED 状态可以重试。")
    return self.activate(context)


class WorkflowNodeHandlerRegistry:
  def __init__(self) -> None:
    self._handlers: dict[WorkflowGraphNodeType, WorkflowNodeHandler] = {}

  def register(self, handler: WorkflowNodeHandler) -> None:
    if handler.node_type in self._handlers:
      raise WorkflowNodeHandlerRegistrationError(
        f"节点类型 {handler.node_type.value} 已注册 Handler。"
      )
    self._handlers[handler.node_type] = handler

  def resolve(self, node_type: WorkflowGraphNodeType) -> WorkflowNodeHandler | None:
    return self._handlers.get(node_type)

  def require(self, node_type: WorkflowGraphNodeType) -> WorkflowNodeHandler:
    handler = self.resolve(node_type)
    if handler is None:
      raise WorkflowNodeHandlerNotFoundError(
        f"节点类型 {node_type.value} 尚未注册 Handler。"
      )
    return handler


def build_default_workflow_node_handler_registry() -> WorkflowNodeHandlerRegistry:
  registry = WorkflowNodeHandlerRegistry()
  registry.register(HumanTaskNodeHandler())
  registry.register(NoticeNodeHandler())
  return registry
