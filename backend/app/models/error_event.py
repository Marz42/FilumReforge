from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import build_json_type
from app.models.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class ErrorEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
  __tablename__ = "error_events"
  __table_args__ = (
    Index("idx_error_events_request_id", "request_id"),
    Index("idx_error_events_scope_created_at", "scope", "created_at"),
    Index("idx_error_events_actor_user_id", "actor_user_id", "created_at"),
    Index("idx_error_events_source_binding", "source_type", "source_id"),
  )

  request_id: Mapped[str] = mapped_column(String(64), nullable=False)
  scope: Mapped[str] = mapped_column(String(128), nullable=False)
  actor_user_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("users.id", name="fk_error_events_actor_user"),
    nullable=True,
  )
  source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
  source_id: Mapped[UUID | None] = mapped_column(nullable=True)
  http_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
  path: Mapped[str | None] = mapped_column(String(255), nullable=True)
  error_type: Mapped[str] = mapped_column(String(255), nullable=False)
  error_message: Mapped[str] = mapped_column(Text, nullable=False)
  error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
  stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
  context_json: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)

  actor_user = relationship("User")
