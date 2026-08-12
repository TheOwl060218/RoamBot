from __future__ import annotations

from hashlib import sha256
from math import asin, cos, isfinite, radians, sin, sqrt
from unicodedata import normalize

from roambot.domain.models import (
    Coordinate,
    Destination,
    DistanceEstimate,
    Origin,
    PlaceSuggestion,
    SceneryType,
)
from roambot.domain.scenery import classify_scenery
from roambot.providers.http import ProviderHttpClient
from roambot.providers.protocols import ProviderError

SEARCH_TERMS = {
    SceneryType.LAKE: "湖泊景区",
    SceneryType.SEA: "滨海景区",
    SceneryType.OLD_TOWN: "古镇",
    SceneryType.MUSEUM: "博物馆",
    SceneryType.PARK: "公园",
    SceneryType.MOUNTAIN: "山岳景区",
}


class AMapProvider:
    def __init__(self, http: ProviderHttpClient, api_key: str) -> None:
        self._http = http
        self._api_key = api_key

    def geocode(self, address: str, city: str) -> Origin:
        params = {
            "key": self._api_key,
            "address": address,
            "output": "json",
        }
        city_hint = city.strip()
        if city_hint:
            params["city"] = city_hint
        payload = self._http.get_json(
            operation="geocode", path="/v3/geocode/geo", params=params
        )
        self._require_success(payload)
        geocodes = payload.get("geocodes")
        if not isinstance(geocodes, list):
            raise _bad_response()
        if not geocodes and city_hint:
            params.pop("city")
            payload = self._http.get_json(
                operation="geocode", path="/v3/geocode/geo", params=params
            )
            self._require_success(payload)
            geocodes = payload.get("geocodes")
            if not isinstance(geocodes, list):
                raise _bad_response()
        if not geocodes:
            raise ProviderError("not_found", "未找到出发地")
        first = geocodes[0]
        if not isinstance(first, dict):
            raise _bad_response()
        coordinate = _parse_coordinate(first.get("location"))
        formatted = first.get("formatted_address")
        return Origin(
            label=address,
            address=formatted if isinstance(formatted, str) and formatted else address,
            coordinate=coordinate,
        )

    def suggest(self, keywords: str, city: str) -> list[PlaceSuggestion]:
        payload = self._http.get_json(
            operation="input_tips",
            path="/v3/assistant/inputtips",
            params={
                "key": self._api_key,
                "keywords": keywords.strip(),
                "city": city.strip(),
                "citylimit": "false",
                "datatype": "poi",
                "output": "json",
            },
        )
        self._require_success(payload)
        tips = payload.get("tips")
        if not isinstance(tips, list):
            raise _bad_response()
        results: list[PlaceSuggestion] = []
        for raw in tips:
            if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
                continue
            name = raw["name"].strip()
            if not name:
                continue
            results.append(
                PlaceSuggestion(
                    provider_id=raw.get("id") if isinstance(raw.get("id"), str) else "",
                    name=name,
                    district=raw.get("district") if isinstance(raw.get("district"), str) else "",
                    address=raw.get("address") if isinstance(raw.get("address"), str) else "",
                    coordinate=_optional_coordinate(raw.get("location")),
                )
            )
            if len(results) == 5:
                break
        return results

    def search(
        self,
        center: Coordinate,
        city: str,
        scenery_types: tuple[SceneryType, ...],
        radius_km: float,
    ) -> list[Destination]:
        selected_types = tuple(dict.fromkeys(scenery_types))[:6]
        if not selected_types:
            return []

        candidate_groups: list[list[Destination]] = []
        seen: set[str] = set()
        use_around = radius_km <= 50
        for scenery_type in selected_types:
            params = self._place_params(SEARCH_TERMS[scenery_type], city)
            filter_locally = not use_around
            if use_around:
                params.update(
                    {
                        "location": _format_coordinate(center),
                        "radius": str(max(1, min(50000, round(radius_km * 1000)))),
                        "sortrule": "weight",
                    }
                )
                path = "/v5/place/around"
            else:
                path = "/v5/place/text"

            payload = self._http.get_json(
                operation="poi_search",
                path=path,
                params=params,
            )
            candidates = [
                candidate.model_copy(update={"popularity_rank": rank})
                for rank, candidate in enumerate(self._parse_pois(payload, city), start=1)
            ]
            if use_around and not candidates:
                payload = self._http.get_json(
                    operation="poi_search",
                    path="/v5/place/text",
                    params=self._place_params(SEARCH_TERMS[scenery_type], city),
                )
                candidates = [
                    candidate.model_copy(update={"popularity_rank": rank})
                    for rank, candidate in enumerate(
                        self._parse_pois(payload, city), start=1
                    )
                ]
                filter_locally = True
            group: list[Destination] = []
            for candidate in candidates:
                if filter_locally and _haversine_km(center, candidate.coordinate) > radius_km:
                    continue
                if candidate.provider_id in seen:
                    continue
                seen.add(candidate.provider_id)
                group.append(candidate)
            candidate_groups.append(group)

        quotas = [0] * len(candidate_groups)
        remaining = 25
        while remaining:
            progressed = False
            for index, group in enumerate(candidate_groups):
                if quotas[index] >= len(group):
                    continue
                quotas[index] += 1
                remaining -= 1
                progressed = True
                if remaining == 0:
                    break
            if not progressed:
                break

        merged: list[Destination] = []
        for group, quota in zip(candidate_groups, quotas, strict=True):
            merged.extend(group[:quota])

        return merged

    def resolve(self, name: str, city: str) -> Destination:
        payload = self._http.get_json(
            operation="poi_search",
            path="/v5/place/text",
            params=self._place_params(name.strip(), city),
        )
        candidates = self._parse_pois(payload, city)
        if not candidates:
            raise ProviderError("not_found", "未找到指定地点")
        normalized_target = _normalize_name(name)
        return next(
            (
                candidate
                for candidate in candidates
                if _normalize_name(candidate.name) == normalized_target
            ),
            candidates[0],
        )

    def measure(
        self,
        origins: list[Origin],
        destination: Destination,
    ) -> list[DistanceEstimate]:
        if not origins or len(origins) > 100:
            raise ProviderError("bad_request", "高德距离请求的起点数量无效")
        payload = self._http.get_json(
            operation="distance",
            path="/v3/distance",
            params={
                "key": self._api_key,
                "origins": "|".join(_format_coordinate(origin.coordinate) for origin in origins),
                "destination": _format_coordinate(destination.coordinate),
                "type": "1",
                "output": "json",
            },
        )
        self._require_success(payload)
        results = payload.get("results")
        if not isinstance(results, list) or len(results) != len(origins):
            raise _bad_response()

        estimates: list[DistanceEstimate] = []
        for origin, result in zip(origins, results, strict=True):
            if not isinstance(result, dict):
                raise _bad_response()
            distance_m = _nonnegative_number(result.get("distance"))
            duration_s = _nonnegative_number(result.get("duration"))
            estimates.append(
                DistanceEstimate(
                    origin_label=origin.label,
                    distance_km=round(distance_m / 1000, 2),
                    duration_minutes=round(duration_s / 60, 2),
                    estimated=False,
                )
            )
        return estimates

    def _parse_pois(self, payload: dict[str, object], city: str) -> list[Destination]:
        self._require_success(payload)
        declared_count = _count(payload.get("count"))
        pois = payload.get("pois")
        if not isinstance(pois, list):
            raise _bad_response()

        candidates = [candidate for poi in pois if (candidate := _parse_poi(poi, city))]
        if declared_count > 0 and not candidates:
            raise _bad_response()
        return candidates

    def _require_success(self, payload: dict[str, object]) -> None:
        status = payload.get("status")
        infocode = payload.get("infocode")
        if status is None or infocode is None:
            raise _bad_response()
        if status != "1" or infocode != "10000":
            raise ProviderError("unavailable", "高德服务暂时不可用")

    def _place_params(self, keywords: str, city: str) -> dict[str, str]:
        return {
            "key": self._api_key,
            "keywords": keywords,
            "region": city,
            "city_limit": "true",
            "show_fields": "business",
            "page_size": "25",
            "page_num": "1",
            "output": "json",
        }


