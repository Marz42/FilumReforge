from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import build_json_type
from app.models.base import Base
from app.models.mixins import TimestampMixin


class Profile(TimestampMixin, Base):
  __tablename__ = "profiles"
  __table_args__ = (
    Index("idx_profiles_department_id", "department_id"),
    Index("idx_profiles_custom_fields_gin", "custom_fields", postgresql_using="gin"),
  )

  user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
  employee_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
  real_name: Mapped[str] = mapped_column(String(120), nullable=False)
  department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id"), nullable=False)
  job_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
  phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
  hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
  custom_fields: Mapped[dict[str, Any]] = mapped_column(build_json_type(), default=dict, nullable=False)

  user = relationship("User", back_populates="profile")
  department = relationship("Department", back_populates="profiles")
