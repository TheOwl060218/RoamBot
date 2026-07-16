from pathlib import Path

from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from roambot.persistence.tables import Base

type SessionFactory = sessionmaker[Session]


def make_sqlite_url(path: str | Path) -> str:
    absolute_path = Path(path).expanduser().resolve()
    return URL.create(
        drivername="sqlite+pysqlite",
        database=str(absolute_path),
    ).render_as_string(hide_password=False)


def _enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def create_engine_and_session_factory(path: str | Path) -> tuple[Engine, SessionFactory]:
    database_path = Path(path).expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        make_sqlite_url(database_path),
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", _enable_foreign_keys)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine, factory


def initialize_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)
