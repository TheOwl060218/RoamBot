"""Business tool contracts; no provider calls."""

import pytest
from pydantic import ValidationError

from roambot.domain.business_tools import TOOL_CATALOG, Action, CommandRequest, resolve_reference


def test_tool_catalog_covers_existing_user_businesses():
    required = {
        "update_search_conditions",
        "run_recommendation",
        "favorite_place",
        "remove_favorite",
        "list_favorites",
        "list_history",
        "open_history",
        "rerun_history",
        "delete_history",
        "clear_history",
        "create_share",
        "revoke_share",
        "list_plans",
        "open_plan",
        "create_plan_from_selection",
        "update_plan",
        "delete_plan",
        "remove_participant",
        "rotate_invite",
        "revoke_invite",
        "submit_vote",
        "close_voting",
        "decide_plan",
        "reopen_voting",
        "check_plan_weather",
        "join_plan",
        "navigate",
        "open_detail",
        "open_map",
        "close_layer",
        "select_candidates",
        "show_comparison",
        "edit_condition",
        "start_new_query",
        "undo_new_query",
        "clear_conversation",
        "open_account",
        "logout",
        "copy_link",
        "open_external_map",
    }
    assert required <= TOOL_CATALOG.keys()
    for name, spec in TOOL_CATALOG.items():
        assert spec.name == name
        assert spec.description
        assert spec.parameters.model_json_schema()["additionalProperties"] is False


@pytest.mark.parametrize(
    "bad",
    [
        {"tool": "fetch_url", "arguments": {"url": "https://example.com"}},
        {"tool": "open_detail", "arguments": {"place": 0}},
        {"tool": "create_plan_from_selection", "arguments": {"user_id": "other"}},
        {"tool": "create_plan_from_selection", "arguments": {"expected_count": 0}},
        {"tool": "navigate", "arguments": {"page": "https://example.com"}},
    ],
)
def test_tool_calls_reject_unknown_authority_and_invalid_parameters(bad):
    with pytest.raises((ValidationError, ValueError)):
        Action.model_validate(bad).validated_arguments()


def test_reference_never_guesses_ambiguous_name_or_unseen_id():
    objects = [{"id": "one", "name": "公园"}, {"id": "two", "name": "公园"}]
    assert resolve_reference("第二个", objects)["id"] == "two"
    assert resolve_reference("one", objects)["id"] == "one"
    with pytest.raises(ValueError):
        resolve_reference("公园", objects)
    with pytest.raises(ValueError):
        resolve_reference("invented", objects)
    with pytest.raises(ValueError):
        resolve_reference(None, objects)


def test_command_bounds_model_context_and_does_not_accept_an_identity():
    with pytest.raises(ValidationError):
        CommandRequest.model_validate({"message": "收藏", "request_id": "x", "user_id": "other"})
