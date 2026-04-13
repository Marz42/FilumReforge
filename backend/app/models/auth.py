from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class RefreshToken(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
  __tablename__ = "refresh_tokens"
  __table_args__ = (
    Index("idx_refresh_tokens_user_id", "user_id"),
  )

  user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
  token_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
  expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

  user = relationship("User", back_populates="refresh_tokens")
