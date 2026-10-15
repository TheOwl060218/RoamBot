"""Append weather checks without mutating recommendation snapshots."""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "plan_weather_checks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "plan_id",
            sa.String(36),
            sa.ForeignKey("travel_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("plan_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "triggered_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("weather_json", sa.Text, nullable=True),
        sa.Column("risk", sa.String(16), nullable=True),
        sa.Column("change", sa.String(32), nullable=False),
    )
    op.create_index("ix_plan_weather_checks_plan_id", "plan_weather_checks", ["plan_id"])
    op.create_index("ix_plan_weather_checks_candidate_id", "plan_weather_checks", ["candidate_id"])


def downgrade():
    op.drop_table("plan_weather_checks")
