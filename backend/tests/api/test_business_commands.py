"""Command execution is checked against real Mock-backed business state."""

from concurrent.futures import ThreadPoolExecutor
from itertools import count
from threading import Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_history import recommendation_payload, register

from roambot.api.routes.commands import get_business_planner
from roambot.services.assistant_limits import AssistantLimiter

BASE = "/api/v1/assistant/commands"


def test_plan_explanation_uses_authorized_snapshot_instead_of_cached_query(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "explain_plan_snapshot")
    context = history_context(client, csrf)
    created = run(client, csrf, "create_plan_from_selection", context=context)
    plan = created["plan"]
    setup(client, [{"tool": "explain_result"}])
    response = client.post(
        BASE + "/proposals",
        headers={"X-CSRF-Token": csrf},
        json={
            "request_id": str(uuid4()),
            "message": "比较这两个地点的天气",
            "context": {
                "page": "/plans/" + plan["id"],
                "plan_id": plan["id"],
                "assistant_turn": {
                    "revision": 0,
                    "message": "旧条件",
                    "draft": {"main_origin": "杭州"},
                },
            },
        },
    )
    assert response.status_code == 200
    result = execute(client, csrf, response.json()).json()
    assert result["status"] == "completed", result
    assistant = result["steps"][0]["result"]["assistant"]
    assert not assistant.get("patch")
    for candidate in plan["candidates"]:
        assert candidate["snapshot"]["destination"]["name"] in assistant["reply"]


def test_named_plan_can_be_operated_from_an_unrelated_page(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "cross_page_plan")
    context = history_context(client, csrf)
    created = run(client, csrf, "create_plan_from_selection", {"name": "湖边见"}, context)
    plan_id = created["plan"]["id"]
    visited = []

    def planner(request, context):
        visited.extend(context["plans"])
        return {"actions": [{"tool": "rotate_invite", "arguments": {"plan": "湖边见"}}]}

    client.app.dependency_overrides[get_business_planner] = lambda: planner
    proposal = client.post(
        BASE + "/proposals",
        headers={"X-CSRF-Token": csrf},
        json={
            "request_id": str(uuid4()),
            "message": "给湖边见计划生成邀请",
            "context": {"page": "/favorites"},
        },
    )
    assert proposal.status_code == 200
    assert any(p["id"] == plan_id and p["name"] == "湖边见" for p in visited)
    response = execute(client, csrf, proposal.json(), confirmed=True).json()
    assert response["status"] == "completed"
    assert response["steps"][0]["result"]["url"].startswith("/join/")
    other, _, _ = auth_api_fixture()
    other_csrf = register(other, "cross_page_other")
    result = run(other, other_csrf, "describe_capabilities", context={"page": "/"})
    assert "可以" in result["reply"]
    p = propose(other, other_csrf, [{"tool": "rotate_invite", "arguments": {"plan": plan_id}}])
    assert execute(other, other_csrf, p.json(), confirmed=True).json()["status"] == "failed"


def test_history_ordinals_follow_visible_order_and_reject_unowned_ids(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "visible_history_order")
    first = history_context(client, csrf)["history_id"]
    second = history_context(client, csrf)["history_id"]
    context = {"page": "/history", "visible_resources": {"kind": "history", "ids": [first, second]}}
    result = run(client, csrf, "open_history", {"target": 1}, context)
    assert result["history"]["id"] == first
    invalid = {"page": "/history", "visible_resources": {"kind": "history", "ids": ["not-owned"]}}
    proposed = propose(
        client, csrf, [{"tool": "delete_history", "arguments": {"target": 1}}], invalid
    )
    assert proposed.status_code == 200
    executed = execute(client, csrf, proposed.json(), confirmed=True)
    assert executed.json()["status"] == "failed"
    assert len(client.get("/api/v1/history").json()["histories"]) == 2


def setup(client, actions):
    client.app.dependency_overrides[get_business_planner] = lambda: (
        lambda request, context: {"actions": actions, "question": None}
    )


