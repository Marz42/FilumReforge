from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import DocumentCategory, NotificationReceiptType, TaskStatus
from app.core.exceptions import NotFoundError
from app.services.document_service import DocumentService
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.message_center_service import MessageCenterService
from app.services.profile_service import ProfileService
from app.services.task_service import TaskService
from app.services.workflow_engine_service import WorkflowEngineService


def _serialize_value(value):  # noqa: ANN001
  if isinstance(value, datetime):
    return value.isoformat()
  if isinstance(value, UUID):
    return str(value)
  if isinstance(value, Enum):
    return value.value
  if isinstance(value, dict):
    return {key: _serialize_value(nested_value) for key, nested_value in value.items()}
  if isinstance(value, list):
    return [_serialize_value(item) for item in value]
  return value


class SearchDocumentsToolInput(BaseModel):
  query: str = Field(min_length=1, max_length=200)
  category: DocumentCategory | None = None
  limit: int = Field(default=5, ge=1, le=10)


class ReadDocumentToolInput(BaseModel):
  slug: str = Field(min_length=1, max_length=255)


class ListMyTasksToolInput(BaseModel):
  status: TaskStatus | None = None
  limit: int = Field(default=10, ge=1, le=20)


class ListPendingApprovalsToolInput(BaseModel):
  limit: int = Field(default=10, ge=1, le=20)


class ListMyMessagesToolInput(BaseModel):
  limit: int = Field(default=10, ge=1, le=20)
  unread_only: bool = False


class GetProfileSummaryToolInput(BaseModel):
  user_id: UUID | None = None


@dataclass(slots=True)
class RegisteredTool:
  name: str
  description: str
  input_model: type[BaseModel]
  executor_name: str


