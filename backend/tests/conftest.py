from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from roambot.config import Settings
from roambot.main import create_app
from roambot.persistence.database import (
    SessionFactory,
    create_engine_and_session_factory,
    initialize_schema,
)
from roambot.services.auth import AuthService

type AuthFixture = Callable[..., tuple[AuthService, SessionFactory]]
type AuthApiFixture = Callable[..., tuple[TestClient, AuthService, SessionFactory]]


@pytest.fixture
def auth_fixture(tmp_path: Path) -> Iterator[AuthFixture]:
    engines: list[Engine] = []
    database_number = 0

    def create_fixture(
        *,
        clock: Callable[[], datetime] | None = None,
        session_hours: int = 24,
    ) -> tuple[AuthService, SessionFactory]:
        nonlocal database_number
        database_number += 1
        engine, session_factory = create_engine_and_session_factory(
            tmp_path / f"auth-{database_number}.db"
        )
        initialize_schema(engine)
        engines.append(engine)
        return (
            AuthService(
                session_factory,
                session_hours=session_hours,
                clock=clock or (lambda: datetime.now(UTC)),
            ),
            session_factory,
        )

    yield create_fixture

    for engine in engines:
        engine.dispose()


@pytest.fixture
def auth_api_fixture(auth_fixture: AuthFixture) -> Iterator[AuthApiFixture]:
    clients: list[TestClient] = []

    def create_fixture(
        *,
        secure_cookies: bool = False,
        session_hours: int = 24,
        clock: Callable[[], datetime] | None = None,
    ) -> tuple[TestClient, AuthService, SessionFactory]:
        service, session_factory = auth_fixture(
            clock=clock,
            session_hours=session_hours,
        )
        app = create_app()
        app.state.auth_service = service
        app.state.settings = Settings(
            secure_cookies=secure_cookies,
            session_hours=session_hours,
        )
        client = TestClient(app)
        clients.append(client)
        return client, service, session_factory

    yield create_fixture

    for client in clients:
        client.close()
