from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from app.models import WorkflowInstance


def _stringify_route_query(route_query: Mapping[str, object] | None) -> dict[str, str]:
  if route_query is None:
    return {}
  return {
    str(key): str(value)
    for key, value in route_query.items()
    if value is not None
  }


def build_notification_source_payload(
  *,
  source_module: str,
  source_module_label: str,
  source_object_type: str,
  source_object_id: UUID | str | None,
  source_object_label: str | None,
  route_name: str | None,
  route_query: Mapping[str, object] | None = None,
  extra_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
  payload = dict(extra_payload or {})
  payload["source_module"] = source_module
  payload["source_module_label"] = source_module_label
  payload["source_object_type"] = source_object_type
  if source_object_id is not None:
    payload["source_object_id"] = str(source_object_id)
  if source_object_label:
    payload["source_object_label"] = source_object_label
  if route_name:
    payload["source_route_name"] = route_name
    payload["source_route_query"] = _stringify_route_query(route_query)
  return payload


def build_task_source_payload(
  *,
  task_id: UUID,
  task_title: str,
  extra_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
  return build_notification_source_payload(
    source_module="task",
    source_module_label="任务中心",
    source_object_type="task",
    source_object_id=task_id,
    source_object_label=task_title,
    route_name="task-center",
    route_query={
      "tab": "tracking",
      "selected": task_id,
    },
    extra_payload=extra_payload,
  )


def build_report_source_payload(
  *,
  report_id: UUID,
  report_title: str,
  route_tab: str | None = None,
  extra_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
  route_query: dict[str, object] = {"selected": report_id}
  if route_tab:
    route_query["tab"] = route_tab
  return build_notification_source_payload(
    source_module="report",
    source_module_label="汇报中心",
    source_object_type="report",
    source_object_id=report_id,
    source_object_label=report_title,
    route_name="reports",
    route_query=route_query,
    extra_payload=extra_payload,
  )


def build_announcement_source_payload(
  *,
  announcement_id: UUID,
  announcement_title: str,
  extra_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
  return build_notification_source_payload(
    source_module="announcement",
    source_module_label="总览",
    source_object_type="announcement",
    source_object_id=announcement_id,
    source_object_label=announcement_title,
    route_name="overview",
    route_query={"announcement": announcement_id},
    extra_payload=extra_payload,
  )


def build_workflow_source_payload(
  *,
  instance: WorkflowInstance,
  object_label: str,
  route_tab: str | None = None,
  extra_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
  if instance.source_type == "report" and instance.source_id is not None:
    route_query: dict[str, object] = {"selected": instance.source_id}
    if route_tab:
      route_query["tab"] = route_tab
    payload = build_notification_source_payload(
      source_module="report",
      source_module_label="汇报中心",
      source_object_type="workflow",
      source_object_id=instance.id,
      source_object_label=object_label,
      route_name="reports",
      route_query=route_query,
      extra_payload=extra_payload,
    )
  elif instance.source_type == "task" and instance.source_id is not None:
    payload = build_notification_source_payload(
      source_module="task",
      source_module_label="任务中心",
      source_object_type="workflow",
      source_object_id=instance.id,
      source_object_label=object_label,
      route_name="task-center",
      route_query={
        "tab": "tracking",
        "selected": instance.source_id,
      },
      extra_payload=extra_payload,
    )
  else:
    payload = build_notification_source_payload(
      source_module="workflow",
      source_module_label="流程引擎",
      source_object_type="workflow",
      source_object_id=instance.id,
      source_object_label=object_label,
      route_name=None,
      extra_payload=extra_payload,
    )

  payload["workflow_instance_id"] = str(instance.id)
  payload["workflow_source_type"] = instance.source_type
  if instance.source_id is not None:
    payload["workflow_source_id"] = str(instance.source_id)
  return payload
