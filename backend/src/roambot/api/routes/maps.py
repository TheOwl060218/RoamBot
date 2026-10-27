"""Browser map configuration and a restricted JS API security-code proxy."""

from collections import deque
from time import monotonic

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from roambot.providers.amap import AMapProvider

router = APIRouter(prefix="/maps", tags=["maps"])
sdk_router = APIRouter(prefix="/_AMapService", tags=["maps"])
# Only fixed SDK assets and coarse IP city lookup; no search, geocoding,
# arbitrary destinations, or user-provided upstream URL.
_UPSTREAMS = {
    "v4/map/styles": "https://webapi.amap.com/v4/map/styles",
    "v3/vectormap": "https://restapi.amap.com/v3/vectormap",
    "v3/log/init": "https://restapi.amap.com/v3/log/init",
    "v3/ip": "https://restapi.amap.com/v3/ip",
}


def _credentials(request: Request) -> tuple[str, str]:
    settings = request.app.state.settings
    return (
        settings.amap_js_key.get_secret_value().strip(),
        settings.amap_js_security_code.get_secret_value().strip(),
    )


@router.get("/config")
def map_config(request: Request):
    key, security_code = _credentials(request)
    content = {"enabled": False}
    if key and security_code:
        content = {
            "enabled": True,
            "key": key,
            "service_host": "/_AMapService",
        }
    return JSONResponse(content, headers={"Cache-Control": "no-store"})


@router.get("/_AMapService/{path:path}", include_in_schema=False)
@sdk_router.get("/{path:path}", include_in_schema=False)
async def map_proxy(path: str, request: Request):
    upstream = _UPSTREAMS.get(path)
    if upstream is None:
        return Response(status_code=404)
    key, security_code = _credentials(request)
    if path == "v3/ip":
        runtime = getattr(request.app.state, "provider_runtime", None)
        adapter = getattr(getattr(runtime, "_adapters", None), "geocoder", None)
        if not isinstance(adapter, AMapProvider):
            return Response(status_code=503)
        # Web-service endpoints require the existing server-side Web key,
        # not the public JavaScript SDK key/security-code pair.
        key, security_code = adapter._api_key, ""
    if not key or (path != "v3/ip" and not security_code):
        return Response(status_code=503)
    if len(request.url.query) > 8192:
        return Response(status_code=400)
    calls = getattr(request.app.state, "map_proxy_calls", None)
    if calls is None:
        calls = deque()
        request.app.state.map_proxy_calls = calls
    now = monotonic()
    while calls and now - calls[0] >= 60:
        calls.popleft()
    if len(calls) >= 60:
        return Response(status_code=429, headers={"Retry-After": "60"})
    calls.append(now)
    params = [(k, v) for k, v in request.query_params.multi_items() if k not in {"key", "jscode"}]
    params.append(("key", key))
    if security_code:
        params.append(("jscode", security_code))
    # Never forward client cookies/headers, follow redirects, or expose exceptions.
    try:
        async with (
            httpx.AsyncClient(
                transport=getattr(request.app.state, "map_transport", None),
                timeout=8,
                follow_redirects=False,
                trust_env=False,
            ) as client,
            client.stream("GET", upstream, params=params) as response,
        ):
            if response.status_code != 200:
                return Response(status_code=502)
            chunks = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > 2_000_000:
                    return Response(status_code=502)
                chunks.append(chunk)
            body = b"".join(chunks)
            private_values = [security_code, key if path == "v3/ip" else ""]
            if any(value and value.encode() in body for value in private_values):
                return Response(status_code=502)
            return Response(
                body,
                headers={
                    "Content-Type": response.headers.get(
                        "Content-Type", "application/octet-stream"
                    ),
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                },
            )
    except httpx.HTTPError:
        return Response(status_code=502)