def _parse_poi(raw: object, fallback_city: str) -> Destination | None:
    if not isinstance(raw, dict):
        return None
    name = _required_text(raw.get("name"))
    type_name = _required_text(raw.get("type"))
    type_code = _required_text(raw.get("typecode"))
    if name is None or type_name is None or type_code is None:
        return None
    try:
        coordinate = _parse_coordinate(raw.get("location"))
    except ProviderError:
        return None

    raw_id = raw.get("id")
    poi_id = raw_id.strip() if isinstance(raw_id, str) else ""
    if poi_id:
        provider_id = f"amap:{poi_id}"
    else:
        identity = f"{_normalize_name(name)}|{coordinate.longitude:.6f}|{coordinate.latitude:.6f}"
        provider_id = f"amap:synthetic:{sha256(identity.encode('utf-8')).hexdigest()[:16]}"
    raw_address = raw.get("address")
    address = raw_address if isinstance(raw_address, str) else ""
    raw_city = raw.get("cityname")
    city = raw_city if isinstance(raw_city, str) and raw_city else fallback_city
    business = raw.get("business")
    rating = _optional_rating(business.get("rating")) if isinstance(business, dict) else None
    return Destination(
        provider_id=provider_id,
        name=name,
        address=address,
        city=city,
        coordinate=coordinate,
        type_name=type_name,
        type_code=type_code,
        scenery_tags=classify_scenery(name, type_name, type_code, {}),
        popularity_rank=1,
        rating=rating,
    )


