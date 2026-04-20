from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import Enum, JSON, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.type_api import TypeEngine

from pgvector.sqlalchemy import Vector


def build_enum(*, enum_cls: type, name: str) -> Enum:
  return Enum(
    enum_cls,
    name=name,
    native_enum=False,
    validate_strings=True,
    create_constraint=True,
  )


def build_json_type() -> JSON:
  return JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


def build_vector_type(*, dimensions: int) -> TypeEngine[Any]:
  return Vector(dimensions).with_variant(JSON(), "sqlite")


JsonDefaultFactory = Callable[[], dict[str, Any]]
