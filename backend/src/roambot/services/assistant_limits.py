from collections import deque
from collections.abc import Callable
from contextlib import contextmanager
from threading import BoundedSemaphore, Lock
from time import monotonic


class AssistantLimitError(RuntimeError):
    pass


class AssistantLimiter:
    def __init__(self, clock: Callable[[], float] = monotonic, max_keys: int = 2048):
        self._clock, self._max_keys = clock, max_keys
        self._requests: dict[str, deque[float]] = {}
        self._lock = Lock()
        self._slots = BoundedSemaphore(4)

    @contextmanager
    def acquire(self, client_key: str):
        with self._lock:
            now = self._clock()
            for key in list(self._requests):
                times = self._requests[key]
                while times and times[0] <= now - 60:
                    times.popleft()
                if not times:
                    del self._requests[key]
            if client_key not in self._requests and len(self._requests) >= self._max_keys:
                raise AssistantLimitError("Assistant busy.")
            times = self._requests.setdefault(client_key, deque())
            if len(times) >= 10 or not self._slots.acquire(blocking=False):
                raise AssistantLimitError("Assistant busy.")
            times.append(now)
        try:
            yield
        finally:
            self._slots.release()
