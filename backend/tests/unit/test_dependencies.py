from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from time import sleep
from types import SimpleNamespace

from roambot.api import dependencies
from roambot.config import Settings


def test_session_factory_initializes_once_for_concurrent_first_requests(
    monkeypatch,
    tmp_path,
) -> None:
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    settings = Settings(data_dir=tmp_path)
    start = Barrier(2)
    count_lock = Lock()
    create_count = 0

    def create_factory(_path):
        nonlocal create_count
        with count_lock:
            create_count += 1
        sleep(0.05)
        return object(), object()

    monkeypatch.setattr(dependencies, "create_engine_and_session_factory", create_factory)
    monkeypatch.setattr(dependencies, "initialize_schema", lambda _engine: None)

    def resolve_factory():
        start.wait()
        return dependencies.get_session_factory(request, settings)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: resolve_factory(), range(2)))

    assert create_count == 1
    assert results[0] is results[1]
