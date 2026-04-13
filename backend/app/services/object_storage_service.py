from app.integrations.storage.base import StorageAdapter
from app.schemas.storage import StorageObjectDescriptor


class ObjectStorageService:
  def __init__(self, adapter: StorageAdapter) -> None:
    self._adapter = adapter

  async def upload(
    self,
    *,
    object_key: str,
    content: bytes,
    content_type: str,
  ) -> StorageObjectDescriptor:
    return await self._adapter.upload(
      object_key=object_key,
      content=content,
      content_type=content_type,
    )

  async def delete(self, *, object_key: str) -> None:
    await self._adapter.delete(object_key=object_key)
