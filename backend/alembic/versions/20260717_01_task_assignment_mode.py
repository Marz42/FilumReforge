"""Add tasks.assignment_mode for first-class Work Item assignment policy.

Iteration 3 decoupled standalone Task from the graph engine, but downstream
capabilities (task center bucketing, delegate, handshake) still inferred
behaviour from graph metadata. This revision introduces an explicit
``assignment_mode`` column so a Task can declare its assignment policy without
depending on the existence of a WorkflowGraphInstance / NodeInstance / Link.

Only ``direct`` is produced in this pass; ``handshake`` is reserved for the
next batch (PENDING_ACCEPTANCE / DECLINED state machine).

Revision ID: 20260717_01
Revises: 20260716_02
Create Date: 2026-07-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260717_01"
down_revision = "20260716_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column(
    "tasks",
    sa.Column(
      "assignment_mode",
      sa.String(length=16),
      nullable=False,
      server_default="direct",
    ),
  )
  op.create_check_constraint(
    "ck_tasks_assignment_mode",
    "tasks",
    "assignment_mode in ('direct', 'handshake')",
  )


def downgrade() -> None:
  op.drop_constraint("ck_tasks_assignment_mode", "tasks", type_="check")
  op.drop_column("tasks", "assignment_mode")