def propose(client, csrf, actions, context=None, request_id=None):
    setup(client, actions)
    return client.post(
        BASE + "/proposals",
        headers={"X-CSRF-Token": csrf},
        json={
            "request_id": request_id or str(uuid4()),
            "message": "执行当前明确要求",
            "context": context or {},
        },
    )


def execute(client, csrf, proposal, *, confirmed=False):
    return client.post(
        BASE + "/execute",
        headers={"X-CSRF-Token": csrf},
        json={
            "request_id": proposal["request_id"],
            "proposal": proposal["proposal"],
            "confirmed": confirmed,
        },
    )


def history_context(client, csrf):
    payload = {
        **recommendation_payload(),
        "max_distance_km": 500,
        "scenery_types": ["lake", "park", "museum", "old_town", "mountain", "sea"],
    }
    result = client.post(
        "/api/v1/recommendations", json=payload, headers={"X-CSRF-Token": csrf}
    ).json()
    assert len(result["items"]) >= 2
    return {
        "history_id": result["history_id"],
        "selected_ids": [i["destination"]["provider_id"] for i in result["items"][:2]],
    }


def test_create_and_invite_uses_real_selection_and_replay_never_creates_twice(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "command_owner")
    context = history_context(client, csrf)
    proposed = propose(
        client,
        csrf,
        [
            {
                "tool": "create_plan_from_selection",
                "arguments": {"name": "周末出游", "expected_count": 2},
            },
            {"tool": "rotate_invite", "arguments": {}},
        ],
        context,
    )
    assert proposed.status_code == 200
    data = proposed.json()
    assert data["requires_confirmation"] is True
    assert execute(client, csrf, data).status_code == 409
    result = execute(client, csrf, data, confirmed=True)
    assert result.status_code == 200
    assert result.json()["status"] == "completed"
    plans = client.get("/api/v1/plans").json()["plans"]
    assert len(plans) == 1
    assert plans[0]["name"] == "周末出游" and plans[0]["expected_count"] == 2
    assert any(s["result"].get("url", "").startswith("/join/") for s in result.json()["steps"])
    assert execute(client, csrf, data, confirmed=True).json() == result.json()
    assert len(client.get("/api/v1/plans").json()["plans"]) == 1


def test_favorite_binds_to_history_not_model_supplied_destination(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "favorite_command")
    context = history_context(client, csrf)
    p = propose(
        client, csrf, [{"tool": "favorite_place", "arguments": {"place": 2}}], context
    ).json()
    result = execute(client, csrf, p)
    assert result.json()["status"] == "completed"
    favorites = client.get("/api/v1/favorites").json()["favorites"]
    assert len(favorites) == 1
    assert favorites[0]["place"]["provider_place_id"] == context["selected_ids"][1]


def test_other_user_cannot_execute_proposal_or_bind_foreign_history(auth_api_fixture):
    owner, _, _ = auth_api_fixture()
    csrf = register(owner, "commands_alice")
    context = history_context(owner, csrf)
    p = propose(owner, csrf, [{"tool": "list_plans"}], context).json()
    with TestClient(owner.app) as other:
        other_csrf = register(other, "commands_bob")
        assert execute(other, other_csrf, p).status_code == 404
        foreign = propose(
            other, other_csrf, [{"tool": "favorite_place", "arguments": {"place": 1}}], context
        )
        assert foreign.status_code == 404
        assert other.get("/api/v1/favorites").json()["favorites"] == []


def test_csrf_and_request_id_conflict_checked_before_planning(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "commands_csrf")
    key = str(uuid4())
    setup(client, [{"tool": "list_plans"}])
    response = client.post(BASE + "/proposals", json={"request_id": key, "message": "查看计划"})
    assert response.status_code == 403
    first = propose(client, csrf, [{"tool": "list_plans"}], request_id=key)
    assert first.status_code == 200
    conflict = client.post(
        BASE + "/proposals",
        headers={"X-CSRF-Token": csrf},
        json={"request_id": key, "message": "删除计划"},
    )
    assert conflict.status_code == 409


