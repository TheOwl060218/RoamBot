import time

import pytest

from roambot.domain.discovery import DiscoveryRequest, Finish
from roambot.persistence.discovery_sessions import DiscoverySessions
from roambot.services.discovery import DiscoveryJobs, DiscoveryRun


def completed(body, previous):
    run = DiscoveryRun(
        body, None, None, None, lambda _: ("finish", Finish(reply="已找到这些去处。")), previous
    )
    run.cards = [
        {
            "place": {"id": "amap:public", "name": "公园"},
            "experience": "散步",
            "reason": "",
            "sources": [],
        }
    ]
    return run


def test_guest_result_survives_memory_expiry_and_process_registry_restart(tmp_path):
    path = tmp_path / "temporary.sqlite3"
    first = DiscoveryJobs(DiscoverySessions(path))
    body = DiscoveryRequest(message="苏州找个公园")
    key = first.start("guest:one", body, completed)
    first.pool.shutdown(wait=True)
    original = first.owned("guest:one", key).snapshot()
    actor, _, run = first.jobs[key]
    first.jobs[key] = actor, time.monotonic() - 1801, run
    assert first.owned(actor, key).snapshot()["cards"] == original["cards"]
    second = DiscoveryJobs(DiscoverySessions(path))
    try:
        restored = second.owned(actor, key)
        assert restored.snapshot()["conversation"] == original["conversation"]
        assert restored.body.message == body.message
        with pytest.raises(LookupError):
            second.owned("guest:other", key)
        second.adopt_guest(actor, "user:one:session")
        assert second.owned("user:one:session", key).snapshot()["cards"] == original["cards"]
        with pytest.raises(LookupError):
            second.owned(actor, key)
        with pytest.raises(LookupError):
            second.owned("user:one:other-session", key)
    finally:
        second.close()


def test_24_hours_is_a_fixed_deadline_and_expired_rows_are_cleaned(tmp_path):
    now = [1000.0]
    store = DiscoverySessions(tmp_path / "temporary.sqlite3", clock=lambda: now[0])
    run = completed(DiscoveryRequest(message="散步"), None)
    run.run()
    store.save("owned", "guest:one", run.body.model_dump(mode="json"), run.snapshot())
    now[0] += 80000
    store.save("owned", "guest:one", run.body.model_dump(mode="json"), run.snapshot())
    jobs = DiscoveryJobs(store)
    try:
        assert jobs.owned("guest:one", "owned").cards
        now[0] = 87400
        with pytest.raises(LookupError):
            jobs.owned("guest:one", "owned")
        with store.connect() as db:
            assert db.execute("SELECT count(*) FROM results").fetchone()[0] == 0
    finally:
        jobs.close()


def test_adoption_after_restart_revokes_the_old_browser_identity(tmp_path):
    store = DiscoverySessions(tmp_path / "temporary.sqlite3")
    run = completed(DiscoveryRequest(message="散步"), None)
    run.run()
    store.save("owned", "guest:one", run.body.model_dump(mode="json"), run.snapshot())
    jobs = DiscoveryJobs(store)
    try:
        jobs.adopt_guest("guest:one", "user:one:session")
        assert jobs.owned("user:one:session", "owned").cards
        with pytest.raises(LookupError):
            jobs.owned("guest:one", "owned")
    finally:
        jobs.close()
