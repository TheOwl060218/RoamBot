"""Include itinerary documents in managed schema upgrades."""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    # Earlier stage builds initialized these tables through ORM create_all.
    # Adopt those existing tables without replacing their saved documents.
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "itineraries" not in tables:
        op.create_table(
            "itineraries",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("owner", sa.String(100), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("document_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_itineraries_owner", "itineraries", ["owner"])
    if "itinerary_workspaces" not in tables:
        op.create_table(
            "itinerary_workspaces",
            sa.Column("owner", sa.String(100), primary_key=True),
            sa.Column("current_id", sa.String(36), nullable=True),
        )


def downgrade():
    op.drop_table("itinerary_workspaces")
    op.drop_index("ix_itineraries_owner", table_name="itineraries")
    op.drop_table("itineraries")
