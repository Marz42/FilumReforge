from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Department(UUIDPrimaryKeyMixin, TimestampMixin, Base):
  __tablename__ = "departments"
  __table_args__ = (
    UniqueConstraint("parent_id", "name", name="uq_departments_parent_name"),
    Index("idx_departments_parent_id", "parent_id"),
  )

  name: Mapped[str] = mapped_column(String(120), nullable=False)
  code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
  parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
  manager_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
  sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

  parent = relationship("Department", remote_side="Department.id", back_populates="children")
  children = relationship("Department", back_populates="parent")
  manager = relationship("User", back_populates="managed_departments")
  profiles = relationship("Profile", back_populates="department")
  profile_positions = relationship("ProfilePosition", back_populates="department")
  reporting_lines = relationship("ReportingLine", back_populates="department")
  delegations = relationship("Delegation", back_populates="scope_department")
  tasks = relationship("Task", back_populates="department")