def test_partial_failure_records_success_and_never_repeats_it(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "commands_partial")
    context = history_context(client, csrf)
    p = propose(
        client,
        csrf,
        [
            {"tool": "create_plan_from_selection", "arguments": {}},
            {"tool": "favorite_place", "arguments": {"place": "不存在的候选"}},
        ],
        context,
    ).json()
    result = execute(client, csrf, p).json()
    assert result["status"] == "failed"
    assert result["steps"][0]["tool"] == "create_plan_from_selection"
    assert result["steps"][0]["status"] == "completed"
    assert result["failed_step"] == 1
    assert len(client.get("/api/v1/plans").json()["plans"]) == 1
    execute(client, csrf, p)
    assert len(client.get("/api/v1/plans").json()["plans"]) == 1


def test_dirty_or_invented_selection_cannot_create_plan(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "commands_selection")
    context = history_context(client, csrf)
    for changed in ({"dirty": True}, {"selected_ids": ["fake", "also_fake"]}):
        p = propose(
            client, csrf, [{"tool": "create_plan_from_selection"}], {**context, **changed}
        ).json()
        result = execute(client, csrf, p).json()
        assert result["status"] == "failed"
    assert client.get("/api/v1/plans").json()["plans"] == []


@pytest.mark.parametrize("page", ["recommend", "explore"])
def test_anonymous_proposals_are_bound_to_their_own_cookie(auth_api_fixture, page):
    guest, _, _ = auth_api_fixture()
    setup(guest, [{"tool": "navigate", "arguments": {"page": page}}])
    p = guest.post(
        BASE + "/proposals", json={"request_id": str(uuid4()), "message": "打开推荐"}
    ).json()
    with TestClient(guest.app) as other:
        assert (
            other.post(
                BASE + "/execute", json={"request_id": p["request_id"], "proposal": p["proposal"]}
            ).status_code
            == 404
        )
    result = guest.post(
        BASE + "/execute", json={"request_id": p["request_id"], "proposal": p["proposal"]}
    ).json()
    assert result["status"] == "completed"
    assert result["steps"][0]["result"]["effect"] == {
        "tool": "navigate",
        "arguments": {"page": page},
    }


def run(client, csrf, tool, arguments=None, context=None):
    proposal = propose(client, csrf, [{"tool": tool, "arguments": arguments or {}}], context).json()
    response = execute(client, csrf, proposal, confirmed=True)
    assert response.status_code == 200, response.json()
    result = response.json()
    assert result["status"] == "completed", result
    return result["steps"][0]["result"]


def test_plan_lifecycle_uses_existing_permissions_and_state_machine(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "commands_plan_lifecycle")
    ticks = count(0, 61)
    client.app.state.assistant_limiter = AssistantLimiter(clock=lambda: next(ticks))
    context = history_context(client, csrf)
    created = run(client, csrf, "create_plan_from_selection", {"name": "初始"}, context)
    plan_id = created["plan"]["id"]
    current = {"plan_id": plan_id, "page": "/plans/" + plan_id}
    assert run(client, csrf, "list_plans")["data"]["plans"][0]["id"] == plan_id
    assert run(client, csrf, "open_plan", {"target": plan_id})["plan"]["id"] == plan_id
    changed = run(client, csrf, "update_plan", {"name": "改名", "expected_count": 3}, current)
    assert changed["plan"]["name"] == "改名" and changed["plan"]["expected_count"] == 3
    voted = run(client, csrf, "submit_vote", {"preferred": 2, "acceptable": [1, 2]}, current)
    assert voted["plan"]["summary"]["voted_count"] == 1
    checked = run(client, csrf, "check_plan_weather", context=current)
    assert all(c["latest_weather"]["status"] == "success" for c in checked["plan"]["candidates"])
    assert run(client, csrf, "close_voting", context=current)["plan"]["status"] == "closed"
    assert run(client, csrf, "decide_plan", {"place": 2}, current)["plan"]["status"] == "decided"
    assert run(client, csrf, "reopen_voting", context=current)["plan"]["status"] == "voting"
    invitation = run(client, csrf, "rotate_invite", context=current)
    assert invitation["url"].startswith("/join/")
    run(client, csrf, "revoke_invite", context=current)
    run(client, csrf, "delete_plan", context=current)
    assert client.get("/api/v1/plans").json()["plans"] == []


