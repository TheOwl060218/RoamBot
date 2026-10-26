from types import SimpleNamespace

from test_business_commands import execute, history_context, propose, register

from roambot.api.dependencies import get_assistant_service
from roambot.domain.assistant import AssistantTurnResponse


def test_unresolved_condition_stops_creation_with_an_old_selection(
    auth_api_fixture,
):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "commands_clarify")
    context = history_context(client, csrf)
    context["assistant_turn"] = {"message": "当前条件", "revision": 0, "draft": {}}
    client.app.dependency_overrides[get_assistant_service] = lambda: SimpleNamespace(
        turn=lambda request: AssistantTurnResponse(
            revision=request.revision,
            reply="请明确这个地点的用途。",
            question="这是主出发地还是目的地？",
            source="demo",
        )
    )
    proposal = propose(
        client,
        csrf,
        [{"tool": "update_search_conditions"}, {"tool": "create_plan_from_selection"}],
        context,
    ).json()
    response = execute(client, csrf, proposal).json()
    assert response["status"] == "awaiting_input"
    assert response["question"] == "这是主出发地还是目的地？"
    assert [s["tool"] for s in response["steps"]] == ["update_search_conditions"]
    assert client.get("/api/v1/plans").json()["plans"] == []
