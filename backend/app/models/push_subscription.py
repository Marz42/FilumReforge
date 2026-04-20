from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import build_enum
from app.core.enums import PushSubscriptionStatus
from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PushSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "push_subscriptions"
  __table_args__ = (
    UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
    Index("idx_push_subscriptions_user_status", "user_id", "status"),
  )

  user_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", name="fk_push_subscriptions_user", ondelete="CASCADE"),
    nullable=False,
  )
  endpoint: Mapped[str] = mapped_column(Text, nullable=False)
  p256dh_key: Mapped[str] = mapped_column(Text, nullable=False)
  auth_key: Mapped[str] = mapped_column(Text, nullable=False)
  status: Mapped[PushSubscriptionStatus] = mapped_column(
    build_enum(enum_cls=PushSubscriptionStatus, name="push_subscription_status"),
    default=PushSubscriptionStatus.ACTIVE,
    nullable=False,
  )
  user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
  last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

  user = relationship("User", back_populates="push_subscriptions")
