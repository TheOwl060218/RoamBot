from logging.config import fileConfig

from sqlalchemy import engine_from_config, event, pool

from alembic import context
from roambot.config import Settings
from roambot.persistence.database import make_sqlite_url
from roambot.persistence.tables import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    injected_url = config.get_main_option("sqlalchemy.url")
    if injected_url.strip():
        return injected_url.strip()

    database_path = Settings().database_path.expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return make_sqlite_url(database_path)


def _enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"check_same_thread": False},
    )
    event.listen(connectable, "connect", _enable_foreign_keys)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
