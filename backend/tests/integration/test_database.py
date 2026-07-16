from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from alembic.config import Config
from sqlalchemy import DateTime, Float, String, Text, create_engine, inspect, text
from sqlalchemy.engine import make_url

from alembic import command
from roambot.config import Settings
from roambot.persistence.database import (
    create_engine_and_session_factory,
    initialize_schema,
    make_sqlite_url,
)
from roambot.persistence.tables import Base

BUSINESS_TABLES = {
    "api_cache",
    "favorites",
    "histories",
    "places",
    "shares",
    "user_sessions",
    "users",
}

EXPECTED_COLUMNS = {
    "users": {
        "id": ("VARCHAR(36)", False, True),
        "username": ("VARCHAR(32)", False, False),
        "password_hash": ("TEXT", False, False),
        "created_at": ("DATETIME", False, False),
    },
    "user_sessions": {
        "id": ("VARCHAR(36)", False, True),
        "user_id": ("VARCHAR(36)", False, False),
        "token_hash": ("VARCHAR(64)", False, False),
        "csrf_hash": ("VARCHAR(64)", False, False),
        "expires_at": ("DATETIME", False, False),
        "revoked_at": ("DATETIME", True, False),
    },
    "places": {
        "id": ("VARCHAR(36)", False, True),
        "provider": ("VARCHAR(32)", False, False),
        "provider_place_id": ("VARCHAR(255)", False, False),
        "name": ("VARCHAR(200)", False, False),
        "address": ("VARCHAR(500)", False, False),
        "city": ("VARCHAR(100)", False, False),
        "longitude": ("FLOAT", False, False),
        "latitude": ("FLOAT", False, False),
        "type_name": ("VARCHAR(200)", False, False),
        "type_code": ("VARCHAR(100)", False, False),
        "scenery_tags_json": ("TEXT", False, False),
        "updated_at": ("DATETIME", False, False),
    },
    "favorites": {
        "id": ("VARCHAR(36)", False, True),
        "user_id": ("VARCHAR(36)", False, False),
        "place_id": ("VARCHAR(36)", False, False),
        "created_at": ("DATETIME", False, False),
    },
    "histories": {
        "id": ("VARCHAR(36)", False, True),
        "user_id": ("VARCHAR(36)", False, False),
        "mode": ("VARCHAR(32)", False, False),
        "request_json": ("TEXT", False, False),
        "result_json": ("TEXT", False, False),
        "created_at": ("DATETIME", False, False),
    },
    "shares": {
        "id": ("VARCHAR(36)", False, True),
        "owner_user_id": ("VARCHAR(36)", False, False),
        "history_id": ("VARCHAR(36)", False, False),
        "token_hash": ("VARCHAR(64)", False, False),
        "created_at": ("DATETIME", False, False),
        "revoked_at": ("DATETIME", True, False),
    },
    "api_cache": {
        "cache_key": ("VARCHAR(64)", False, True),
        "provider": ("VARCHAR(32)", False, False),
        "operation": ("VARCHAR(32)", False, False),
        "payload_json": ("TEXT", False, False),
        "created_at": ("DATETIME", False, False),
        "expires_at": ("DATETIME", False, False),
    },
}

EXPECTED_UNIQUES = {
    "users": {("username",)},
    "user_sessions": {("token_hash",)},
    "places": {("provider", "provider_place_id")},
    "favorites": {("user_id", "place_id")},
    "histories": set(),
    "shares": {("token_hash",)},
    "api_cache": set(),
}

EXPECTED_INDEXES = {
    "users": set(),
    "user_sessions": {("user_id",), ("expires_at",)},
    "places": set(),
    "favorites": {("user_id",)},
    "histories": {("user_id", "created_at")},
    "shares": {("owner_user_id",), ("history_id",)},
    "api_cache": {("expires_at",)},
}

EXPECTED_FOREIGN_KEYS = {
    "users": set(),
    "user_sessions": {(("user_id",), "users", ("id",), "CASCADE")},
    "places": set(),
    "favorites": {
        (("user_id",), "users", ("id",), "CASCADE"),
        (("place_id",), "places", ("id",), "CASCADE"),
    },
    "histories": {(("user_id",), "users", ("id",), "CASCADE")},
    "shares": {
        (("owner_user_id",), "users", ("id",), "CASCADE"),
        (("history_id",), "histories", ("id",), "CASCADE"),
    },
    "api_cache": set(),
}


