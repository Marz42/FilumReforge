"""Iteration 3-F contract: enforce Link iteration and superseded semantics.

Revision ID: 20260716_02
Revises: 20260716_01
Create Date: 2026-07-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260716_02"
down_revision = "20260716_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
  bind = op.get_bind()
  missing = bind.scalar(
    sa.text("SELECT count(*) FROM workflow_human_task_links WHERE iteration IS NULL")
  )
  if missing:
    raise RuntimeError(
      "workflow_human_task_links 仍有 iteration 为空；必须先完成 I3-F reconciliation。"
    )

  op.alter_column("workflow_human_task_links", "iteration", nullable=False)
  op.drop_constraint(
    "wf_human_task_links_lifecycle_chk",
    "workflow_human_task_links",
    type_="check",
  )
  op.create_check_constraint(
    "wf_human_task_links_lifecycle_chk",
    "workflow_human_task_links",
    "lifecycle in ('active', 'completed', 'cancelled', 'invalidated', 'superseded')",
  )
  op.create_check_constraint(
    "wf_human_task_links_iteration_chk",
    "workflow_human_task_links",
    "iteration > 0",
  )
  op.create_check_constraint(
    "wf_human_task_links_superseded_chk",
    "workflow_human_task_links",
    "(lifecycle = 'superseded' AND superseded_at IS NOT NULL "
    "AND superseded_by_link_id IS NOT NULL) "
    "OR (lifecycle <> 'superseded' AND superseded_by_link_id IS NULL)",
  )
  op.create_check_constraint(
    "wf_human_task_links_not_self_chk",
    "workflow_human_task_links",
    "superseded_by_link_id IS NULL OR superseded_by_link_id <> id",
  )


def downgrade() -> None:
  op.drop_constraint(
    "wf_human_task_links_not_self_chk",
    "workflow_human_task_links",
    type_="check",
  )
  op.drop_constraint(
    "wf_human_task_links_superseded_chk",
    "workflow_human_task_links",
    type_="check",
  )
  op.drop_constraint(
    "wf_human_task_links_iteration_chk",
    "workflow_human_task_links",
    type_="check",
  )
  op.drop_constraint(
    "wf_human_task_links_lifecycle_chk",
    "workflow_human_task_links",
    type_="check",
  )
  op.create_check_constraint(
    "wf_human_task_links_lifecycle_chk",
    "workflow_human_task_links",
    "lifecycle in ('active', 'completed', 'cancelled', 'invalidated')",
  )
  op.alter_column("workflow_human_task_links", "iteration", nullable=True)
