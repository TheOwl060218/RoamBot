import logging

from roambot.security.plan_logging import PlanAccessFilter


def test_uvicorn_access_log_redacts_invitation_path_and_query():
    record = logging.LogRecord(
        "uvicorn.access",
        20,
        "",
        0,
        "%s %s %s %s %s",
        ("local", "GET", "/api/v1/public/plans/test-fixture-token?tracking=1", "1.1", 200),
        None,
    )
    assert PlanAccessFilter().filter(record)
    assert "test-fixture-token" not in record.getMessage()
    assert "tracking" not in record.getMessage()


def test_public_response_whitelist_drops_unexpected_private_fields():
    from roambot.api.plan_models import PublicDestination

    result = PublicDestination.model_validate(
        {
            "name": "湖景",
            "address": "公开地址",
            "city": "苏州",
            "scenery_tags": ["lake"],
            "rating": None,
            "coordinate": {"latitude": 31},
            "owner_user_id": "private",
        }
    ).model_dump()
    assert "coordinate" not in result and "owner_user_id" not in result
