"""Durable, identity-scoped conversational command records."""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assistant_commands",
        sa.Column("actor", sa.String(100), primary_key=True),
        sa.Column("request_id", sa.String(100), primary_key=True),
        sa.Column("proposal", sa.String(36), nullable=False, unique=True),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("assistant_commands")
