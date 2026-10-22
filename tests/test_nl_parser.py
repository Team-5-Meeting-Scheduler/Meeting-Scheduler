"""Tests for scheduler.nl_parser. Owner: Vedanshu."""

import os
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from scheduler.nl_parser import (
    _build_client,
    _build_prompt,
    _parse_json_object,
    _response_text,
    filter_slots_by_time_preference,
    load_env,
    parse_natural_language_request,
)
from scheduler.slot_finder import TimeSlot


class FakeResponses:
    def __init__(self, text: str, *, error: Exception | None = None):
        self.text = text
        self.error = error
        self.last_model = None
        self.last_input = None

    def create(self, *, model, input):
        self.last_model = model
        self.last_input = input
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_text=self.text, output=[self.text])


class FakeClient:
    def __init__(self, text: str, *, error: Exception | None = None):
        self.responses = FakeResponses(text, error=error)


def slot(start: str, end: str) -> TimeSlot:
    day = "2026-10-23"
    return TimeSlot(
        start=datetime.fromisoformat(f"{day}T{start}"),
        end=datetime.fromisoformat(f"{day}T{end}"),
    )


def test_parse_returns_participants():
    client = FakeClient(
        '{"participants":["Sam","Priya"],"duration_minutes":30,'
        '"date":"2026-10-27","time_preference":"afternoon"}'
    )
    parsed = parse_natural_language_request(
        "30 minutes with Sam and Priya next Tuesday afternoon",
        known_participants={"Sam", "Priya", "Alex"},
        client=client,
    )
    assert parsed.participants == ["Sam", "Priya"]


def test_parse_returns_duration():
    client = FakeClient(
        '{"participants":["Sam","Priya"],"duration_minutes":30,'
        '"date":"2026-10-27","time_preference":"afternoon"}'
    )
    parsed = parse_natural_language_request(
        "30 minutes with Sam and Priya",
        known_participants={"Sam", "Priya"},
        client=client,
    )
    assert parsed.duration_minutes == 30


def test_parse_returns_meeting_date():
    client = FakeClient(
        '{"participants":["Sam","Priya"],"duration_minutes":30,'
        '"date":"2026-10-27","time_preference":"afternoon"}'
    )
    parsed = parse_natural_language_request(
        "30 minutes with Sam and Priya next Tuesday afternoon",
        known_participants={"Sam", "Priya"},
        client=client,
    )
    assert parsed.meeting_date == date(2026, 10, 27)


def test_parse_returns_afternoon_preference():
    client = FakeClient(
        '{"participants":["Sam","Priya"],"duration_minutes":30,'
        '"date":"2026-10-27","time_preference":"afternoon"}'
    )
    parsed = parse_natural_language_request(
        "30 minutes with Sam and Priya next Tuesday afternoon",
        known_participants={"Sam", "Priya"},
        client=client,
    )
    assert parsed.time_preference == "afternoon"


def test_parse_rejects_empty_request_text():
    with pytest.raises(ValueError, match="required"):
        parse_natural_language_request("  ", client=FakeClient("{}"))


def test_parse_rejects_none_request_text():
    with pytest.raises(ValueError, match="required"):
        parse_natural_language_request(None, client=FakeClient("{}"))  # type: ignore[arg-type]


def test_parse_rejects_unknown_participant():
    client = FakeClient(
        '{"participants":["Sam","Alex"],"duration_minutes":30,'
        '"date":"2026-10-23","time_preference":null}'
    )
    with pytest.raises(ValueError, match="Alex"):
        parse_natural_language_request(
            "meet Sam and Alex",
            known_participants={"Sam", "Priya"},
            client=client,
        )


def test_parse_rejects_zero_duration():
    client = FakeClient(
        '{"participants":["Sam"],"duration_minutes":0,'
        '"date":"2026-10-23","time_preference":null}'
    )
    with pytest.raises(ValueError, match="positive"):
        parse_natural_language_request("zero minutes with Sam", client=client)


def test_parse_rejects_negative_duration():
    client = FakeClient(
        '{"participants":["Sam"],"duration_minutes":-15,'
        '"date":"2026-10-23","time_preference":null}'
    )
    with pytest.raises(ValueError, match="positive"):
        parse_natural_language_request("negative duration", client=client)


