"""Shared pytest fixtures. Owner: Vedanshu."""

from __future__ import annotations

import pytest

_SECRET_ENV_VARS = (
    "AZURE_OPENAI_API_KEY",
    "OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "OPENAI_BASE_URL",
    "AZURE_OPENAI_DEPLOYMENT",
    "OPENAI_MODEL",
)


@pytest.fixture(autouse=True)
def _keep_tests_away_from_env_secrets(monkeypatch):
    """Source code may load .env normally; the test suite must not.

    - Block auto-loading the project .env file.
    - Clear any real Azure/OpenAI values inherited from the shell.
    - Install non-secret placeholders so mocked NL paths can run.
    Tests that check missing credentials override these values themselves.
    Explicit load_env(path) to a temporary file remains allowed.
    """
    from scheduler import nl_parser

    original_load_env = nl_parser.load_env

    def guarded_load_env(env_path=None):
        if env_path is None:
            return
        return original_load_env(env_path)

    monkeypatch.setattr(nl_parser, "load_env", guarded_load_env)

    for name in _SECRET_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.invalid/openai/v1")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "test-model")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key-not-a-secret")
