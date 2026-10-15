from datetime import timedelta

from roambot.domain.models import DailyWeather, SceneryType


def interval_reminders(weather: list[DailyWeather], tags: frozenset[SceneryType]) -> list[str]:
    """Attach each sustained impact once, at its first date; never change scores."""
    notes: list[list[str]] = [[] for _ in weather]
    new_temperature_events: set[int] = set()
    indoor = tags == frozenset({SceneryType.MUSEUM})
    distant = bool(tags & {SceneryType.LAKE, SceneryType.SEA, SceneryType.MOUNTAIN})

    def events(day: DailyWeather) -> dict[str, str]:
        result = {}
        if day.precipitation_mm > 1:
            result["rain"] = "heavy" if day.precipitation_mm > 10 else "rain"
        elif day.precipitation_mm > 0 or "雨" in day.condition:
            result["rain"] = "light"
        if day.wind_speed_kmh > 20:
            result["wind"] = (
                "severe"
                if day.wind_speed_kmh > 40
                else "strong"
                if day.wind_speed_kmh > 30
                else "wind"
            )
        if day.temp_max_c > 32:
            result["heat"] = "heat"
        if day.temp_min_c < 10:
            result["cold"] = "freezing" if day.temp_min_c < 0 else "cold"
        if distant and day.visibility_km < 10:
            result["visibility"] = "limited"
        if not indoor and day.uv_index > 8:
            result["uv"] = "high"
        return result

    states = [events(day) for day in weather]
    for i, day in enumerate(weather):
        previous = (
            states[i - 1] if i and day.date - weather[i - 1].date == timedelta(days=1) else {}
        )
        for kind, severity in states[i].items():
            if previous.get(kind) == severity:
                continue
            end = i
            while (
                end + 1 < len(weather)
                and states[end + 1].get(kind) == severity
                and weather[end + 1].date - weather[end].date == timedelta(days=1)
            ):
                end += 1
            label = f"{day.date.month}月{day.date.day}日"
            if end > i:
                label += f"–{weather[end].date.month}月{weather[end].date.day}日"
            if kind == "rain":
                change = (
                    "降水增强"
                    if previous.get(kind) == "rain" and severity == "heavy"
                    else "降水减弱"
                    if previous.get(kind) == "heavy"
                    else "预计有降水"
                )
                impact = "往返途中备好雨具" if indoor else "户外游览需备雨具，留意湿滑路面"
                if severity == "heavy":
                    impact = (
                        "往返途中降水较多，考虑调整日期" if indoor else "降水较多，优先考虑其他日期"
                    )
                text = f"{change}，{impact}"
                if severity == "light":
                    text = (
                        "预报含降雨，往返途中携带雨具"
                        if indoor
                        else "预报含降雨，随身携带雨具并留意湿滑路面"
                    )
            elif kind == "wind":
                setting = (
                    "海边"
                    if SceneryType.SEA in tags
                    else "湖边"
                    if SceneryType.LAKE in tags
                    else "山地"
                    if SceneryType.MOUNTAIN in tags
                    else "户外"
                )
                text = (
                    "风速较高，往返途中注意防风" if indoor else f"风速较高，{setting}停留注意防风"
                )
                if severity in {"strong", "severe"}:
                    text += "，避免长时间暴露"
                if severity == "severe":
                    text = (
                        "风速进一步增强，考虑减少室外活动"
                        if previous.get(kind)
                        else "风速很高，考虑减少室外活动"
                    )
            elif kind == "heat":
                new_temperature_events.add(i)
                text = "高温，往返途中注意防暑" if indoor else "高温，缩短室外停留并注意补水防晒"
            elif kind == "cold":
                new_temperature_events.add(i)
                text = "气温偏低，准备保暖衣物" if severity == "cold" else "最低温低于0℃，注意保暖"
            elif kind == "visibility":
                text = "能见度偏低，远景观赏可能受影响"
            else:
                text = "紫外线较强，室外活动做好防晒"
            notes[i].append(f"{label}：{text}。")
        if previous.get("rain") and "rain" not in states[i]:
            notes[i].append("降水较前一天减弱，可重新考虑户外安排；仍需留意湿滑路面。")

    # Compare with the last announced baseline to catch gradual changes too.
    if weather:
        baseline = weather[0]
        for i, day in enumerate(weather[1:], 1):
            low = day.temp_min_c - baseline.temp_min_c
            high = day.temp_max_c - baseline.temp_max_c
            if abs(low) < 5 and abs(high) < 5:
                continue
            delta = high if abs(high) >= abs(low) else low
            metric = "最高温" if abs(high) >= abs(low) else "最低温"
            if i not in new_temperature_events:
                impact = "增添衣物，注意早晚保暖" if delta < 0 else "调整衣物，户外活动注意补水"
                trend = "降温" if delta < 0 else "升温"
                notes[i].append(
                    f"较{baseline.date.month}月{baseline.date.day}日{trend}，{metric}变化约{abs(delta):g}℃；{impact}。"
                )
            baseline = day
    return ["".join(day_notes) for day_notes in notes]
