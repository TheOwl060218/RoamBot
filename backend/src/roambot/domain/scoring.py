from __future__ import annotations

from math import sqrt
from statistics import fmean, pvariance

from roambot.domain.models import (
    DailySuitability,
    DailyWeather,
    SceneryExposure,
    SceneryType,
    TravelAdviceStatus,
)

OUTDOOR = frozenset(
    {
        SceneryType.LAKE,
        SceneryType.SEA,
        SceneryType.OLD_TOWN,
        SceneryType.PARK,
        SceneryType.MOUNTAIN,
    }
)
INDOOR = frozenset({SceneryType.MUSEUM})


def _exposure(scenery_tags: frozenset[SceneryType]) -> SceneryExposure:
    has_outdoor = bool(scenery_tags & OUTDOOR)
    has_indoor = bool(scenery_tags & INDOOR)
    if has_outdoor and not has_indoor:
        return SceneryExposure.OUTDOOR
    if has_indoor and not has_outdoor:
        return SceneryExposure.INDOOR
    return SceneryExposure.MIXED


def _penalty(
    exposure: SceneryExposure,
    *,
    outdoor: int,
    mixed: int,
    indoor: int,
) -> int:
    return {
        SceneryExposure.OUTDOOR: outdoor,
        SceneryExposure.MIXED: mixed,
        SceneryExposure.INDOOR: indoor,
    }[exposure]


def _number(value: float) -> str:
    return f"{value:g}"


def _exposure_label(exposure: SceneryExposure) -> str:
    return {
        SceneryExposure.OUTDOOR: "户外场景",
        SceneryExposure.MIXED: "室内外混合场景",
        SceneryExposure.INDOOR: "室内场景",
    }[exposure]


def _advice_status(score: float) -> TravelAdviceStatus:
    if score >= 75:
        return TravelAdviceStatus.SUITABLE
    if score >= 50:
        return TravelAdviceStatus.CAUTION
    return TravelAdviceStatus.NOT_RECOMMENDED


def clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def score_daily_weather(
    weather: DailyWeather, scenery_tags: frozenset[SceneryType]
) -> DailySuitability:
    score = 100.0
    reasons: list[str] = []
    exposure = _exposure(scenery_tags)
    exposure_label = _exposure_label(exposure)

    if not scenery_tags:
        reasons.append("地点类型信息有限，天气影响按室内外混合场景估算")

    if weather.precipitation_mm > 10:
        penalty = _penalty(exposure, outdoor=60, mixed=45, indoor=35)
        score -= penalty
        reasons.append(
            f"预计降水量达到{_number(weather.precipitation_mm)}毫米，"
            f"{exposure_label}受影响明显，建议调整出行日期"
        )
    elif weather.precipitation_mm > 1:
        penalty = _penalty(exposure, outdoor=35, mixed=25, indoor=15)
        score -= penalty
        reasons.append(
            f"预计有{_number(weather.precipitation_mm)}毫米降水，"
            f"{exposure_label}需准备雨具并留意路面情况"
        )
    elif weather.precipitation_mm > 0:
        penalty = _penalty(exposure, outdoor=10, mixed=8, indoor=5)
        score -= penalty
        reasons.append(
            f"预计有少量降水，{exposure_label}建议随身携带雨具"
        )

    hottest = weather.temp_max_c
    coldest = weather.temp_min_c
    if hottest > 35 or coldest < 0:
        penalty = _penalty(exposure, outdoor=40, mixed=30, indoor=15)
        score -= penalty
        if hottest > 35:
            reasons.append(
                f"最高温度预计达到{_number(hottest)}℃，{exposure_label}，"
                "建议避开高温时段并做好防暑准备"
            )
        else:
            reasons.append(
                f"最低温度预计降至{_number(coldest)}℃，{exposure_label}，"
                "建议注意保暖并缩短室外停留"
            )
    elif hottest > 32 or coldest < 10:
        penalty = _penalty(exposure, outdoor=25, mixed=18, indoor=10)
        score -= penalty
        reasons.append(
            f"预计温度范围为{_number(coldest)}–{_number(hottest)}℃，"
            f"{exposure_label}体感可能不舒适，请合理安排时段"
        )
    elif hottest > 28 or coldest < 18:
        penalty = _penalty(exposure, outdoor=10, mixed=8, indoor=5)
        score -= penalty
        reasons.append(
            f"预计温度范围为{_number(coldest)}–{_number(hottest)}℃，"
            "建议按实际体感准备衣物"
        )

    if weather.wind_speed_kmh > 40:
        score -= _penalty(exposure, outdoor=40, mixed=30, indoor=20)
        reasons.append(
            f"预计风速达到{_number(weather.wind_speed_kmh)}公里/小时，"
            f"{exposure_label}不宜长时间停留"
        )
    elif weather.wind_speed_kmh > 30:
        score -= _penalty(exposure, outdoor=25, mixed=18, indoor=10)
        reasons.append(
            f"预计风速达到{_number(weather.wind_speed_kmh)}公里/小时，"
            f"{exposure_label}请注意防风"
        )
    elif weather.wind_speed_kmh > 20:
        score -= _penalty(exposure, outdoor=10, mixed=5, indoor=0)
        reasons.append(
            f"预计风速为{_number(weather.wind_speed_kmh)}公里/小时，"
            "户外活动可能受到一定影响"
        )

    if weather.visibility_km < 2:
        score -= 30
        reasons.append(
            f"预计能见度仅{_number(weather.visibility_km)}公里，建议谨慎出行"
        )
    elif weather.visibility_km < 5:
        score -= 15
        reasons.append(
            f"预计能见度为{_number(weather.visibility_km)}公里，请留意交通安全"
        )
    elif weather.visibility_km < 10:
        score -= 5
        reasons.append(
            f"预计能见度为{_number(weather.visibility_km)}公里，远景观赏可能受影响"
        )

    if weather.uv_index > 8:
        score -= _penalty(exposure, outdoor=10, mixed=5, indoor=0)
        reasons.append(
            f"紫外线指数预计达到{_number(weather.uv_index)}，"
            "户外停留时请做好防晒"
        )

    if not reasons:
        reasons.append(f"{exposure_label}的天气条件总体较适合出行")
    final_score = clamp(score)
    summary = f"{weather.date.month}月{weather.date.day}日" + "；".join(reasons) + "。"
    return DailySuitability(
        date=weather.date,
        score=final_score,
        reasons=reasons,
        status=_advice_status(final_score),
        summary=summary,
    )


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


def score_rating(rating: float) -> float:
    if not 0 <= rating <= 5:
        raise ValueError("rating must be between zero and five")
    return clamp(rating * 20)
