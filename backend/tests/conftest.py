from __future__ import annotations

import ipaddress
import socket
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


def _loopback_socket_address(address: object) -> bool:
    if not isinstance(address, tuple) or not address:
        return True
    host = str(address[0]).split("%", maxsplit=1)[0]
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def deny_external_network(monkeypatch: pytest.MonkeyPatch) -> None:
    original_create_connection = socket.create_connection
    original_socket_connect = socket.socket.connect

    def guarded_create_connection(address: object, *args: object, **kwargs: object):
        if not _loopback_socket_address(address):
            raise AssertionError(f"outbound network is disabled in tests: {address!r}")
        return original_create_connection(address, *args, **kwargs)

    def guarded_socket_connect(instance: socket.socket, address: object):
        if not _loopback_socket_address(address):
            raise AssertionError(f"outbound network is disabled in tests: {address!r}")
        return original_socket_connect(instance, address)

    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)
    monkeypatch.setattr(socket.socket, "connect", guarded_socket_connect)


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
        app.state.session_factory = session_factory
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
