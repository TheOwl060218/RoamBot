import pytest
from pydantic import ValidationError

from roambot.config import Settings
from roambot.main import create_app


def test_source_workflow_environment_reaches_app(monkeypatch):
    monkeypatch.setenv("ROAMBOT_DISCOVERY_ORCHESTRATION_MODE", "source")
    settings = Settings()
    assert settings.discovery_orchestration_mode == "source"
    app = create_app(settings)
    assert app.state.discovery_orchestration_mode == "source"


def test_workflow_default_preserves_legacy():
    assert Settings().discovery_orchestration_mode == "legacy"


def test_invalid_workflow_is_rejected(monkeypatch):
    monkeypatch.setenv("ROAMBOT_DISCOVERY_ORCHESTRATION_MODE", "typo")
    with pytest.raises(ValidationError):
        Settings()