def _type_name(column_type: object) -> str:
    if isinstance(column_type, Text):
        return "TEXT"
    if isinstance(column_type, DateTime):
        return "DATETIME"
    if isinstance(column_type, Float):
        return "FLOAT"
    if isinstance(column_type, String):
        return f"VARCHAR({column_type.length})"
    raise AssertionError(f"unexpected SQL type: {column_type!r}")


def _reflected_columns(inspector: object, table_name: str) -> dict[str, tuple[str, bool, bool]]:
    return {
        column["name"]: (
            _type_name(column["type"]),
            column["nullable"],
            bool(column["primary_key"]),
        )
        for column in inspector.get_columns(table_name)
    }


def test_upgrade_head_is_repeatable_and_creates_exact_schema(tmp_path: Path) -> None:
    url = make_sqlite_url(tmp_path / "migration.db")
    config = Config("backend/alembic.ini")
    config.set_main_option("sqlalchemy.url", url)

    command.upgrade(config, "head")
    command.upgrade(config, "head")

    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == BUSINESS_TABLES | {"alembic_version"}

        for table_name in BUSINESS_TABLES:
            assert _reflected_columns(inspector, table_name) == EXPECTED_COLUMNS[table_name]
            assert {
                tuple(item["column_names"])
                for item in inspector.get_unique_constraints(table_name)
            } == EXPECTED_UNIQUES[table_name]
            assert {
                tuple(item["column_names"]) for item in inspector.get_indexes(table_name)
            } == EXPECTED_INDEXES[table_name]
            assert {
                (
                    tuple(item["constrained_columns"]),
                    item["referred_table"],
                    tuple(item["referred_columns"]),
                    item["options"].get("ondelete"),
                )
                for item in inspector.get_foreign_keys(table_name)
            } == EXPECTED_FOREIGN_KEYS[table_name]

        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001"
    finally:
        engine.dispose()


def test_orm_metadata_matches_schema_contract() -> None:
    assert set(Base.metadata.tables) == BUSINESS_TABLES

    for table_name, table in Base.metadata.tables.items():
        actual = {
            column.name: (_type_name(column.type), column.nullable, column.primary_key)
            for column in table.columns
        }
        assert actual == EXPECTED_COLUMNS[table_name]
        for column in table.columns:
            if isinstance(column.type, DateTime):
                assert column.type.timezone is True


def test_settings_defaults_and_environment_override(
    tmp_path: Path, monkeypatch: object
) -> None:
    for name in (
        "ROAMBOT_DATA_DIR",
        "ROAMBOT_DATABASE_NAME",
        "ROAMBOT_SECURE_COOKIES",
        "ROAMBOT_SESSION_HOURS",
    ):
        monkeypatch.delenv(name, raising=False)

    defaults = Settings()
    assert defaults.data_dir == Path("data")
    assert defaults.database_name == "roambot.db"
    assert defaults.database_path == Path("data/roambot.db")
    assert defaults.secure_cookies is False
    assert defaults.session_hours == 24

    monkeypatch.setenv("ROAMBOT_DATA_DIR", str(tmp_path / "configured"))
    monkeypatch.setenv("ROAMBOT_DATABASE_NAME", "custom.db")
    monkeypatch.setenv("ROAMBOT_SECURE_COOKIES", "true")
    monkeypatch.setenv("ROAMBOT_SESSION_HOURS", "12")
    configured = Settings()

    assert configured.database_path == tmp_path / "configured" / "custom.db"
    assert configured.secure_cookies is True
    assert configured.session_hours == 12


def test_database_helpers_use_absolute_url_parent_directory_and_foreign_keys(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.chdir(tmp_path)
    database_path = Path("nested/roambot.db")
    expected_path = database_path.resolve()

    url = make_sqlite_url(database_path)
    parsed_url = make_url(url)
    assert parsed_url.drivername == "sqlite+pysqlite"
    assert Path(parsed_url.database).resolve() == expected_path
    assert not database_path.parent.exists()

    engine, session_factory = create_engine_and_session_factory(database_path)
    try:
        assert database_path.parent.is_dir()
        with engine.connect() as connection:
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
            with ThreadPoolExecutor(max_workers=1) as executor:
                result = executor.submit(
                    lambda: connection.scalar(text("SELECT 1"))
                ).result()
            assert result == 1

        initialize_schema(engine)
        assert set(inspect(engine).get_table_names()) == BUSINESS_TABLES
        with session_factory() as session:
            assert session.scalar(text("SELECT 1")) == 1
    finally:
        engine.dispose()
