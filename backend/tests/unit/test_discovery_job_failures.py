"""Worker failures must become observable terminal states without losing valid cards."""

import pytest

from roambot.domain.discovery import DiscoveryRequest, Finish
from roambot.services.discovery import DiscoveryJobs, DiscoveryRun


def build(body, previous):
    return DiscoveryRun(
        body, None, None, None, lambda _: ("finish", Finish(reply="完成")), previous
    )


@pytest.mark.parametrize("has_cards,cancelled", [(False, False), (True, False), (False, True)])
def test_unexpected_worker_error_ends_job_and_preserves_published_cards(
    caplog, has_cards, cancelled
):
    saved = []

    def factory(body, previous):
        run = build(body, previous)
        if has_cards:
            run.cards = [{"place": {"id": "amap:verified", "name": "已核实地点"}}]
        if cancelled:
            run.cancelled.set()

        def crash():
            raise AttributeError("private request must not appear in logs")

        run.run = crash
        return run

    jobs = DiscoveryJobs()
    key = jobs.start(
        "user:one",
        DiscoveryRequest(message="散步"),
        factory,
        on_complete=lambda run: saved.append(run.cards) or "saved",
    )
    jobs.pool.shutdown(wait=True)
    result = jobs.owned("user:one", key).snapshot()
    assert result["status"] == ("cancelled" if cancelled else "partial" if has_cards else "failed")
    assert result["stage"] == "" and not result["request_location"]
    assert bool(result["cards"]) == has_cards
    assert bool(saved) == has_cards
    assert any(issue["code"] == "unexpected_error" for issue in result["issues"])
    assert "private request" not in caplog.text
    with pytest.raises(LookupError):
        jobs.owned("user:other", key)


def test_history_failure_preserves_result_and_does_not_retry_the_write(caplog):
    attempts = []

    def factory(body, previous):
        run = build(body, previous)
        run.cards = [{"place": {"id": "amap:verified", "name": "已核实地点"}}]
        return run

    def save(run):
        attempts.append(run.cards)
        raise OSError("private storage details")

    jobs = DiscoveryJobs()
    key = jobs.start("user:one", DiscoveryRequest(message="散步"), factory, on_complete=save)
    jobs.pool.shutdown(wait=True)
    result = jobs.owned("user:one", key).snapshot()
    assert result["status"] == "partial" and result["cards"]
    assert result["history_id"] is None and len(attempts) == 1
    assert {"tool": "history", "code": "save_unconfirmed"} in result["issues"]
    assert "private storage" not in caplog.text
