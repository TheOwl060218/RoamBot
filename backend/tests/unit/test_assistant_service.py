from contextlib import ExitStack
from datetime import UTC, date, datetime

import pytest

from roambot.domain.assistant import AssistantModelReply, AssistantTurnRequest
from roambot.providers.protocols import ProviderError
from roambot.security.assistant_context import AssistantContextSigner
from roambot.services.assistant import AssistantService
from roambot.services.assistant_limits import AssistantLimiter, AssistantLimitError


def test_explicit_unsupported_dates_get_a_question_not_an_ai_failure():
    class Provider:
        calls = 0

        def turn(self, request, facts):
            self.calls += 1
            return AssistantModelReply(
                intent="conditions",
                date_request={"start_date": "2026-10-11", "end_date": "2026-10-20"},
            )

    provider = Provider()
    response = AssistantService(
        provider,
        AssistantContextSigner(b"x", lambda: datetime.now(UTC)),
        today=lambda: date(2026, 10, 12),
        demo=False,
    ).turn(
        AssistantTurnRequest(
            message="从10月11日到10月20日", revision=0, draft={"main_origin": "苏州"}
        )
    )
    assert provider.calls == 1
    assert response.source == "live"
    assert not response.patch.model_fields_set
    assert "2026-10-12" in response.question and "2026-10-18" in response.question
    assert "2026-10-11" in response.question and "2026-10-20" in response.question


def test_native_date_intent_does_not_overwrite_existing_origin():
    class Provider:
        def turn(self, request, facts):
            return AssistantModelReply(
                intent="conditions",
                date_request={"offset_days": 1, "duration_days": 4},
            )

    response = AssistantService(
        Provider(),
        AssistantContextSigner(b"x", lambda: datetime.now(UTC)),
        today=lambda: date(2026, 10, 12),
        demo=False,
    ).turn(
        AssistantTurnRequest(message="明天出发玩四天", revision=0, draft={"main_origin": "常州"})
    )
    assert "main_origin" not in response.patch.model_fields_set
    assert "main_origin" not in response.confirmed_fields
    assert response.patch.start_date == date(2026, 10, 13)
    assert response.patch.end_date == date(2026, 10, 16)
    assert response.question


def test_model_date_intent_is_calculated_not_extracted_from_sentence():
    class Provider:
        def turn(self, request, facts):
            return AssistantModelReply(
                intent="conditions", date_request={"offset_days": 2, "duration_days": 1}
            )

    response = AssistantService(
        Provider(),
        AssistantContextSigner(b"x", lambda: datetime.now(UTC)),
        today=lambda: date(2026, 10, 12),
        demo=False,
    ).turn(AssistantTurnRequest(message="后天出发，玩一天", revision=0, draft={}))
    assert response.patch.start_date == date(2026, 10, 14)
    assert response.patch.end_date == date(2026, 10, 14)


def test_ambiguous_relative_message_does_not_inject_dates():
    class Provider:
        def turn(self, request, facts):
            return AssistantModelReply(intent="conditions", patch={"main_origin": "常州"})

    response = AssistantService(
        Provider(),
        AssistantContextSigner(b"x", lambda: datetime.now(UTC)),
        today=lambda: date(2026, 10, 12),
        demo=False,
    ).turn(AssistantTurnRequest(message="明天再说", revision=0, draft={}))
    assert response.patch.start_date is None
    assert response.question


def test_out_of_window_relative_request_does_not_inject_dates():
    class Provider:
        def turn(self, request, facts):
            return AssistantModelReply(intent="conditions", patch={"main_origin": "常州"})

    response = AssistantService(
        Provider(),
        AssistantContextSigner(b"x", lambda: datetime.now(UTC)),
        today=lambda: date(2026, 10, 12),
        demo=False,
    ).turn(AssistantTurnRequest(message="大后天出发玩五天", revision=0, draft={}))
    assert response.patch.start_date is None


def test_partial_conditions_keep_model_clarification_question():
    class Provider:
        def turn(self, request, facts):
            return AssistantModelReply(
                intent="conditions",
                patch={"max_distance_km": 80},
                question="南京是目的地还是同行出发地？",
            )

    response = AssistantService(
        Provider(),
        AssistantContextSigner(b"x", lambda: datetime.now(UTC)),
        today=lambda: date(2026, 10, 12),
        demo=False,
    ).turn(
        AssistantTurnRequest(
            message="80公里内",
            revision=0,
            draft={
                "main_origin": "常州",
                "start_date": "2026-10-13",
                "end_date": "2026-10-14",
                "scenery_types": ["lake"],
            },
        )
    )
    assert response.question == "南京是目的地还是同行出发地？"


