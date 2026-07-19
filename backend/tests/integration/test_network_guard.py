from __future__ import annotations

import socket
from pathlib import Path

import pytest


def test_backend_test_session_denies_external_socket_before_dns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def dns_must_not_run(*args: object, **kwargs: object) -> object:
        raise RuntimeError("network guard did not intercept before DNS")

    monkeypatch.setattr(socket, "getaddrinfo", dns_must_not_run)

    with pytest.raises(AssertionError, match="outbound network is disabled"):
        socket.create_connection(("provider.example.invalid", 443), timeout=0.01)


def test_provider_http_unit_tests_use_mock_transport() -> None:
    unit_dir = Path(__file__).parents[1] / "unit"
    provider_tests = sorted(unit_dir.glob("test_*provider*.py"))

    assert provider_tests
    for path in provider_tests:
        source = path.read_text(encoding="utf-8")
        if "httpx.Client(" in source:
            assert "httpx.MockTransport" in source, path.name
