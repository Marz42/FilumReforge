"""1B: workflow graph template scope departments

Revision ID: 20260709_01
Revises: 20260623_01
Create Date: 2026-07-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260709_01"
down_revision = "20260623_01"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
  op.add_column(
    "workflow_graph_templates",
    sa.Column(
      "scope_department_ids",
      _json_type(),
      nullable=False,
      server_default=sa.text("'[]'"),
    ),
  )


def downgrade() -> None:
  op.drop_column("workflow_graph_templates", "scope_department_ids")
