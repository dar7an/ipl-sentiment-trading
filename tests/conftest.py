"""Keep corpus replay and mocked-client tests independent of local API keys."""

import pytest


@pytest.fixture(autouse=True)
def disable_live_api_keys(monkeypatch):
    for name in ("TYPESAFE_API_KEY", "JEV_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
