"""Allow a closed ballot without selecting a destination; retain related rows."""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _replace_status_check(values):
    connection = op.get_bind()
    table = sa.Table("travel_plans", sa.MetaData(), autoload_with=connection)
    for constraint in table.constraints:
        if isinstance(constraint, sa.CheckConstraint):
            constraint.name = (
                "ck_travel_plans_status" if "status" in str(constraint.sqltext)
                else "ck_travel_plans_expected_count"
            )
    # SQLite rebuilds the parent table. FK enforcement during DROP would cascade
    # into its children; disable it outside a transaction on this connection only.
    with op.get_context().autocommit_block():
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        with op.batch_alter_table("travel_plans", copy_from=table, recreate="always") as batch:
            batch.drop_constraint("ck_travel_plans_status", type_="check")
            batch.create_check_constraint("ck_travel_plans_status", f"status IN ({values})")
        if connection.exec_driver_sql("PRAGMA foreign_key_check").first() is not None:
            raise RuntimeError("Plan migration failed foreign-key validation")
    finally:
        with op.get_context().autocommit_block():
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def upgrade():
    _replace_status_check("'voting', 'closed', 'decided'")


def downgrade():
    # Never silently turn a stopped ballot back into an open one.
    query = sa.text("SELECT 1 FROM travel_plans WHERE status='closed' LIMIT 1")
    if op.get_bind().execute(query).first():
        raise RuntimeError("Resolve closed plans before downgrading")
    _replace_status_check("'voting', 'decided'")
