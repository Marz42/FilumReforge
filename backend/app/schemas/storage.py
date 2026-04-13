from pydantic import BaseModel


class StorageObjectDescriptor(BaseModel):
  storage_provider: str
  bucket: str
  object_key: str
