from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DepartmentRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  name: str
  code: str
  parent_id: UUID | None
  manager_id: UUID | None
  sort_order: int
  is_active: bool
  created_at: datetime
  updated_at: datetime


class DepartmentTreeNode(BaseModel):
  id: UUID
  name: str
  code: str
  parent_id: UUID | None
  manager_id: UUID | None
  sort_order: int
  is_active: bool
  children: list["DepartmentTreeNode"] = Field(default_factory=list)


DepartmentTreeNode.model_rebuild()


class DepartmentCreateRequest(BaseModel):
  name: str = Field(min_length=1, max_length=120)
  code: str = Field(min_length=1, max_length=64)
  parent_id: UUID | None = None
  manager_id: UUID | None = None
  sort_order: int = 0


class DepartmentUpdateRequest(BaseModel):
  name: str | None = Field(default=None, min_length=1, max_length=120)
  code: str | None = Field(default=None, min_length=1, max_length=64)
  parent_id: UUID | None = None
  manager_id: UUID | None = None
  sort_order: int | None = None
  is_active: bool | None = None
