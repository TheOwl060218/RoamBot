"""Add independent travel plans without rewriting existing records."""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "travel_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("start_date", sa.String(10), nullable=False),
        sa.Column("end_date", sa.String(10), nullable=False),
        sa.Column("expected_count", sa.Integer, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("final_candidate_id", sa.String(255), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('voting', 'decided')"),
        sa.CheckConstraint("expected_count >= 1 AND expected_count <= 100"),
    )
    op.create_index("ix_travel_plans_owner_user_id", "travel_plans", ["owner_user_id"])
    op.create_table(
        "plan_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "plan_id",
            sa.String(36),
            sa.ForeignKey("travel_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_id", sa.String(255), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("snapshot_json", sa.Text, nullable=False),
        sa.Column("longitude", sa.Float, nullable=False),
        sa.Column("latitude", sa.Float, nullable=False),
        sa.UniqueConstraint("plan_id", "provider_id"),
    )
    op.create_index("ix_plan_candidates_plan_id", "plan_candidates", ["plan_id"])
    op.create_table(
        "plan_participants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "plan_id",
            sa.String(36),
            sa.ForeignKey("travel_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nickname", sa.String(32), nullable=False),
        sa.Column("normalized_nickname", sa.String(100), nullable=False),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("anonymous_hash", sa.String(64), nullable=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("plan_id", "normalized_nickname"),
        sa.UniqueConstraint("plan_id", "user_id"),
        sa.UniqueConstraint("plan_id", "anonymous_hash"),
        sa.CheckConstraint("(user_id IS NULL) != (anonymous_hash IS NULL)"),
    )
    op.create_index("ix_plan_participants_plan_id", "plan_participants", ["plan_id"])


def downgrade():
    for name in ("plan_participants", "plan_candidates", "travel_plans"):
        op.drop_table(name)