def test_history_share_and_favorite_lifecycle(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "commands_personal")
    context = history_context(client, csrf)
    assert run(client, csrf, "list_history")["data"]["histories"]
    assert (
        run(client, csrf, "open_history", context=context)["history"]["id"] == context["history_id"]
    )
    rerun = run(client, csrf, "rerun_history", context=context)
    assert rerun["history"]["result"]["items"]
    favorite = run(client, csrf, "favorite_place", {"place": 1}, context)["favorite"]
    assert run(client, csrf, "list_favorites")["data"]["favorites"][0]["id"] == favorite["id"]
    run(client, csrf, "remove_favorite", {"target": favorite["id"]})
    assert client.get("/api/v1/favorites").json()["favorites"] == []
    share = run(client, csrf, "create_share", context=context)["share"]
    assert client.get("/api/v1/public/shares/" + share["url"].split("/")[-1]).status_code == 200
    run(client, csrf, "revoke_share", context=context)
    assert client.get("/api/v1/public/shares/" + share["url"].split("/")[-1]).status_code == 404
    run(client, csrf, "delete_history", context=context)
    run(client, csrf, "clear_history")
    assert client.get("/api/v1/history").json()["histories"] == []


@pytest.mark.parametrize("secure_cookie", [False, True])
def test_guest_join_and_vote_with_cookie_set_in_same_batch(auth_api_fixture, secure_cookie):
    owner, _, _ = auth_api_fixture()
    csrf = register(owner, "commands_guest_owner")
    context = history_context(owner, csrf)
    created = run(owner, csrf, "create_plan_from_selection", context=context)
    current = {"plan_id": created["plan"]["id"]}
    invitation = run(owner, csrf, "rotate_invite", context=current)
    token = invitation["url"].split("/")[-1]
    owner.app.state.settings = owner.app.state.settings.model_copy(
        update={"secure_cookies": secure_cookie}
    )
    with TestClient(owner.app, base_url="https://testserver") as guest:
        proposed = propose(
            guest,
            "",
            [
                {"tool": "join_plan", "arguments": {"nickname": "同行甲"}},
                {"tool": "submit_vote", "arguments": {"preferred": 1, "acceptable": [1, 2]}},
            ],
            {"invite_token": token, "page": "/join/" + token},
        ).json()
        result = execute(guest, "", proposed).json()
        assert result["status"] == "completed", result
        assert "roambot_plan_identity" in guest.cookies
        assert result["steps"][1]["result"]["plan"]["summary"]["voted_count"] == 1
    updated = owner.get("/api/v1/plans/" + current["plan_id"]).json()["plan"]
    participant = next(p for p in updated["participants"] if p["nickname"] == "同行甲")
    run(owner, csrf, "remove_participant", {"target": participant["id"]}, current)
    remaining = owner.get("/api/v1/plans/" + current["plan_id"]).json()["plan"]["participants"]
    assert all(p["id"] != participant["id"] for p in remaining)


def test_command_proposals_keep_existing_rate_limit(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "commands_limit")
    client.app.state.assistant_limiter = AssistantLimiter(clock=lambda: 1)
    for _ in range(10):
        assert propose(client, csrf, [{"tool": "list_plans"}]).status_code == 200
    assert propose(client, csrf, [{"tool": "list_plans"}]).status_code == 429


