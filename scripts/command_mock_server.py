"""Isolated browser-test server. Simulate separate minutes between planner turns."""

import os
import sys
from itertools import count
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

import uvicorn
from roambot.config import Settings
from roambot.main import create_app
from roambot.services.assistant_limits import AssistantLimiter

if __name__ == "__main__":
    app = create_app(
        Settings(provider_mode="mock", demo_mode=True, secure_cookies=False)
    )
    virtual_minutes = count(0, 61)
    app.state.assistant_limiter = AssistantLimiter(clock=lambda: next(virtual_minutes))
    uvicorn.run(
        app, host="127.0.0.1", port=int(os.environ.get("COMMAND_TEST_PORT", "8031"))
    )
