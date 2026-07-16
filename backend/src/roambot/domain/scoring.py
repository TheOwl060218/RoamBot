from __future__ import annotations

from math import sqrt
from statistics import fmean, pvariance

from roambot.domain.models import DailySuitability, DailyWeather, SceneryType

OUTDOOR = frozenset(
    {
        SceneryType.LAKE,
        SceneryType.SEA,
        SceneryType.OLD_TOWN,
        SceneryType.PARK,
        SceneryType.MOUNTAIN,
    }
)


def clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def score_daily_weather(
    weather: DailyWeather, scenery_tags: frozenset[SceneryType]
) -> DailySuitability:
    score = 100.0
    reasons: list[str] = []
    outdoor = not scenery_tags or bool(scenery_tags & OUTDOOR)

    if not scenery_tags:
        reasons.append("风景类型未知")

    if weather.precipitation_mm > 10:
        penalty = 60 if outdoor else 35
        score -= penalty
        reasons.append(f"强降水 -{penalty}")
    elif weather.precipitation_mm > 1:
        penalty = 35 if outdoor else 15
        score -= penalty
        reasons.append(f"降雨 -{penalty}")
    elif weather.precipitation_mm > 0:
        penalty = 10 if outdoor else 5
        score -= penalty
        reasons.append(f"微量降水 -{penalty}")

    hottest = weather.temp_max_c
    coldest = weather.temp_min_c
    if hottest > 35 or coldest < 0:
        score -= 40
        reasons.append("极端温度 -40")
    elif hottest > 32 or coldest < 10:
        score -= 25
        reasons.append("温度不舒适 -25")
    elif hottest > 28 or coldest < 18:
        score -= 10
        reasons.append("温度稍有偏离 -10")

    if weather.wind_speed_kmh > 40:
        score -= 40 if outdoor else 20
        reasons.append("大风")
    elif weather.wind_speed_kmh > 30:
        score -= 25 if outdoor else 10
        reasons.append("风力较强")
    elif weather.wind_speed_kmh > 20 and outdoor:
        score -= 10
        reasons.append("户外风力影响")

    if weather.visibility_km < 2:
        score -= 30
        reasons.append("能见度很低")
    elif weather.visibility_km < 5:
        score -= 15
        reasons.append("能见度较低")
    elif weather.visibility_km < 10:
        score -= 5
        reasons.append("能见度一般")

    if weather.uv_index > 8 and outdoor:
        score -= 10
        reasons.append("紫外线强")

    if not reasons:
        reasons.append("天气条件总体舒适")
    return DailySuitability(date=weather.date, score=clamp(score), reasons=reasons)


def aggregate_weather(scores: list[float]) -> float:
    if not scores:
        raise ValueError("daily weather scores must not be empty")
    return clamp(fmean(scores) * 0.70 + min(scores) * 0.30)


def score_distance(distance_km: float, max_distance_km: float) -> float:
    if max_distance_km <= 0:
        raise ValueError("max distance must be positive")
    return clamp(100 * (1 - distance_km / max_distance_km))


def score_fairness(distances_km: list[float], max_distance_km: float) -> float:
    if not distances_km:
        raise ValueError("distances must not be empty")
    if len(distances_km) == 1:
        return clamp(100.0)
    stddev = sqrt(pvariance(distances_km))
    return clamp(100 * (1 - stddev / max_distance_km))


def score_popularity(rank: int, local_bonus: float = 0) -> float:
    if rank < 1:
        raise ValueError("invalid popularity rank")
    if not -20 <= local_bonus <= 20:
        raise ValueError("popularity bonus must be between -20 and 20")
    return clamp(100 - 4 * (rank - 1) + local_bonus)
