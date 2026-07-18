from __future__ import annotations

import logging
from collections.abc import Mapping
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx

from roambot.providers.protocols import ProviderError

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class ProviderHttpClient:
    def __init__(
        self,
        client: httpx.Client,
        *,
        provider: str,
        base_url: str,
        timeout: float = 5.0,
        secrets: tuple[str, ...] = (),
    ) -> None:
        self._client = client
        self._provider = provider
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._secrets = tuple(secret for secret in secrets if secret)

    def get_json(
        self,
        *,
        operation: str,
        path: str,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            method="GET",
            operation=operation,
            path=path,
            params=params,
            headers=headers,
        )

    def post_json(
        self,
        *,
        operation: str,
        path: str,
        json_body: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            method="POST",
            operation=operation,
            path=path,
            headers=headers,
            json_body=json_body,
        )

    def _request_json(
        self,
        *,
        method: str,
        operation: str,
        path: str,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_id = uuid4().hex
        started = perf_counter()
        status: int | str = "error"
        try:
            response = self._client.request(
                method,
                f"{self._base_url}/{path.lstrip('/')}",
                params=params,
                headers=headers,
                json=json_body,
                timeout=self._timeout,
            )
            status = response.status_code
            if response.status_code == 429:
                raise ProviderError("rate_limited", "Provider rate limit reached.")
            if response.status_code >= 400:
                raise ProviderError("unavailable", "Provider request failed.")
            try:
                payload = response.json()
            except ValueError:
                raise ProviderError("bad_response", "Provider returned invalid JSON.") from None
            if not isinstance(payload, dict):
                raise ProviderError("bad_response", "Provider returned an invalid payload.")
            return payload
        except httpx.TimeoutException:
            status = "timeout"
            raise ProviderError("timeout", "Provider request timed out.") from None
        except httpx.RequestError:
            status = "unavailable"
            raise ProviderError("unavailable", "Provider request failed.") from None
        finally:
            elapsed_ms = round((perf_counter() - started) * 1000)
            logger.info(
                "provider_request provider=%s operation=%s status=%s elapsed_ms=%d request_id=%s",
                self._provider,
                operation,
                status,
                elapsed_ms,
                request_id,
            )

    def redact(self, text: str) -> str:
        redacted = text
        for secret in self._secrets:
            redacted = redacted.replace(secret, "[redacted]")
        return redacted
