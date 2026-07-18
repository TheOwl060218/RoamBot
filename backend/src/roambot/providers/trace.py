from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from roambot.domain.models import SourceKind, SourceState


class ProviderEvent(StrEnum):
    CACHE = "cache"
    DEMO = "demo"
    WEATHER_EXCLUDED = "weather_excluded"
    STRAIGHT_LINE = "straight_line"
    TEMPLATE_EXPLANATION = "template_explanation"
    INSUFFICIENT_CANDIDATES = "insufficient_candidates"


_NOTICES = {
    ProviderEvent.CACHE: "使用未过期缓存结果",
    ProviderEvent.DEMO: "使用内置苏州演示数据",
    ProviderEvent.WEATHER_EXCLUDED: "部分候选因天气不可用已排除",
    ProviderEvent.STRAIGHT_LINE: "部分路程使用直线距离估算",
    ProviderEvent.TEMPLATE_EXPLANATION: "推荐理由由本地模板生成",
    ProviderEvent.INSUFFICIENT_CANDIDATES: "符合条件的候选不足 3 个",
}
_NOTICE_ORDER = tuple(_NOTICES)
_DEGRADED_EVENTS = {
    ProviderEvent.WEATHER_EXCLUDED,
    ProviderEvent.STRAIGHT_LINE,
    ProviderEvent.TEMPLATE_EXPLANATION,
}


@dataclass
class ProviderTrace:
    events: set[ProviderEvent] = field(default_factory=set)

    def mark(self, event: ProviderEvent) -> None:
        self.events.add(event)

    def to_source_state(self, final_item_count: int) -> SourceState:
        if final_item_count < 3:
            self.mark(ProviderEvent.INSUFFICIENT_CANDIDATES)
        if self.events & _DEGRADED_EVENTS:
            kind = SourceKind.DEGRADED
        elif ProviderEvent.DEMO in self.events:
            kind = SourceKind.DEMO
        elif ProviderEvent.CACHE in self.events:
            kind = SourceKind.CACHE
        else:
            kind = SourceKind.LIVE
        return SourceState(
            kind=kind,
            notices=[_NOTICES[event] for event in _NOTICE_ORDER if event in self.events],
        )
