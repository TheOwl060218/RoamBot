"""Bounded plain-text preferences and conservative offline extraction."""

from __future__ import annotations

import re
from datetime import date, timedelta

from roambot.domain.models import SceneryType

SCENERY_QUERY_LIMIT = 120
SCENERY_KEYWORD_LIMIT = 24


def _plain(value: str, limit: int) -> str:
    if any(ord(c) < 32 for c in value) or re.search(r"https?://|[<>|]", value, re.I):
        raise ValueError("preference must be plain text")
    value = value.strip()
    if not value or len(value) > limit:
        raise ValueError("invalid preference length")
    return value


def normalize_scenery_query(value: str | None) -> str | None:
    return _plain(value, SCENERY_QUERY_LIMIT) if value is not None else None


def normalize_scenery_keywords(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    if len(values) > 4:
        raise ValueError("at most four keywords")
    return list(dict.fromkeys(_plain(value, SCENERY_KEYWORD_LIMIT) for value in values))


SCENERY_WORDS = (
    (SceneryType.LAKE, ("湖", "水边", "水库"), "湖泊"),
    (SceneryType.SEA, ("海边", "海景", "海岸", "海滩"), "海滨"),
    (SceneryType.OLD_TOWN, ("古镇", "古街", "历史街区"), "古镇"),
    (SceneryType.MUSEUM, ("博物馆", "展览", "美术馆", "室内"), "博物馆"),
    (SceneryType.PARK, ("公园", "绿地", "湿地", "散步"), "公园"),
    (SceneryType.MOUNTAIN, ("登山", "徒步", "爬山", "山景"), "山岳景区"),
)


def parse_fallback_conditions(message: str, today: date):
    # Local import keeps normalizers usable by the contract validators.
    from roambot.domain.assistant import AssistantPatch
    from roambot.domain.regions import region_catalog

    patch: dict = {}
    clauses = re.split(r"[，,。；;\n]", message)
    positive = "，".join(c for c in clauses if not re.search(r"不要|不想|避开|不去", c))
    origin = re.search(r"(?:从)?([^，,。；;\n]{1,60}?)(?:出发)", positive)
    if origin:
        patch["main_origin"] = re.sub(r"^从", "", origin.group(1)).strip()
    elif "苏州站" in positive:
        patch["main_origin"] = "苏州站"
    day = today + timedelta(days=1) if "明天" in positive else today if "今天" in positive else None
    if "这周末" in positive or "本周末" in positive:
        day = today + timedelta(days=(5 - today.weekday()) % 7 if today.weekday() < 6 else 0)
        end = min(day + timedelta(days=1 if day.weekday() == 5 else 0), today + timedelta(days=6))
        patch.update(start_date=day, end_date=end)
    elif day:
        patch.update(start_date=day, end_date=day)
    distance = re.search(r"(\d+(?:\.\d+)?)\s*(?:公里|km|千米)", positive, re.I)
    if distance and 0 < float(distance.group(1)) <= 500:
        patch["max_distance_km"] = float(distance.group(1))
    types, keywords = [], []
    for kind, words, keyword in SCENERY_WORDS:
        if any(word in positive for word in words):
            types.append(kind)
            keywords.append(keyword)
    if types:
        scenic = [
            c.strip()
            for c in clauses
            if any(word in c for _, words, _ in SCENERY_WORDS for word in words)
            or re.search(r"安静|热闹|不要|避开|不想", c)
        ]
        patch.update(
            scenery_types=types,
            scenery_query="，".join(scenic)[:120],
            scenery_keywords=keywords[:4],
        )
    regions = [
        r["adcode"]
        for r in region_catalog()["regions"]
        if r["name"] in positive and re.search(r"去|目的地|范围", positive)
    ]
    if regions:
        patch["destination_regions"] = list(dict.fromkeys(regions))[:50]
    return AssistantPatch(**patch)
