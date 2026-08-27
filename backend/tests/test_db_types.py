from __future__ import annotations

import pytest
from alembic.migration import MigrationContext
from sqlalchemy import Column, MetaData, String, Table, insert, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.db_types import CompatibleValueEnum, build_compatible_value_enum
from app.core.enums import TaskStatus
from app.models import EmploymentEvent, Task, TaskLog, User


@pytest.mark.asyncio
async def test_compatible_value_enum_reads_legacy_casing_and_writes_canonical_values() -> None:
  metadata = MetaData()
  status_table = Table(
    "ki014_status_compatibility",
    metadata,
    Column("status", build_compatible_value_enum(enum_cls=TaskStatus, length=16), nullable=False),
  )
  engine = create_async_engine("sqlite+aiosqlite:///:memory:")

  try:
    async with engine.begin() as connection:
      await connection.run_sync(metadata.create_all)
      await connection.execute(insert(status_table).values(status=TaskStatus.BLOCKED))
      raw_status = await connection.scalar(text("SELECT status FROM ki014_status_compatibility"))
      assert raw_status == "blocked"

      await connection.execute(text("UPDATE ki014_status_compatibility SET status = 'TODO'"))
      decoded_status = await connection.scalar(select(status_table.c.status))
      assert decoded_status == TaskStatus.TODO
  finally:
    await engine.dispose()


def test_ki014_phase_a_metadata_matches_non_destructive_authority_decisions() -> None:
  trigger_status_type = EmploymentEvent.__table__.c.trigger_status.type
  assert trigger_status_type.length == 32
  assert "ck_employment_events_employment_events_trigger_status_check" in {
    constraint.name for constraint in EmploymentEvent.__table__.constraints
  }

  for column in (
    Task.__table__.c.status,
    TaskLog.__table__.c.from_status,
    TaskLog.__table__.c.to_status,
  ):
    assert isinstance(column.type, CompatibleValueEnum)
    assert isinstance(column.type.impl, String)
    assert column.type.impl.length == 16

  assert "idx_users_invitation_token_hash" in {index.name for index in User.__table__.indexes}


def test_ki014_phase_a_types_have_expected_alembic_comparison_behavior() -> None:
  context = MigrationContext.configure(dialect_name="postgresql")
  task_status_type = build_compatible_value_enum(enum_cls=TaskStatus, length=16)
  trigger_status_type = EmploymentEvent.__table__.c.trigger_status.type

  assert context.impl.compare_type(Column("status", String(6)), Column("status", task_status_type)) is True
  assert context.impl.compare_type(Column("status", String(16)), Column("status", task_status_type)) is False
  assert (
    context.impl.compare_type(
      Column("trigger_status", String(32)),
      Column("trigger_status", trigger_status_type),
    )
    is False
  )


def test_compatible_value_enum_rejects_unknown_values() -> None:
  enum_type = build_compatible_value_enum(enum_cls=TaskStatus, length=16)

  with pytest.raises(ValueError, match="Unsupported TaskStatus value"):
    enum_type.process_bind_param("paused", dialect=None)  # type: ignore[arg-type]

  with pytest.raises(ValueError, match="Unsupported TaskStatus database value"):
    enum_type.process_result_value("PAUSED", dialect=None)  # type: ignore[arg-type]
