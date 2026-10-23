"""Real, category-free map tools and public search. No arbitrary URL fetching."""

import json
import re
import threading
import time
from html import unescape
from urllib.parse import urlsplit
from xml.etree import ElementTree

import httpx
from pydantic import BaseModel, ValidationError

from roambot.domain.discovery import TOOLS, native_tools
from roambot.domain.models import Coordinate
from roambot.providers.amap import _format_coordinate
from roambot.providers.protocols import ProviderError


class InvalidDiscoveryStep(ProviderError):
    def __init__(self, details):
        super().__init__("bad_response", "推荐行动参数需要修正。")
        self.details = details


def safe_public_url(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if (
            parsed.scheme != "https"
            or not host
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
            or "." not in host
        ):
            return None
        import ipaddress

        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            if host.endswith((".local", ".localhost", ".internal")):
                return None
        return value
    except ValueError:
        return None


class PublicSearch:
    """Bounded public RSS search; snippets are evidence, not fetched page contents."""

    def __init__(self, client=None):
        self.client = client

    def search(self, query: str) -> list[dict]:
        def read(client):
            with client.stream(
                "GET",
                "https://cn.bing.com/search",
                params={"q": query, "format": "rss"},
                timeout=10,
                follow_redirects=False,
            ) as response:
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > 256000:
                        raise ProviderError("bad_response", "公开检索响应过大。")
                    chunks.append(chunk)
            raw = b"".join(chunks)
            if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                raise ProviderError("bad_response", "公开检索格式无效。")
            root = ElementTree.fromstring(raw)
            results = []
            for item in root.findall(".//item")[:6]:
                link = safe_public_url(item.findtext("link") or "")
                if link:
                    results.append(
                        {
                            "url": link,
                            "title": unescape(item.findtext("title") or "")[:200],
                            "excerpt": unescape(item.findtext("description") or "")[:1200],
                            "kind": "search_excerpt",
                        }
                    )
            return results

        try:
            if self.client is not None:
                return read(self.client)
            with httpx.Client() as client:
                return read(client)
        except (httpx.HTTPError, ElementTree.ParseError):
            raise ProviderError("unavailable", "公开资料检索暂未完成。") from None


class TavilySearch:
    def __init__(self, api_key, client=None):
        self._key = api_key
        self.client = client
        self.request_count = 0
        self.reported_credits = 0
        self.usage_reported = False
        self.usage_response_count = 0
        self._usage_lock = threading.Lock()

    def search(self, query):
        def read(client):
            with self._usage_lock:
                self.request_count += 1
            response = client.post(
                "https://api.tavily.com/search",
                headers={"Authorization": "Bearer " + self._key},
                json={
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 5,
                    "include_answer": False,
                    "include_raw_content": False,
                    "include_usage": True,
                },
                timeout=15,
                follow_redirects=False,
            )
            response.raise_for_status()
            if len(response.content) > 1500000:
                raise ProviderError("bad_response", "公开资料响应过大。")
            data = response.json()
            with self._usage_lock:
                credits = data.get("usage", {}).get("credits")
                if (
                    isinstance(credits, (int, float))
                    and not isinstance(credits, bool)
                    and credits >= 0
                ):
                    self.reported_credits += credits
                    self.usage_reported = True
                    self.usage_response_count += 1
            results = []
            for item in data.get("results", [])[:5]:
                link = safe_public_url(item.get("url", ""))
                if link:
                    raw = item.get("content") or item.get("raw_content") or ""
                    results.append(
                        {
                            "url": link,
                            "title": str(item.get("title") or "")[:200],
                            "excerpt": str(raw)[:4000],
                            "kind": "search_excerpt" if item.get("content") else "web_page",
                            "retrieved_at": time.time(),
                        }
                    )
            return results

        try:
            if self.client is not None:
                return read(self.client)
            with httpx.Client() as client:
                return read(client)
        except httpx.HTTPStatusError as error:
            raise ProviderError("tavily_http_" + str(error.response.status_code),
                                "公开资料检索暂未完成。") from None
        except httpx.ProxyError:
            raise ProviderError("tavily_proxy_error", "公开资料检索暂未完成。") from None
        except httpx.TimeoutException:
            raise ProviderError("tavily_timeout", "公开资料检索暂未完成。") from None
        except httpx.ConnectError:
            raise ProviderError("tavily_connect_error", "公开资料检索暂未完成。") from None
        except httpx.HTTPError:
            raise ProviderError("tavily_transport_error", "公开资料检索暂未完成。") from None
        except (ValueError, KeyError, TypeError):
            raise ProviderError("tavily_bad_response", "公开资料检索暂未完成。") from None


def source_mentions_place(place, source):
    """Entity binding, not a scenery dictionary. Unrelated pages are not place facts."""
    text = re.sub(r"\s+", "", (source.get("title", "") + source.get("excerpt", ""))).casefold()
    full_name = re.sub(r"\s+", "", place["name"]).casefold()
    base_name = re.split(r"[（(]", full_name, maxsplit=1)[0]
    city = place.get("city", "").removesuffix("市")
    return bool(full_name and full_name in text) or bool(
        len(base_name) >= 3 and base_name in text and city and city in text
    )


def normalized_arguments(model, data, *, user_texts=()):
    """Normalize JSON-encoded arrays only, then perform the full typed validation."""
    if not isinstance(data, dict):
        return data
    from typing import get_args, get_origin

    result = dict(data)
    # Tolerate only redundant provenance for an already-known scalar field,
    # and only when it quotes this user's actual words. Unknown semantic fields
    # and canonical quote fields still go through strict model validation.
    # Never apply this to source text or use it to invent a missing field.
    for key in set(result) - model.model_fields.keys():
        if not isinstance(key, str):
            continue
        base = key.removesuffix('_quote')
        quote = result[key]
        if (base != key and base in model.model_fields and base in result
                and result[base] is not None and not isinstance(result[base], (dict, list))
                and isinstance(quote, str) and quote and any(quote in text for text in user_texts)):
            result.pop(key)

    def nested_model(annotation):
        choices = get_args(annotation) or (annotation,)
        models = [choice for choice in choices
                  if isinstance(choice, type) and issubclass(choice, BaseModel)]
        return models[0] if len(models) == 1 else None
    for name, field in model.model_fields.items():
        if name not in result:
            continue
        if get_origin(field.annotation) is list:
            if isinstance(result[name], str) and len(result[name]) <= 20000:
                try:
                    decoded = json.loads(result[name])
                    if isinstance(decoded, list):
                        result[name] = decoded
                except ValueError:
                    pass
            item_type = get_args(field.annotation)[0]
            if (
                isinstance(result[name], list)
                and isinstance(item_type, type)
                and issubclass(item_type, BaseModel)
            ):
                result[name] = [normalized_arguments(item_type, item, user_texts=user_texts) for item in result[name]]
        else:
            nested = nested_model(field.annotation)
            if nested and isinstance(result[name], dict):
                result[name] = normalized_arguments(nested, result[name], user_texts=user_texts)
    return result


class DiscoveryMap:
    def __init__(self, amap):
        self.amap = amap

    def gps(self, point: Coordinate) -> Coordinate:
        if point.system == "gcj02":
            return point
        if point.system != "wgs84":
            raise ValueError("不支持的定位坐标系。")
        data = self.amap._http.get_json(
            operation="coordinate_convert",
            path="/v3/assistant/coordinate/convert",
            params={
                "key": self.amap._api_key,
                "locations": _format_coordinate(point),
                "coordsys": "gps",
                "output": "json",
            },
        )
        self.amap._require_success(data)
        lng, lat = map(float, data["locations"].split(","))
        return Coordinate(longitude=lng, latitude=lat)

    def geocode(self, address: str):
        return self.amap.geocode(address, "")

    def area(self, point: Coordinate):
        """Resolve coarse public search scope, without disclosing a street address."""
        if point.system != 'gcj02':
            raise ValueError('地区解析需要已转换的地图坐标。')
        payload = self.amap._http.get_json(operation='discovery_area', path='/v3/geocode/regeo',
            params={'key': self.amap._api_key, 'location': _format_coordinate(point),
                    'extensions': 'base', 'output': 'json'})
        self.amap._require_success(payload)
        result = payload.get('regeocode')
        address = result.get('addressComponent') if isinstance(result, dict) else None
        if not isinstance(address, dict):
            raise ProviderError('bad_response', '定位地区响应不完整。')
        parts = [address.get(field) for field in ('province', 'city', 'district')]
        area = ' '.join(dict.fromkeys(value.strip() for value in parts if isinstance(value, str) and value.strip()))
        if not area:
            raise ProviderError('area_unavailable', '定位地区尚未解析完成。')
        return area

    def search(
        self, query: str, region: str | None, center: Coordinate | None, radius: float | None
    ) -> list[dict]:
        params = {
            "key": self.amap._api_key,
            "keywords": query,
            "page_size": "15",
            "page_num": "1",
            "show_fields": "business,navi,photos,children",
            "output": "json",
        }
        if region:
            params.update(region=region, city_limit="true")
        if center is not None:
            params.update(
                location=_format_coordinate(center),
                radius=str(min(50000, round((radius or 5) * 1000))),
                sortrule="distance",
            )
        payload = self.amap._http.get_json(
            operation="discovery_search",
            path="/v5/place/around" if center else "/v5/place/text",
            params=params,
        )
        try:
            self.amap._require_success(payload)
        except ProviderError:
            code = str(payload.get("infocode", ""))
            raise ProviderError(
                "amap_" + code if re.fullmatch(r"\d{5}", code) else "unavailable",
                "地图检索暂未完成。",
            ) from None
        result = []
        for raw in payload.get("pois", [])[:15]:
            if not isinstance(raw, dict) or not raw.get("id") or not raw.get("name"):
                continue
            try:
                lng, lat = map(float, raw["location"].split(","))
                point = Coordinate(longitude=lng, latitude=lat)
            except (KeyError, TypeError, ValueError):
                continue
            business = raw.get("business") if isinstance(raw.get("business"), dict) else {}
            result.append(
                {
                    "id": "amap:" + raw["id"],
                    "name": str(raw["name"])[:200],
                    "address": str(raw.get("address") or "")[:300],
                    "city": raw.get("cityname") or region or "",
                    "coordinate": point.model_dump(),
                    "map_type": raw.get("type") or "",
                    "parent_id": raw.get("parent") or None,
                    "verified_at": time.time(),
                    "facts": {
                        key: business[key]
                        for key in ("opentime_today", "opentime_week", "rating", "cost", "tel")
                        if isinstance(business.get(key), (str, int, float))
                    },
                    "map_url": "https://www.amap.com/detail/" + raw["id"],
                }
            )
        return result

    def route(self, center: Coordinate, place: dict, mode: str) -> dict:
        target = Coordinate(**place["coordinate"])
        paths = {
            "walking": "/v3/direction/walking",
            "bicycling": "/v4/direction/bicycling",
            "driving": "/v3/direction/driving",
        }
        payload = self.amap._http.get_json(
            operation="discovery_route",
            path=paths[mode],
            params={
                "key": self.amap._api_key,
                "origin": _format_coordinate(center),
                "destination": _format_coordinate(target),
                "output": "json",
            },
        )
        if mode == "bicycling":
            if str(payload.get("errcode")) != "0":
                raise ProviderError("unavailable", "骑行路线暂不可用。")
            paths_data = payload.get("data", {}).get("paths", [])
        else:
            self.amap._require_success(payload)
            paths_data = payload.get("route", {}).get("paths", [])
        if not paths_data:
            raise ProviderError("not_found", "未取得实际路线。")
        best = min(paths_data, key=lambda p: float(p["distance"]))
        return {
            "mode": mode,
            "distance_km": float(best["distance"]) / 1000,
            "duration_minutes": round(float(best["duration"]) / 60, 1),
            "estimated": False,
        }


def model_step(provider, messages, allowed=None):
    payload = provider._http.post_json(
        operation="discovery_reasoning",
        path="/chat/completions",
        headers={"Authorization": "Bearer " + provider._key},
        timeout=20,
        json_body={
            "model": provider._model,
            "temperature": 0.2,
            "max_tokens": 2400,
            **(
                {"enable_thinking": provider._enable_thinking}
                if provider._enable_thinking is not None
                else {}
            ),
            "tools": native_tools(allowed),
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "messages": messages,
        },
    )
    try:
        choice = payload["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ValueError("incomplete")
        message = choice["message"]
        calls = message.get("tool_calls") or []
        if len(calls) == 1:
            function = calls[0]["function"]
            if function["name"] in TOOLS:
                action = {"tool": function["name"], "arguments": json.loads(function["arguments"])}
            elif function["name"] == "take_discovery_step":
                action = json.loads(function["arguments"])
            else:
                raise ValueError("unknown")
        else:
            action = json.loads(message["content"])
        name, arguments = action["tool"], action["arguments"]
        if name not in TOOLS:
            raise ValueError("unknown")
        parameters = TOOLS[name][0]
        return name, parameters.model_validate(normalized_arguments(parameters, arguments))
    except ValidationError as error:
        details = [{"field": e["loc"], "type": e["type"]} for e in error.errors()]
        raise InvalidDiscoveryStep(details) from None
    except (KeyError, IndexError, TypeError, ValueError):
        raise InvalidDiscoveryStep("仅选择一个已提供的工具，按其参数合同重新提出行动。") from None


def review_batch(provider, conversation, context, cards, *, record_usage=None):
    from roambot.providers.discovery_review import assess_batch

    return assess_batch(provider, conversation, context, cards, record_usage=record_usage)
