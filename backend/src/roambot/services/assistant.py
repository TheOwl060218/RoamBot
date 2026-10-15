import logging
from collections.abc import Callable
from datetime import date

from roambot.domain.assistant import (
    AssistantPatch,
    AssistantTurnRequest,
    AssistantTurnResponse,
    merge_assistant_patch,
    required_question,
)
from roambot.providers.assistant import AssistantFormatError, AssistantProvider
from roambot.providers.protocols import ProviderError
from roambot.security.assistant_context import AssistantContextSigner, FactCandidate
from roambot.services.assistant_interpretation import interpret_reply, next_conversation_state

logger = logging.getLogger(__name__)


def render_fact(candidate: FactCandidate, topic: str) -> str:
    name = candidate.destination.name
    if topic == "weather":
        days = [
            f"{d.date.isoformat()} {d.condition} {d.temp_min_c:g}–{d.temp_max_c:g}°C"
            for d in candidate.weather
        ]
        return f"{name}：" + "；".join(days)
    if topic == "journey":
        routes = [
            f"{d.origin_label} {d.distance_km:g}km"
            + (f"，约{d.duration_minutes:g}分钟" if d.duration_minutes is not None else "")
            + ("（估算）" if d.estimated else "")
            for d in candidate.distances
        ]
        return f"{name}：" + "；".join(routes)
    if topic == "fairness":
        group = candidate.group_accessibility
        return (
            f"{name}：平均{group.average_distance_km:g}km，最远{group.max_distance_km:g}km，"
            f"公平性{group.fairness_score:g}/100。"
        )
    if topic == "rating":
        rating = candidate.destination.rating
        return f"{name}：" + (f"高德评分{rating:g}/5。" if rating is not None else "暂无地点评分。")
    return f"{name}：出游匹配指数{candidate.score.total:g}/100；" + render_fact(
        candidate, "journey"
    )


def _clip(text: str | None, limit: int) -> str | None:
    return text[:limit] if text else text


class AssistantService:
    def __init__(
        self,
        provider: AssistantProvider,
        signer: AssistantContextSigner,
        today: Callable[[], date],
        demo: bool,
    ):
        self._provider, self._signer, self._today, self._demo = provider, signer, today, demo

    def turn(self, request: AssistantTurnRequest) -> AssistantTurnResponse:
        facts = (
            self._signer.verify(request.assistant_context) if request.assistant_context else None
        )
        candidates = {c.candidate_id: c for c in facts.candidates} if facts else {}
        if request.focused_destination_id and request.focused_destination_id not in candidates:
            raise ValueError("focused destination outside context")
        source = "demo" if self._demo else "live"

        def checked_turn(format_error: AssistantFormatError | None = None):
            repair = getattr(self._provider, "repair_turn", None)
            reply = (
                repair(request, facts, format_error)
                if format_error is not None and callable(repair)
                else self._provider.turn(request, facts)
            )
            reply = interpret_reply(reply, request.draft, self._today(), request.conversation_state)
            if reply.intent == "conditions":
                try:
                    merge_assistant_patch(
                        request.draft,
                        reply.patch,
                        self._today(),
                        validate_existing_dates=False,
                    )
                except ValueError:
                    raise ProviderError("bad_response", "Invalid assistant conditions.") from None
            elif reply.intent == "answer" and (
                reply.answer_plan is None
                or any(i not in candidates for i in reply.answer_plan.candidate_ids)
                or (
                    request.focused_destination_id
                    and reply.answer_plan.candidate_ids != [request.focused_destination_id]
                )
            ):
                raise ProviderError("bad_response", "Unverified assistant answer.")
            return reply

        try:
            model = checked_turn()
        except ProviderError as first:
            if first.code not in {"timeout", "unavailable", "bad_response", "rate_limited"}:
                raise
            try:
                model = checked_turn(first if isinstance(first, AssistantFormatError) else None)
            except ProviderError as second:
                raise second from None
        if model.intent == "answer":
            plan = model.answer_plan
            if plan is None or any(i not in candidates for i in plan.candidate_ids):
                raise ProviderError("bad_response", "Unverified assistant answer.")
            if request.focused_destination_id and plan.candidate_ids != [
                request.focused_destination_id
            ]:
                raise ProviderError("bad_response", "Unverified assistant focus.")
            reply = "\n".join(render_fact(candidates[i], plan.topic) for i in plan.candidate_ids)
            if facts and facts.source_state in {"demo", "degraded", "cache"}:
                reply = "依据当前结果（演示/缓存/降级数据，非实时保证）：\n" + reply
            return AssistantTurnResponse(
                revision=request.revision,
                reply=_clip(reply, 4000),
                source=source,
                conversation_state=request.conversation_state,
            )
        try:
            merged = merge_assistant_patch(
                request.draft,
                model.patch,
                self._today(),
                validate_existing_dates=False,
            )
        except ValueError:
            raise ProviderError("bad_response", "Invalid assistant conditions.") from None
        fields = sorted(model.patch.model_fields_set)
        logger.info(
            "assistant_reply intent=%s fields=%s start=%s end=%s",
            model.intent,
            fields,
            model.patch.start_date,
            model.patch.end_date,
        )
        question = _clip(
            model.question
            or (required_question(merged, self._today()) if model.intent == "conditions" else None),
            200,
        )
        reply = "条件已更新，可点击开始推荐。" if fields else "可以直接编辑条件，或继续补充。"
        if model.intent == "conversation":
            reply = "需要时可以继续补充想去的地方。"
        if self._demo:
            reply = "演示助手仅支持苏州站、明天、湖/公园等有限示例。" + reply
        unsupported = (model.unsupported_preferences or [])[:5]
        if model.intent == "unsupported":
            unsupported = unsupported or ["当前请求的功能"]
            reply = "这项功能尚未接入；目前可以结合天气、路程和地点信息帮你选择目的地。"
        elif unsupported:
            reply = _clip(reply + "这些偏好尚未用作筛选：" + "、".join(unsupported), 4000)
        return AssistantTurnResponse(
            revision=request.revision,
            reply=reply,
            patch=AssistantPatch.model_validate(model.patch.model_dump(exclude_unset=True)),
            confirmed_fields=fields,
            question=question,
            quick_replies=(model.quick_replies or [])[:3],
            unsupported_preferences=unsupported,
            conversation_state=next_conversation_state(request.conversation_state, model),
            source=source,
        )