def test_partial_vote_update_preserves_other_vote_fields(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "commands_vote_patch")
    context = history_context(client, csrf)
    created = run(client, csrf, "create_plan_from_selection", context=context)
    current = {"plan_id": created["plan"]["id"]}
    voted = run(client, csrf, "submit_vote", {"preferred": 1, "acceptable": [1, 2]}, current)
    original = voted["plan"]["me"]["acceptable_ids"]
    changed = run(client, csrf, "submit_vote", {"preferred": 2}, current)
    assert changed["plan"]["me"]["acceptable_ids"] == original


def test_concurrent_execution_claims_the_mutation_only_once(auth_api_fixture):
    from types import SimpleNamespace

    from roambot.api.routes.plans import get_plan_service
    from roambot.services.plans import PlanService

    client, _, factory = auth_api_fixture()
    csrf = register(client, "commands_concurrent")
    context = history_context(client, csrf)
    p = propose(client, csrf, [{"tool": "create_plan_from_selection"}], context).json()
    service = PlanService(factory)
    entered, release = Event(), Event()

    def create(user, body):
        entered.set()
        assert release.wait(5)
        return service.create(user, body)

    client.app.dependency_overrides[get_plan_service] = lambda: SimpleNamespace(create=create)
    with ThreadPoolExecutor(1) as pool:
        first = pool.submit(execute, client, csrf, p)
        assert entered.wait(5)
        second = execute(client, csrf, p)
        release.set()
        assert second.status_code == 409
        assert first.result().json()["status"] == "completed"
    del client.app.dependency_overrides[get_plan_service]
    assert len(client.get("/api/v1/plans").json()["plans"]) == 1


def test_unknown_write_result_is_never_replayed(auth_api_fixture):
    from types import SimpleNamespace

    from roambot.api.routes.plans import get_plan_service
    from roambot.services.plans import PlanService

    client, _, factory = auth_api_fixture()
    csrf = register(client, "commands_uncertain")
    context = history_context(client, csrf)
    p = propose(client, csrf, [{"tool": "create_plan_from_selection"}], context).json()
    service = PlanService(factory)

    def interrupted(user, body):
        service.create(user, body)
        raise RuntimeError("simulated failure after commit")

    client.app.dependency_overrides[get_plan_service] = lambda: SimpleNamespace(create=interrupted)
    assert execute(client, csrf, p).json()["status"] == "uncertain"
    assert execute(client, csrf, p).status_code == 409
    del client.app.dependency_overrides[get_plan_service]
    assert len(client.get("/api/v1/plans").json()["plans"]) == 1


def test_logout_tool_reuses_auth_api_and_ends_the_session(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "commands_logout")
    result = run(client, csrf, "logout")
    assert result["auth_changed"] is True
    assert client.get("/api/v1/auth/me").status_code == 401


def test_a_new_login_cannot_replay_the_previous_sessions_proposal(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "commands_session_scope")
    p = propose(client, csrf, [{"tool": "list_plans"}]).json()
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "commands_session_scope", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    assert execute(client, login.json()["csrf_token"], p).status_code == 404


def test_deleted_history_does_not_block_unrelated_navigation_or_new_conditions(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "commands_old_history")
    context = history_context(client, csrf)
    client.delete("/api/v1/history/" + context["history_id"], headers={"X-CSRF-Token": csrf})
    p = propose(client, csrf, [{"tool": "navigate", "arguments": {"page": "recommend"}}], context)
    assert p.status_code == 200
    assert execute(client, csrf, p.json()).json()["status"] == "completed"


def test_vote_ordinal_uses_the_visible_candidate_order_not_database_order(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "commands_visible_order")
    context = history_context(client, csrf)
    plan = run(client, csrf, "create_plan_from_selection", context=context)["plan"]
    visible = [
        {"id": c["id"], "name": c["snapshot"]["destination"]["name"]}
        for c in reversed(plan["candidates"])
    ]
    voted = run(
        client,
        csrf,
        "submit_vote",
        {"preferred": 1},
        {"plan_id": plan["id"], "visible_places": visible},
    )
    assert voted["plan"]["me"]["preferred_id"] == visible[0]["id"]
