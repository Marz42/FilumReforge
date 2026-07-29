from __future__ import annotations

import inspect
from uuid import uuid4

from app.core.enums import (
  TaskPriority,
  TaskSourceType,
  TaskStatus,
  WorkflowGraphTemplateStatus,
)
from app.models import Task, WorkflowGraphTemplate, WorkflowGraphTemplateNode
from app.services.task_user_facing_state import resolve_task_user_facing_state
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.workflow_graph_template_capabilities import compute_template_capabilities
from app.services.workflow_template_capability_contract import (
  CHILD_RUN_DISPATCH,
  COLLECTION_FINALIZE,
  build_template_capability_snapshot,
  instance_supports_capability,
  read_task_capability,
  resolve_instance_runtime_policy,
  resolve_node_task_capability,
  resolve_task_root_visibility,
)


def test_i4e_non_video_template_uses_the_same_declared_capabilities() -> None:
  template = WorkflowGraphTemplate(
    id=uuid4(),
    code="contract_intake_v1",
    base_code="contract_intake",
    version=1,
    name="合同材料收集",
    status=WorkflowGraphTemplateStatus.ACTIVE,
    config={
      "launch_schema": {"fields": [{"key": "contract_name", "label": "合同名称"}]},
      "workflow_capabilities": [
        "structured_form_submission",
        COLLECTION_FINALIZE,
        CHILD_RUN_DISPATCH,
      ],
      "runtime_policy": {
        "notify_on_node_activation": True,
        "archive_on_completion": True,
      },
      "instantiation_mode": "direct",
    },
    created_by=uuid4(),
  )
  node = WorkflowGraphTemplateNode(
    id=uuid4(),
    template_id=template.id,
    node_key="COLLECT_CONTRACT_DATA",
    title="提交合同材料",
    sort_order=1,
    config={
      "kind": "single",
      "task_capability": {
        "surface": "structured_form",
        "submit_mode": "form",
        "state_policy": "submission",
      },
    },
  )

  template_caps = compute_template_capabilities(
    template=template,
    nodes=[node],
    edges=[],
    fork_target_codes=set(),
  )
  snapshot = build_template_capability_snapshot(template.config)

  assert template_caps.can_instantiate_directly is True
  assert snapshot["source"] == "explicit"
  assert instance_supports_capability({"capability_snapshot": snapshot}, COLLECTION_FINALIZE)
  assert instance_supports_capability({"capability_snapshot": snapshot}, CHILD_RUN_DISPATCH)
  assert resolve_instance_runtime_policy({"capability_snapshot": snapshot}).archive_on_completion
  assert resolve_node_task_capability(node.config)["surface"] == "structured_form"
  assert resolve_task_root_visibility({
    "workflow_graph_root_task": True,
    "task_capability": {
      "surface": "run_overview",
      "state_policy": "run_active",
      "root_visibility": "overview",
    },
  }) == "overview"


def test_i4e_task_projection_uses_capability_not_node_or_template_names() -> None:
  metadata = {
    "workflow_graph_instance_id": str(uuid4()),
    "workflow_node_instance_id": str(uuid4()),
    "template_node_key": "ARBITRARY_BUSINESS_KEY",
    "task_capability": {
      "surface": "deliverable",
      "submit_mode": "file",
      "state_policy": "deliverable",
      "root_visibility": "normal",
    },
  }
  task = Task(
    id=uuid4(),
    title="提交合同扫描件",
    creator_id=uuid4(),
    assignee_id=uuid4(),
    status=TaskStatus.REVIEW,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.TEMPLATE,
    extra_metadata=metadata,
  )

  assert read_task_capability(metadata)["surface"] == "deliverable"
  assert resolve_task_user_facing_state(task=task, status=task.status) == "awaiting_confirm"


def test_i4e_legacy_values_are_confined_to_compatibility_adapter() -> None:
  batch_snapshot = build_template_capability_snapshot({"run_kind": "batch"})
  production_snapshot = build_template_capability_snapshot({"run_kind": "production"})

  assert batch_snapshot["source"] == "legacy_run_kind"
  assert COLLECTION_FINALIZE in batch_snapshot["capabilities"]
  assert production_snapshot["runtime"]["archive_on_completion"] is True
  assert resolve_task_root_visibility({
    "workflow_graph_root_task": True,
    "run_kind": "production",
  }) == "hidden_for_non_management"

  runtime_source = inspect.getsource(WorkflowGraphService)
  assert 'context.get("run_kind")' not in runtime_source
  assert '== "production"' not in runtime_source
