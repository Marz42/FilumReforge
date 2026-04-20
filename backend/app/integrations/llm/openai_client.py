from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from openai import AsyncOpenAI

from app.core.config import Settings
from app.core.exceptions import ConfigurationError


class OpenAIClient:
  def __init__(
    self,
    settings: Settings,
    *,
    client: AsyncOpenAI | None = None,
  ) -> None:
    self._settings = settings
    self._client = client or AsyncOpenAI(
      api_key=settings.openai_api_key,
      base_url=settings.openai_base_url or None,
    )

  def _require_api_key(self, capability: str) -> None:
    if not self._settings.openai_api_key:
      raise ConfigurationError(f"未配置 OPENAI_API_KEY，无法执行{capability}。")

  async def create_embeddings(
    self,
    *,
    inputs: Sequence[str],
    model: str | None = None,
  ) -> list[list[float]]:
    self._require_api_key("知识库 embedding")
    if not inputs:
      return []

    response = await self._client.embeddings.create(
      model=model or self._settings.openai_embedding_model,
      input=list(inputs),
    )
    return [list(item.embedding) for item in response.data]

  async def create_chat_completion(self, **kwargs: Any) -> Any:
    self._require_api_key("AI 路由")
    return await self._client.chat.completions.create(**kwargs)