def test_empty_patch_keeps_model_clarification_question():
    class Provider:
        def turn(self, request, facts):
            return AssistantModelReply(
                intent="conditions", patch={}, question="从苏州出发还是去苏州？"
            )

    response = AssistantService(
        Provider(),
        AssistantContextSigner(b"x", lambda: datetime.now(UTC)),
        today=lambda: date(2026, 10, 12),
        demo=False,
    ).turn(AssistantTurnRequest(message="苏州", revision=0, draft={}))
    assert response.question == "从苏州出发还是去苏州？"


def test_full_width_patch_does_not_exceed_confirmed_fields_cap():
    class Provider:
        def turn(self, request, facts):
            return AssistantModelReply(
                intent="conditions",
                patch={
                    "mode": "recommendation",
                    "main_origin": "苏州站",
                    "companion_origins": ["上海站"],
                    "start_date": "2026-10-13",
                    "end_date": "2026-10-14",
                    "max_distance_km": 80,
                    "scenery_types": ["lake"],
                    "scenery_query": "湖边",
                    "scenery_keywords": ["湖"],
                    "destination_regions": ["320500"],
                    "target_place": "拙政园",
                    "weights": {"weather": 30, "distance": 30, "popularity": 20, "fairness": 20},
                },
            )

    response = AssistantService(
        Provider(),
        AssistantContextSigner(b"x", lambda: datetime.now(UTC)),
        today=lambda: date(2026, 10, 12),
        demo=False,
    ).turn(AssistantTurnRequest(message="全部条件", revision=0, draft={}))
    assert response.source == "live"
    assert len(response.confirmed_fields) == 12


def test_unavailable_live_assistant_never_guesses_conditions_after_one_retry():
    class Provider:
        calls = 0

        def turn(self, request, facts):
            self.calls += 1
            raise ProviderError("timeout", "timeout")

    provider = Provider()
    service = AssistantService(
        provider,
        AssistantContextSigner(b"x", lambda: datetime.now(UTC)),
        today=lambda: date(2026, 10, 10),
        demo=False,
    )
    with pytest.raises(ProviderError):
        service.turn(AssistantTurnRequest(message="苏州站出发，明天去湖边", revision=0, draft={}))
    assert provider.calls == 2


def test_invalid_semantic_patch_is_retried_without_using_fallback():
    class Provider:
        calls = 0

        def turn(self, request, facts):
            self.calls += 1
            if self.calls == 1:
                return AssistantModelReply(
                    intent="conditions",
                    patch={"start_date": "2030-01-01", "end_date": "2030-01-01"},
                )
            return AssistantModelReply(intent="conditions", patch={"main_origin": "苏州站"})

    provider = Provider()
    response = AssistantService(
        provider,
        AssistantContextSigner(b"x", lambda: datetime.now(UTC)),
        today=lambda: date(2026, 10, 10),
        demo=False,
    ).turn(AssistantTurnRequest(message="苏州站出发", revision=0, draft={}))
    assert provider.calls == 2
    assert response.patch.main_origin == "苏州站"


def test_turn_updates_draft_and_only_one_question():
    class Provider:
        def turn(self, request, facts):
            assert request.draft.main_origin == "上海站"
            assert facts is None
            return AssistantModelReply(intent="conditions", patch={"main_origin": "苏州站"})

    service = AssistantService(
        Provider(),
        AssistantContextSigner(b"x", lambda: datetime.now(UTC)),
        today=lambda: date(2026, 10, 10),
        demo=True,
    )
    request = AssistantTurnRequest(message="改苏州站", revision=2, draft={"main_origin": "上海站"})
    response = service.turn(request)
    assert response.revision == 2
    assert response.patch.main_origin == "苏州站"
    assert response.question == "准备哪天出发、哪天结束？可选择未来7天。"
    assert response.source == "demo"
    assert request.draft.main_origin == "上海站"


def test_limit_release_rate_window_and_bounded_keys():
    clock = [0.0]
    limiter = AssistantLimiter(clock=lambda: clock[0], max_keys=2)
    with ExitStack() as stack:
        for i in range(4):
            stack.enter_context(limiter.acquire(str(i % 2)))
        with pytest.raises(AssistantLimitError), limiter.acquire("0"):
            pass
    for _ in range(8):
        with limiter.acquire("0"):
            pass
    with pytest.raises(AssistantLimitError), limiter.acquire("0"):
        pass
    with pytest.raises(AssistantLimitError), limiter.acquire("new"):
        pass
    clock[0] = 61
    with pytest.raises(RuntimeError), limiter.acquire("new"):
        raise RuntimeError
    with limiter.acquire("new"):
        pass
