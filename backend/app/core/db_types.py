from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import Enum, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.sql.type_api import TypeEngine
from sqlalchemy.types import TypeDecorator

from pgvector.sqlalchemy import Vector


def build_enum(*, enum_cls: type, name: str) -> Enum:
  return Enum(
    enum_cls,
    name=name,
    native_enum=False,
    validate_strings=True,
    create_constraint=True,
  )


def build_value_enum(
  *,
  enum_cls: type,
  name: str,
  length: int | None = None,
  create_constraint: bool = True,
) -> Enum:
  options: dict[str, Any] = {}
  if length is not None:
    options["length"] = length
  return Enum(
    enum_cls,
    name=name,
    native_enum=False,
    validate_strings=True,
    create_constraint=create_constraint,
    values_callable=lambda members: [member.value for member in members],
    **options,
  )


class CompatibleValueEnum(TypeDecorator[Any]):
  """Persist enum values while accepting legacy member-name casing on reads."""

  impl = String
  cache_ok = True

  def __init__(self, *, enum_cls: type, length: int) -> None:
    self.enum_cls = enum_cls
    self.length = length
    super().__init__(length=length)

  def process_bind_param(self, value: Any | None, dialect: Dialect) -> str | None:
    if value is None:
      return None
    if isinstance(value, self.enum_cls):
      return str(value.value)
    try:
      return str(self.enum_cls(str(value).lower()).value)
    except ValueError as exc:
      raise ValueError(f"Unsupported {self.enum_cls.__name__} value: {value!r}") from exc

  def process_result_value(self, value: Any | None, dialect: Dialect) -> Any | None:
    if value is None or isinstance(value, self.enum_cls):
      return value
    try:
      return self.enum_cls(str(value).lower())
    except ValueError as exc:
      raise ValueError(f"Unsupported {self.enum_cls.__name__} database value: {value!r}") from exc


def build_compatible_value_enum(*, enum_cls: type, length: int) -> CompatibleValueEnum:
  return CompatibleValueEnum(enum_cls=enum_cls, length=length)


def build_json_type() -> JSON:
  return JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


def build_vector_type(*, dimensions: int) -> TypeEngine[Any]:
  return Vector(dimensions).with_variant(JSON(), "sqlite")


JsonDefaultFactory = Callable[[], dict[str, Any]]
