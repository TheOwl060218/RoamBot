import base64
from datetime import UTC, datetime, timedelta

import pytest

from roambot.domain.models import RecommendationResponse
from roambot.security.assistant_context import AssistantContextSigner


def test_signed_context_expiry_and_size():
    now = datetime(2026, 10, 10, tzinfo=UTC)
    clock = [now]
    signer = AssistantContextSigner(b"a" * 32, lambda: clock[0])
    result = RecommendationResponse(
        items=[], source_state={"kind": "demo"}, generated_at=now.isoformat()
    )
    token = signer.issue(result)
    assert signer.verify(token).candidates == []
    with pytest.raises(ValueError):
        signer.verify(token[:-1] + ("a" if token[-1] != "a" else "b"))
    with pytest.raises(ValueError):
        AssistantContextSigner(b"b" * 32, lambda: now).verify(token)
    with pytest.raises(ValueError):
        signer.verify("x" * 65537)
    clock[0] += timedelta(minutes=30)
    with pytest.raises(ValueError):
        signer.verify(token)
    assert b"coordinate" not in base64.urlsafe_b64decode(token.split(".")[0] + "==")
