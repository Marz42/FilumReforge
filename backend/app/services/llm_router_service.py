from __future__ import annotations

import json
from dataclasses import dataclass

from app.core.config import Settings
from app.core.exceptions import ConflictError
from app.integrations.llm.openai_client import OpenAIClient
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService, KnowledgeSearchHit
from app.services.tool_registry_service import ToolRegistryService


@dataclass(slots=True)
class RouterResult:
  mode: str
  prompt: str
  reply_text: str
  tool_results: list[dict[str, object]]
  command_name: str | None = None
  knowledge_hits: list[KnowledgeSearchHit] | None = None


class LLMRouterService:
  def __init__(
    self,
    *,
    settings: Settings,
    openai_client: OpenAIClient,
    retrieval_service: KnowledgeRetrievalService,
    tool_registry_service: ToolRegistryService,
  ) -> None:
    self._settings = settings
    self._openai_client = openai_client
    self._retrieval_service = retrieval_service
    self._tool_registry_service = tool_registry_service

  async def route_text(self, *, actor, text: str) -> RouterResult:  # noqa: ANN001
    normalized_text = text.strip()
    if not normalized_text:
      raise ConflictError("请输入 @系统 或 / 命令内容。")

    if normalized_text.startswith("@系统"):
      prompt = normalized_text.removeprefix("@系统").strip()
      if not prompt:
        raise ConflictError("请在 @系统 后输入问题。")
      return await self._handle_mention(actor=actor, prompt=prompt)

    if normalized_text.startswith("/"):
      return await self._handle_slash_command(actor=actor, text=normalized_text)

    raise ConflictError("当前输入不是支持的 @系统 或 / 命令。")

  async def _handle_slash_command(self, *, actor, text: str) -> RouterResult:  # noqa: ANN001
    raw_command, _, raw_args = text.partition(" ")
    command = raw_command[1:].strip().lower()
    args_text = raw_args.strip()

    if command in {"docs", "kb"}:
      if not args_text:
        raise ConflictError("请在 /docs 后提供检索内容。")
      tool_result = await self._tool_registry_service.execute_tool(
        actor=actor,
        tool_name="search_documents",
        arguments={"query": args_text},
      )
      reply_text = self._format_search_documents_reply(tool_result["result"]["items"])
    elif command == "doc":
      if not args_text:
        raise ConflictError("请在 /doc 后提供文档 slug。")
      tool_result = await self._tool_registry_service.execute_tool(
        actor=actor,
        tool_name="read_document",
        arguments={"slug": args_text},
      )
      reply_text = self._format_read_document_reply(tool_result["result"]["document"])
    elif command == "tasks":
      arguments = {"status": args_text} if args_text else {}
      tool_result = await self._tool_registry_service.execute_tool(
        actor=actor,
        tool_name="list_my_tasks",
        arguments=arguments,
      )
      reply_text = self._format_list_reply("任务", tool_result["result"]["items"], "title")
    elif command == "approvals":
      tool_result = await self._tool_registry_service.execute_tool(
        actor=actor,
        tool_name="list_pending_approvals",
        arguments={},
      )
      reply_text = self._format_list_reply("待审批", tool_result["result"]["items"], "step_name")
    elif command == "messages":
      tool_result = await self._tool_registry_service.execute_tool(
        actor=actor,
        tool_name="list_my_messages",
        arguments={"unread_only": args_text.lower() == "unread"},
      )
      reply_text = self._format_list_reply("消息", tool_result["result"]["items"], "title")
    elif command == "profile":
      tool_result = await self._tool_registry_service.execute_tool(
        actor=actor,
        tool_name="get_profile_summary",
        arguments={},
      )
      reply_text = self._format_profile_reply(tool_result["result"]["profile"])
    else:
      raise ConflictError("不支持的命令。可用命令：/docs /doc /tasks /approvals /messages /profile")

    return RouterResult(
      mode="slash_command",
      prompt=text,
      command_name=command,
      reply_text=reply_text,
      tool_results=[tool_result],
      knowledge_hits=None,
    )

  async def _handle_mention(self, *, actor, prompt: str) -> RouterResult:  # noqa: ANN001
    rag_context, knowledge_hits = await self._retrieval_service.build_rag_context(
      actor=actor,
      query=prompt,
      limit=3,
    )
    messages: list[dict[str, object]] = [
      {
        "role": "system",
        "content": (
          "你是 Project Filum 的系统助手。"
          "只能基于知识库上下文和工具结果回答，不要编造未执行过的数据。"
          f"\n\n知识库上下文：\n{rag_context or '当前没有命中的知识库片段。'}"
        ),
      },
      {"role": "user", "content": prompt},
    ]

    tool_results: list[dict[str, object]] = []
    for _ in range(4):
      response = await self._openai_client.create_chat_completion(
        model=self._settings.openai_chat_model,
        messages=messages,
        tools=self._tool_registry_service.get_openai_tools(),
        tool_choice="auto",
      )
      message = response.choices[0].message
      tool_calls = getattr(message, "tool_calls", None) or []
      if not tool_calls:
        reply_text = message.content or self._build_tool_only_reply(tool_results)
        return RouterResult(
          mode="mention",
          prompt=prompt,
          reply_text=reply_text,
          tool_results=tool_results,
          knowledge_hits=knowledge_hits,
        )

      assistant_tool_calls = []
      for tool_call in tool_calls:
        arguments = json.loads(tool_call.function.arguments or "{}")
        tool_result = await self._tool_registry_service.execute_tool(
          actor=actor,
          tool_name=tool_call.function.name,
          arguments=arguments,
        )
        tool_results.append(tool_result)
        assistant_tool_calls.append(
          {
            "id": tool_call.id,
            "type": "function",
            "function": {
              "name": tool_call.function.name,
              "arguments": tool_call.function.arguments or "{}",
            },
          }
        )

      messages.append(
        {
          "role": "assistant",
          "content": message.content or "",
          "tool_calls": assistant_tool_calls,
        }
      )
      for tool_call, tool_result in zip(tool_calls, tool_results[-len(tool_calls):], strict=True):
        messages.append(
          {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(tool_result, ensure_ascii=False),
          }
        )

    return RouterResult(
      mode="mention",
      prompt=prompt,
      reply_text=self._build_tool_only_reply(tool_results),
      tool_results=tool_results,
      knowledge_hits=knowledge_hits,
    )

  @staticmethod
  def _build_tool_only_reply(tool_results: list[dict[str, object]]) -> str:
    if not tool_results:
      return "我暂时没有可返回的结果。"
    lines = ["已执行以下工具："]
    for index, tool_result in enumerate(tool_results, start=1):
      lines.append(f"{index}. {tool_result['tool_name']}")
    return "\n".join(lines)

  @staticmethod
  def _format_search_documents_reply(items: list[dict[str, object]]) -> str:
    if not items:
      return "未检索到匹配的知识库文档。"
    return "\n".join(
      [
        "匹配到以下知识库文档：",
        *[
          f"{index}. {item['title']} ({item['slug']}) - {item['excerpt']}"
          for index, item in enumerate(items, start=1)
        ],
      ]
    )

  @staticmethod
  def _format_read_document_reply(document: dict[str, object]) -> str:
    return (
      f"{document['title']} ({document['slug']})\n"
      f"状态：{document['status']}\n"
      f"版本：{document['version']}\n\n"
      f"{document['content_md']}"
    )

  @staticmethod
  def _format_list_reply(label: str, items: list[dict[str, object]], title_key: str) -> str:
    if not items:
      return f"当前没有可返回的{label}。"
    return "\n".join(
      [
        f"当前{label}：",
        *[
          f"{index}. {item.get(title_key) or '未命名'}"
          for index, item in enumerate(items, start=1)
        ],
      ]
    )

  @staticmethod
  def _format_profile_reply(profile: dict[str, object]) -> str:
    display_name = profile["real_name"] or "当前用户"
    return (
      f"档案摘要：{display_name}\n"
      f"账号状态：{profile['user_status']}\n"
      f"岗位：{profile['job_title'] or '未设置'}\n"
      f"可见字段数：{profile['visible_fields_count']}"
    )