def _optional_coordinate(raw: object) -> Coordinate | None:
    try:
        return _parse_coordinate(raw)
    except ProviderError:
        return None


def _parse_coordinate(raw: object) -> Coordinate:
    if not isinstance(raw, str) or raw.count(",") != 1:
        raise _bad_response()
    longitude_text, latitude_text = raw.split(",")
    try:
        longitude = float(longitude_text)
        latitude = float(latitude_text)
        if not isfinite(longitude) or not isfinite(latitude):
            raise ValueError
        return Coordinate(longitude=longitude, latitude=latitude)
    except (TypeError, ValueError):
        raise _bad_response() from None


def _required_text(raw: object) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    return raw.strip()


def _count(raw: object) -> int:
    try:
        count = int(raw)
    except (TypeError, ValueError):
        raise _bad_response() from None
    if count < 0:
        raise _bad_response()
    return count


def _nonnegative_number(raw: object) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise _bad_response() from None
    if not isfinite(value) or value < 0:
        raise _bad_response()
    return value


def _optional_rating(raw: object) -> float | None:
    if isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not isfinite(value) or not 0 <= value <= 5:
        return None
    return value


def _format_coordinate(coordinate: Coordinate) -> str:
    return f"{_format_number(coordinate.longitude)},{_format_number(coordinate.latitude)}"


def _format_number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _normalize_name(value: str) -> str:
    return normalize("NFKC", value).strip()


def _haversine_km(left: Coordinate, right: Coordinate) -> float:
    earth_radius_km = 6371.0088
    left_latitude = radians(left.latitude)
    right_latitude = radians(right.latitude)
    latitude_delta = right_latitude - left_latitude
    longitude_delta = radians(right.longitude - left.longitude)
    haversine = sin(latitude_delta / 2) ** 2 + (
        cos(left_latitude) * cos(right_latitude) * sin(longitude_delta / 2) ** 2
    )
    return 2 * earth_radius_km * asin(sqrt(haversine))


def _bad_response() -> ProviderError:
    return ProviderError("bad_response", "高德返回的数据格式无效")
