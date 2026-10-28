import logging

import httpx
import pytest

from roambot.providers.http import ProviderHttpClient
from roambot.providers.protocols import ProviderError

SECRETS = ("amap-secret-123", "weather-secret-456", "llm-secret-789")


def make_http(handler: httpx.MockTransport) -> ProviderHttpClient:
    return ProviderHttpClient(
        httpx.Client(transport=handler),
        provider="test-provider",
        base_url="https://provider.example.com",
        timeout=0.25,
        secrets=SECRETS,
    )


def assert_sanitized(text: str) -> None:
    assert all(secret not in text for secret in SECRETS)
    assert "key=" not in text
    assert "X-QW-Api-Key" not in text
    assert "Authorization" not in text


@pytest.mark.parametrize("payload,reason", [(SECRETS[2], "json"), ([SECRETS[2]], "envelope")])
def test_invalid_response_body_has_safe_correlated_diagnostics(caplog, payload, reason):
    def handler(request):
        return (
            httpx.Response(200, text=payload)
            if isinstance(payload, str)
            else httpx.Response(200, json=payload)
        )

    client = make_http(httpx.MockTransport(handler))
    with caplog.at_level(logging.INFO), pytest.raises(ProviderError) as captured:
        client.post_json(operation="nomination", path="chat/completions", json_body={})
    assert captured.value.code == "bad_response"
    invalid = next(
        r.getMessage()
        for r in caplog.records
        if r.getMessage().startswith("provider_response_invalid")
    )
    request = next(
        r.getMessage() for r in caplog.records if r.getMessage().startswith("provider_request")
    )
    assert f"reason={reason}" in invalid
    assert invalid.split("request_id=")[1] == request.split("request_id=")[1]
    assert_sanitized(caplog.text)


def test_missing_llm_model_is_reported_as_configuration_failure():
    client = ProviderHttpClient(
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(404, json={"error": SECRETS[2]}))
        ),
        provider="llm",
        base_url="https://provider.example.com/v1",
        secrets=SECRETS,
    )
    with pytest.raises(ProviderError) as captured:
        client.post_json(operation="assistant_turn", path="chat/completions", json_body={})
    assert captured.value.code == "configuration_error"
    assert_sanitized(str(captured.value))


def test_get_json_returns_an_object_without_logging_request_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/data"
        assert request.url.params["key"] == SECRETS[0]
        return httpx.Response(200, json={"status": "ok"})

    client = make_http(httpx.MockTransport(handler))
    with caplog.at_level(logging.INFO, logger="roambot.providers.http"):
        result = client.get_json(
            operation="geocode",
            path="/v1/data",
            params={"key": SECRETS[0]},
            headers={"Authorization": f"Bearer {SECRETS[2]}"},
        )

    assert result == {"status": "ok"}
    assert "provider=test-provider" in caplog.text
    assert "operation=geocode" in caplog.text
    assert_sanitized(caplog.text)


def test_base_url_path_prefix_is_preserved() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(200, json={"status": "ok"})

    client = ProviderHttpClient(
        httpx.Client(transport=httpx.MockTransport(handler)),
        provider="llm",
        base_url="https://provider.example.com/v1",
    )

    assert client.post_json(
        operation="explain",
        path="/chat/completions",
        json_body={"model": "test"},
    ) == {"status": "ok"}


@pytest.mark.parametrize(
    "handler,expected_code",
    [
        (lambda _: httpx.Response(429, json={"error": SECRETS[0]}), "rate_limited"),
        (lambda _: httpx.Response(500, text=SECRETS[1]), "unavailable"),
        (lambda _: httpx.Response(200, text="not-json"), "bad_response"),
        (lambda _: httpx.Response(200, json=[SECRETS[2]]), "bad_response"),
        (lambda _: httpx.Response(400, json={"message": SECRETS[0]}), "unavailable"),
    ],
)
def test_http_and_payload_failures_are_stable_and_sanitized(
    handler: object,
    expected_code: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = make_http(httpx.MockTransport(handler))

    with (
        caplog.at_level(
            logging.INFO,
            logger="roambot.providers.http",
        ),
        pytest.raises(ProviderError) as captured,
    ):
        client.get_json(
            operation="weather",
            path="/v7/weather/7d",
            params={"key": SECRETS[0]},
            headers={"X-QW-Api-Key": SECRETS[1]},
        )

    assert captured.value.code == expected_code
    assert_sanitized(f"{captured.value}\n{caplog.text}")


def test_timeout_is_translated_without_exposing_the_request(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"timed out at {request.url}", request=request)

    client = make_http(httpx.MockTransport(timeout))

    with (
        caplog.at_level(
            logging.INFO,
            logger="roambot.providers.http",
        ),
        pytest.raises(ProviderError) as captured,
    ):
        client.get_json(
            operation="llm",
            path="/chat/completions",
            headers={"Authorization": f"Bearer {SECRETS[2]}"},
        )

    assert captured.value.code == "timeout"
    assert_sanitized(f"{captured.value}\n{caplog.text}")
