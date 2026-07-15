from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from collections.abc import Iterator
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class WorkflowEventContext:
  command_id: str | None = None
  causation_id: UUID | None = None
  correlation_id: UUID | None = None


_current_context: ContextVar[WorkflowEventContext] = ContextVar(
  "workflow_event_context",
  default=WorkflowEventContext(),
)


def current_workflow_event_context() -> WorkflowEventContext:
  return _current_context.get()


@contextmanager
def bind_workflow_event_context(
  *,
  command_id: str | None,
  causation_id: UUID | None = None,
  correlation_id: UUID | None = None,
) -> Iterator[WorkflowEventContext]:
  context = WorkflowEventContext(
    command_id=command_id,
    causation_id=causation_id,
    correlation_id=correlation_id or uuid4(),
  )
  token = _current_context.set(context)
  try:
    yield context
  finally:
    _current_context.reset(token)