def test_parse_accepts_duration_alias_key():
    client = FakeClient(
        '{"participants":["Sam"],"duration":45,'
        '"date":"2026-10-23","time_preference":null}'
    )
    parsed = parse_natural_language_request("45 minutes with Sam", client=client)
    assert parsed.duration_minutes == 45


def test_parse_rejects_invalid_date():
    client = FakeClient(
        '{"participants":["Sam"],"duration_minutes":30,'
        '"date":"10-23-2026","time_preference":null}'
    )
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        parse_natural_language_request("meet Sam", client=client)


def test_parse_rejects_missing_date():
    client = FakeClient(
        '{"participants":["Sam"],"duration_minutes":30,"time_preference":null}'
    )
    with pytest.raises(ValueError, match="date"):
        parse_natural_language_request("meet Sam", client=client)


def test_parse_rejects_invalid_time_preference():
    client = FakeClient(
        '{"participants":["Sam"],"duration_minutes":30,'
        '"date":"2026-10-23","time_preference":"evening"}'
    )
    with pytest.raises(ValueError, match="morning"):
        parse_natural_language_request("meet Sam tonight", client=client)


def test_parse_accepts_null_time_preference():
    client = FakeClient(
        '{"participants":["Sam"],"duration_minutes":30,'
        '"date":"2026-10-23","time_preference":null}'
    )
    parsed = parse_natural_language_request("30 minutes with Sam", client=client)
    assert parsed.time_preference is None


def test_parse_treats_any_time_preference_as_none():
    client = FakeClient(
        '{"participants":["Sam"],"duration_minutes":30,'
        '"date":"2026-10-23","time_preference":"any"}'
    )
    parsed = parse_natural_language_request("anytime with Sam", client=client)
    assert parsed.time_preference is None


def test_parse_deduplicates_participants():
    client = FakeClient(
        '{"participants":["Sam","Sam","Priya"],"duration_minutes":30,'
        '"date":"2026-10-23","time_preference":null}'
    )
    parsed = parse_natural_language_request(
        "Sam Sam and Priya",
        known_participants={"Sam", "Priya"},
        client=client,
    )
    assert parsed.participants == ["Sam", "Priya"]


def test_parse_rejects_empty_participant_list():
    client = FakeClient(
        '{"participants":[],"duration_minutes":30,'
        '"date":"2026-10-23","time_preference":null}'
    )
    with pytest.raises(ValueError, match="participant"):
        parse_natural_language_request("nobody", client=client)


def test_parse_rejects_blank_participant_name():
    client = FakeClient(
        '{"participants":[" "],"duration_minutes":30,'
        '"date":"2026-10-23","time_preference":null}'
    )
    with pytest.raises(ValueError, match="non-empty"):
        parse_natural_language_request("blank name", client=client)


def test_parse_extracts_json_from_fenced_markdown():
    client = FakeClient(
        '```json\n{"participants":["Priya"],"duration_minutes":15,'
        '"date":"2026-10-24","time_preference":"morning"}\n```'
    )
    parsed = parse_natural_language_request("quick chat with Priya", client=client)
    assert parsed.participants == ["Priya"]


def test_parse_extracts_duration_from_fenced_markdown():
    client = FakeClient(
        '```json\n{"participants":["Priya"],"duration_minutes":15,'
        '"date":"2026-10-24","time_preference":"morning"}\n```'
    )
    parsed = parse_natural_language_request("quick chat with Priya", client=client)
    assert parsed.duration_minutes == 15


def test_parse_rejects_non_json_response():
    with pytest.raises(ValueError, match="JSON object"):
        parse_natural_language_request("meet Sam", client=FakeClient("not json"))


def test_parse_rejects_empty_model_response():
    with pytest.raises(ValueError, match="empty"):
        parse_natural_language_request("meet Sam", client=FakeClient("   "))


def test_parse_wraps_provider_errors():
    client = FakeClient("{}", error=RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="LLM request failed"):
        parse_natural_language_request("meet Sam", client=client)


def test_filter_keeps_morning_slots_only():
    slots = [slot("09:00", "09:30"), slot("13:00", "13:30")]
    assert filter_slots_by_time_preference(slots, "morning") == [slot("09:00", "09:30")]


