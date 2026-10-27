"""Add invitation and voting tables."""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "plan_anonymous_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "plan_invites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "plan_id",
            sa.String(36),
            sa.ForeignKey("travel_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_plan_invites_plan_id", "plan_invites", ["plan_id"])
    op.create_table(
        "plan_votes",
        sa.Column(
            "participant_id",
            sa.String(36),
            sa.ForeignKey("plan_participants.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "preferred_candidate_id",
            sa.String(36),
            sa.ForeignKey("plan_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "plan_acceptable",
        sa.Column(
            "participant_id",
            sa.String(36),
            sa.ForeignKey("plan_votes.participant_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("plan_candidates.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade():
    for name in ("plan_acceptable", "plan_votes", "plan_invites", "plan_anonymous_sessions"):
        op.drop_table(name)
