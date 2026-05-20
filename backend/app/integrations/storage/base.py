from typing import Protocol

from app.schemas.storage import StorageObjectDescriptor


class StorageAdapter(Protocol):
  async def upload(
    self,
    *,
    object_key: str,
    content: bytes,
    content_type: str,
  ) -> StorageObjectDescriptor: ...

  async def delete(self, *, object_key: str) -> None: ...

  async def generate_download_url(
    self,
    *,
    object_key: str,
    expires_in_seconds: int = 300,
  ) -> str: ...

  async def read_object(self, *, object_key: str) -> bytes: ...