def test_filter_keeps_afternoon_slots_only():
    slots = [slot("09:00", "09:30"), slot("13:00", "13:30")]
    assert filter_slots_by_time_preference(slots, "afternoon") == [
        slot("13:00", "13:30")
    ]


def test_filter_with_no_preference_keeps_all_slots():
    slots = [slot("09:00", "09:30"), slot("13:00", "13:30")]
    assert filter_slots_by_time_preference(slots, None) == slots


def test_filter_rejects_unknown_preference():
    with pytest.raises(ValueError, match="morning"):
        filter_slots_by_time_preference([slot("09:00", "09:30")], "evening")


def test_prompt_includes_reference_date():
    prompt = _build_prompt("meet Sam", ["Sam"], date(2026, 10, 20))
    assert "2026-10-20" in prompt


def test_prompt_includes_known_participants():
    prompt = _build_prompt("meet Sam", ["Sam", "Priya"], date(2026, 10, 20))
    assert "Sam, Priya" in prompt


def test_parse_json_object_rejects_array_payload():
    with pytest.raises(ValueError, match="object"):
        _parse_json_object("[1, 2, 3]")


def test_response_text_uses_output_text_when_present():
    response = SimpleNamespace(output_text='{"ok":true}', output=[])
    assert _response_text(response) == '{"ok":true}'


def test_response_text_reads_nested_content_blocks():
    block = SimpleNamespace(text='{"participants":["Sam"]}')
    item = SimpleNamespace(content=[block], text=None)
    response = SimpleNamespace(output_text=None, output=[item])
    assert '{"participants":["Sam"]}' in _response_text(response)


def test_build_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_API_KEY"):
        _build_client()


def test_build_client_rejects_placeholder_key(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "<your-api-key>")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.invalid/openai/v1")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "example-model")
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_API_KEY"):
        _build_client()


def test_build_client_requires_endpoint(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "")
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_ENDPOINT"):
        _build_client()


def test_build_client_requires_deployment(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.invalid/openai/v1")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "")
    monkeypatch.setenv("OPENAI_MODEL", "")
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_DEPLOYMENT"):
        _build_client()


def test_build_client_passes_endpoint_to_openai(monkeypatch):
    created: dict[str, str] = {}

    class FakeOpenAI:
        def __init__(self, *, base_url, api_key):
            created["base_url"] = base_url
            created["api_key"] = api_key

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.invalid/openai/v1")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "example-model")
    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    _build_client()
    assert created["base_url"] == "https://example.invalid/openai/v1"


def test_build_client_passes_api_key_to_openai(monkeypatch):
    created: dict[str, str] = {}

    class FakeOpenAI:
        def __init__(self, *, base_url, api_key):
            created["base_url"] = base_url
            created["api_key"] = api_key

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.invalid/openai/v1")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "example-model")
    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    _build_client()
    assert created["api_key"] == "test-key"


def test_load_env_reads_explicit_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("AZURE_OPENAI_DEPLOYMENT=test-model\n", encoding="utf-8")
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
    load_env(env_file)
    assert os.getenv("AZURE_OPENAI_DEPLOYMENT") == "test-model"


def test_fake_client_receives_the_user_request():
    client = FakeClient(
        '{"participants":["Sam"],"duration_minutes":30,'
        '"date":"2026-10-23","time_preference":null}'
    )
    parse_natural_language_request(
        "30 minutes with Sam",
        known_participants={"Sam"},
        reference_date=date(2026, 10, 20),
        client=client,
    )
    assert "30 minutes with Sam" in client.responses.last_input


def test_suite_blocks_autoload_of_project_dotenv():
    """Autouse fixture makes load_env() without a path a no-op in tests."""
    load_env()
    assert os.getenv("AZURE_OPENAI_API_KEY") == "test-key-not-a-secret"


def test_parse_without_client_still_invokes_load_env_hook(monkeypatch):
    calls: list[object] = []

    def tracking_load_env(env_path=None):
        calls.append(env_path)

    monkeypatch.setattr("scheduler.nl_parser.load_env", tracking_load_env)
    monkeypatch.setattr(
        "scheduler.nl_parser._build_client",
        lambda: (_ for _ in ()).throw(RuntimeError("stop before network")),
    )
    with pytest.raises(RuntimeError, match="stop before network"):
        parse_natural_language_request("30 minutes with Sam")
    assert calls == [None]
