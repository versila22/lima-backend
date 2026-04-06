"""Add performance indexes on members and alignments.

Revision ID: 20260406_2230
Revises: 20260406_2135
Create Date: 2026-04-06 22:30:00
"""
from alembic import op

revision = "20260406_2230"
down_revision = "20260406_2135"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_members_activation_token", "members", ["activation_token"], unique=False)
    op.create_index("ix_members_reset_token", "members", ["reset_token"], unique=False)
    op.create_index("ix_members_app_role", "members", ["app_role"], unique=False)
    op.create_index("ix_alignments_season_status", "alignments", ["season_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_members_activation_token", table_name="members")
    op.drop_index("ix_members_reset_token", table_name="members")
    op.drop_index("ix_members_app_role", table_name="members")
    op.drop_index("ix_alignments_season_status", table_name="alignments")
