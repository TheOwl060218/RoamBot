"""Request-local usage receipts, safe across concurrent discovery requests."""

from contextlib import contextmanager
from contextvars import ContextVar

_recorder = ContextVar("discovery_usage_recorder", default=None)


@contextmanager
def capture_model_usage():
    receipt = {"usage": None}
    token = _recorder.set(lambda value: receipt.update(usage=value))
    try:
        yield receipt
    finally:
        _recorder.reset(token)


def record_model_usage(response, callback=None):
    recorder = callback or _recorder.get()
    if recorder:
        recorder(response.get("usage") if isinstance(response, dict) else None)
