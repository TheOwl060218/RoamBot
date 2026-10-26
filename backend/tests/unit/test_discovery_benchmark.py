import importlib.util
import sqlite3
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest


def benchmark():
    path = Path(__file__).parents[3] / "scripts/benchmark_discovery_orchestration.py"
    assert path.is_file(), "comparison runner has not been implemented"
    spec = importlib.util.spec_from_file_location("discovery_benchmark", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def builder(usage=0):
    def create(message, folder):
        with closing(sqlite3.connect(folder / "facts.sqlite3")) as db, db:
            original = db.execute("SELECT value FROM fixture").fetchone()[0]
            assert original == "cold", "second implementation inherited the first's warm cache"
            db.execute("UPDATE fixture SET value='warmed'")
        return SimpleNamespace(
            run=lambda: None,
            snapshot=lambda: {
                "status": "completed",
                "cards": [],
                "first_batch_ms": None,
                "metrics": {"model_calls": 0, "search_credits": usage, "web_requests": 1},
            },
        )

    return create


def seed_at(path):
    path.mkdir()
    with closing(sqlite3.connect(path / "facts.sqlite3")) as db, db:
        db.execute("CREATE TABLE fixture(value TEXT)")
        db.execute("INSERT INTO fixture VALUES ('cold')")


def test_benchmark_compares_identical_initial_cache_without_real_calls(tmp_path):
    source = tmp_path / "seed"
    seed_at(source)
    result = benchmark().compare_pair(
        {"legacy": builder(), "coordinated": builder()},
        source,
        tmp_path / "output",
        ["controlled offline request"],
    )
    assert len(result["runs"]) == 2
    assert result["live"] is False and result["search_credits"] == 0
    with closing(sqlite3.connect(source / "facts.sqlite3")) as db, db:
        assert db.execute("SELECT value FROM fixture").fetchone()[0] == "cold"


def test_live_budget_stops_on_unknown_usage(tmp_path):
    source = tmp_path / "seed"
    seed_at(source)
    result = benchmark().compare_pair(
        {"legacy": builder(None), "coordinated": builder()},
        source,
        tmp_path / "output",
        ["controlled request"],
        live=True,
    )
    assert len(result["runs"]) == 1
    assert result["search_credits"] is None
    assert result["stopped"] == "unknown_search_usage"


def test_cache_snapshot_closes_source_and_destination_connections(tmp_path, monkeypatch):
    source = tmp_path / "seed"
    seed_at(source)
    module = benchmark()
    original_connect = sqlite3.connect
    opened = []

    def capture(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(module.sqlite3, "connect", capture)
    module.copy_cache_snapshot(source, tmp_path / "copy")
    assert len(opened) == 2
    for connection in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")
