"""Add workflow_graph_templates.tags JSONB column.

Revision ID: 20260722_01
Revises: 20260717_02
Create Date: 2026-07-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260722_01"
down_revision = "20260717_02"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
  op.add_column(
    "workflow_graph_templates",
    sa.Column(
      "tags",
      _json_type(),
      nullable=False,
      server_default=sa.text("'[]'"),
    ),
  )
  op.execute(
    """
    UPDATE workflow_graph_templates
    SET tags = '["视频", "选题会"]'::jsonb
    WHERE code LIKE 'topic_meeting_batch%'
    """
  )
  op.execute(
    """
    UPDATE workflow_graph_templates
    SET tags = '["视频", "制作"]'::jsonb
    WHERE code LIKE 'video_production_per_topic%'
    """
  )


def downgrade() -> None:
  op.drop_column("workflow_graph_templates", "tags")
