from __future__ import annotations

from pathlib import Path

from app.integrations.storage.base import StorageAdapter
from app.schemas.storage import StorageObjectDescriptor


class LocalStorageAdapter(StorageAdapter):
  def __init__(self, *, base_path: str, bucket: str) -> None:
    self._base_path = Path(base_path)
    self._bucket = bucket

  def _resolve_path(self, object_key: str) -> Path:
    relative_path = Path(object_key)
    if relative_path.is_absolute() or ".." in relative_path.parts:
      raise ValueError("非法的对象存储路径。")
    return self._base_path / self._bucket / relative_path

  async def upload(
    self,
    *,
    object_key: str,
    content: bytes,
    content_type: str,
  ) -> StorageObjectDescriptor:
    target_path = self._resolve_path(object_key)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content)
    return StorageObjectDescriptor(
      storage_provider="local",
      bucket=self._bucket,
      object_key=object_key,
    )

  async def delete(self, *, object_key: str) -> None:
    target_path = self._resolve_path(object_key)
    if target_path.exists():
      target_path.unlink()

  async def generate_download_url(
    self,
    *,
    object_key: str,
    expires_in_seconds: int = 300,
  ) -> str:
    return str(self._resolve_path(object_key))