class ToolRegistryService:
  def __init__(
    self,
    *,
    document_service: DocumentService,
    retrieval_service: KnowledgeRetrievalService,
    task_service: TaskService,
    workflow_engine_service: WorkflowEngineService,
    message_center_service: MessageCenterService,
    profile_service: ProfileService,
  ) -> None:
    self._document_service = document_service
    self._retrieval_service = retrieval_service
    self._task_service = task_service
    self._workflow_engine_service = workflow_engine_service
    self._message_center_service = message_center_service
    self._profile_service = profile_service
    self._tools: dict[str, RegisteredTool] = {
      tool.name: tool
      for tool in [
        RegisteredTool(
          name="search_documents",
          description="检索知识库中与问题最相关的制度、SOP、公告或 FAQ。",
          input_model=SearchDocumentsToolInput,
          executor_name="_execute_search_documents",
        ),
        RegisteredTool(
          name="read_document",
          description="按 slug 读取单篇知识库文档的完整内容。",
          input_model=ReadDocumentToolInput,
          executor_name="_execute_read_document",
        ),
        RegisteredTool(
          name="list_my_tasks",
          description="查询当前用户可见的任务清单，可按状态过滤。",
          input_model=ListMyTasksToolInput,
          executor_name="_execute_list_my_tasks",
        ),
        RegisteredTool(
          name="list_pending_approvals",
          description="查询当前用户待处理的审批步骤。",
          input_model=ListPendingApprovalsToolInput,
          executor_name="_execute_list_pending_approvals",
        ),
        RegisteredTool(
          name="list_my_messages",
          description="查询当前用户收件箱中的消息，可只看未读。",
          input_model=ListMyMessagesToolInput,
          executor_name="_execute_list_my_messages",
        ),
        RegisteredTool(
          name="get_profile_summary",
          description="获取当前用户或指定用户的档案摘要。",
          input_model=GetProfileSummaryToolInput,
          executor_name="_execute_get_profile_summary",
        ),
      ]
    }

  def list_tools(self) -> list[RegisteredTool]:
    return list(self._tools.values())

  def get_openai_tools(self) -> list[dict[str, object]]:
    return [
      {
        "type": "function",
        "function": {
          "name": tool.name,
          "description": tool.description,
          "parameters": tool.input_model.model_json_schema(),
        },
      }
      for tool in self.list_tools()
    ]

  async def execute_tool(
    self,
    *,
    actor,
    tool_name: str,
    arguments: dict[str, object] | None = None,
  ) -> dict[str, object]:
    tool = self._tools.get(tool_name)
    if tool is None:
      raise NotFoundError("AI 工具不存在。")
    payload = tool.input_model.model_validate(arguments or {})
    executor = getattr(self, tool.executor_name)
    result = await executor(actor=actor, payload=payload)
    return {
      "tool_name": tool.name,
      "arguments": _serialize_value(payload.model_dump(mode="python")),
      "result": _serialize_value(result),
    }

  async def _execute_search_documents(self, *, actor, payload: SearchDocumentsToolInput) -> dict[str, object]:  # noqa: ANN001
    hits = await self._retrieval_service.search_documents(
      actor=actor,
      query=payload.query,
      category=payload.category,
      limit=payload.limit,
    )
    return {
      "items": [
        {
          "document_id": hit.document.id,
          "title": hit.document.title,
          "slug": hit.document.slug,
          "category": hit.document.category,
          "score": round(hit.score, 4),
          "excerpt": hit.chunk_text[:240],
        }
        for hit in hits
      ]
    }

  async def _execute_read_document(self, *, actor, payload: ReadDocumentToolInput) -> dict[str, object]:  # noqa: ANN001
    document = await self._document_service.get_document_by_slug(actor=actor, slug=payload.slug)
    return {
      "document": {
        "id": document.id,
        "title": document.title,
        "slug": document.slug,
        "category": document.category,
        "status": document.status,
        "version": document.version,
        "published_at": document.published_at,
        "content_md": document.content_md,
      }
    }

  async def _execute_list_my_tasks(self, *, actor, payload: ListMyTasksToolInput) -> dict[str, object]:  # noqa: ANN001
    tasks = await self._task_service.list_tasks(actor=actor)
    filtered_tasks = [task for task in tasks if payload.status is None or task.status == payload.status]
    return {
      "items": [
        {
          "id": task.id,
          "title": task.title,
          "status": task.status,
          "priority": task.priority,
          "due_date": task.due_date,
          "department_name": task.department.name if task.department is not None else None,
          "assignee_email": task.assignee.email if task.assignee is not None else None,
        }
        for task in filtered_tasks[: payload.limit]
      ]
    }

  async def _execute_list_pending_approvals(
    self,
    *,
    actor,
    payload: ListPendingApprovalsToolInput,
  ) -> dict[str, object]:  # noqa: ANN001
    step_runs = await self._workflow_engine_service.list_pending_step_runs(actor=actor)
    return {
      "items": [
        {
          "step_run_id": step_run.id,
          "workflow_instance_id": step_run.instance_id,
          "workflow_name": step_run.instance.definition.name if step_run.instance and step_run.instance.definition else None,
          "step_name": step_run.step.name if step_run.step is not None else None,
          "created_at": step_run.created_at,
          "delegated_from_user_id": step_run.delegated_from_user_id,
        }
        for step_run in step_runs[: payload.limit]
      ]
    }

  async def _execute_list_my_messages(self, *, actor, payload: ListMyMessagesToolInput) -> dict[str, object]:  # noqa: ANN001
    messages = [
      message
      for message in await self._message_center_service.list_messages(actor=actor)
      if message.recipient_user_id == actor.id
    ]

    items = []
    for message in messages:
      receipt_types = {
        receipt.receipt_type
        for receipt in message.receipts
        if receipt.user_id == actor.id
      }
      if payload.unread_only and NotificationReceiptType.READ in receipt_types:
        continue
      items.append(
        {
          "id": message.id,
          "title": message.title,
          "message_type": message.message_type,
          "created_at": message.created_at,
          "read": NotificationReceiptType.READ in receipt_types,
          "acknowledged": NotificationReceiptType.ACKNOWLEDGED in receipt_types,
        }
      )
      if len(items) >= payload.limit:
        break

    return {"items": items}

  async def _execute_get_profile_summary(self, *, actor, payload: GetProfileSummaryToolInput) -> dict[str, object]:  # noqa: ANN001
    profile_view = await self._profile_service.get_profile_view(
      actor=actor,
      user_id=payload.user_id or actor.id,
    )
    return {
      "profile": {
        "user_id": profile_view["user_id"],
        "user_email": profile_view["user_email"],
        "user_status": profile_view["user_status"],
        "employee_no": profile_view["employee_no"],
        "real_name": profile_view["real_name"],
        "department_id": profile_view["department_id"],
        "job_title": profile_view["job_title"],
        "custom_fields": profile_view["custom_fields"],
        "positions_count": len(profile_view["positions"]),
        "visible_fields_count": len(profile_view["visible_fields"]),
      }
    }
