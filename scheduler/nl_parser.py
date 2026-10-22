"""Parse natural-language scheduling requests with an LLM. Owner: Vedanshu.

The model only converts text into structured fields. Conflict detection and
slot search stay in the existing Python scheduling engine. Core CLI use does
not require this module or an API key.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date, time
from pathlib import Path

from scheduler.slot_finder import TimeSlot

TIME_PREFERENCES = frozenset({"morning", "afternoon"})
MORNING_END = time(12, 0)


@dataclass(frozen=True)
class ParsedSchedulingRequest:
    """Structured scheduling inputs produced from natural language."""

    participants: list[str]
    duration_minutes: int
    meeting_date: date
    time_preference: str | None = None


def load_env(env_path: str | Path | None = None) -> None:
    """Load environment variables from a .env file when python-dotenv is installed.

    Permission errors are ignored so blocked secret files (for example under
    .cursorignore) do not break typed CLI use or mocked tests.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    try:
        if env_path is not None:
            load_dotenv(env_path, override=False)
            return

        cwd_env = Path.cwd() / ".env"
        package_env = Path(__file__).resolve().parents[1] / ".env"
        if cwd_env.is_file():
            load_dotenv(cwd_env, override=False)
        elif package_env.is_file():
            load_dotenv(package_env, override=False)
    except OSError:
        return


def parse_natural_language_request(
    request_text: str,
    *,
    known_participants: set[str] | None = None,
    reference_date: date | None = None,
    client=None,
) -> ParsedSchedulingRequest:
    """Convert a natural-language request into validated scheduling parameters.

    Raises ValueError when the text is empty, the model response is unusable,
    or the structured fields fail validation. Raises RuntimeError when the
    OpenAI client or API credentials are missing.
    """
    text = request_text.strip() if isinstance(request_text, str) else ""
    if not text:
        raise ValueError("Natural-language request text is required.")

    load_env()
    today = reference_date or date.today()
    known = sorted(known_participants or [])
    raw = _ask_model(
        text,
        known_participants=known,
        reference_date=today,
        client=client,
    )
    payload = _parse_json_object(raw)
    parsed = _validated_request(payload)
    if known_participants is not None:
        missing = [name for name in parsed.participants if name not in known_participants]
        if missing:
            raise ValueError(
                "No calendar found for participant " + ", ".join(missing) + "."
            )
    return parsed


def filter_slots_by_time_preference(
    slots: list[TimeSlot], time_preference: str | None
) -> list[TimeSlot]:
    """Keep slots that fall in morning (< 12:00) or afternoon (>= 12:00)."""
    if time_preference is None:
        return list(slots)
    preference = time_preference.strip().lower()
    if preference not in TIME_PREFERENCES:
        raise ValueError("Time preference must be 'morning' or 'afternoon'.")
    if preference == "morning":
        return [slot for slot in slots if slot.start.time() < MORNING_END]
    return [slot for slot in slots if slot.start.time() >= MORNING_END]


def _ask_model(
    request_text: str,
    *,
    known_participants: list[str],
    reference_date: date,
    client,
) -> str:
    openai_client = client or _build_client()
    prompt = _build_prompt(request_text, known_participants, reference_date)
    try:
        response = openai_client.responses.create(
            model=_deployment_name(),
            input=prompt,
        )
    except Exception as error:  # noqa: BLE001 - surface provider errors clearly
        raise RuntimeError(f"LLM request failed: {error}") from error
    text = _response_text(response)
    if not text.strip():
        raise ValueError("LLM returned an empty response.")
    return text


def _build_client():
    api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key or not api_key.strip() or api_key.strip() == "<your-api-key>":
        raise RuntimeError(
            "Natural-language mode requires AZURE_OPENAI_API_KEY in the environment "
            "or a local .env file. Typed CLI flags work without an API key."
        )
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("OPENAI_BASE_URL")
    if not endpoint or not endpoint.strip():
        raise RuntimeError(
            "Natural-language mode requires AZURE_OPENAI_ENDPOINT in the environment "
            "or a local .env file."
        )
    _deployment_name()

    try:
        from openai import OpenAI
    except ImportError as error:
        raise RuntimeError(
            "The openai package is required for --request. "
            "Install with: pip install -e \".[nl]\""
        ) from error

    return OpenAI(base_url=endpoint.strip().rstrip("/"), api_key=api_key.strip())


def _deployment_name() -> str:
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT") or os.getenv("OPENAI_MODEL")
    if not deployment or not deployment.strip():
        raise RuntimeError(
            "Natural-language mode requires AZURE_OPENAI_DEPLOYMENT in the environment "
            "or a local .env file."
        )
    return deployment.strip()


def _build_prompt(
    request_text: str, known_participants: list[str], reference_date: date
) -> str:
    people = ", ".join(known_participants) if known_participants else "(none provided)"
    return (
        "Convert the office manager's scheduling request into JSON only.\n"
        "Do not explain. Do not use markdown. Return one JSON object with keys:\n"
        '  participants: array of strings\n'
        "  duration_minutes: positive integer\n"
        '  date: YYYY-MM-DD\n'
        '  time_preference: "morning", "afternoon", or null\n'
        f"Reference date (today): {reference_date.isoformat()}\n"
        f"Known participants: {people}\n"
        "Match participant names to the known list when possible.\n"
        "Resolve relative dates such as next Tuesday from the reference date.\n"
        "Morning means before 12:00. Afternoon means 12:00 or later.\n"
        f"Request: {request_text}\n"
    )


def _response_text(response) -> str:
    direct = getattr(response, "output_text", None)
    if isinstance(direct, str) and direct.strip():
        return direct

    parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        content = getattr(item, "content", None)
        if isinstance(content, str) and content.strip():
            parts.append(content)
            continue
        for block in content or []:
            text = getattr(block, "text", None)
            if isinstance(text, str) and text.strip():
                parts.append(text)
            elif isinstance(block, dict):
                value = block.get("text")
                if isinstance(value, str) and value.strip():
                    parts.append(value)
        text = getattr(item, "text", None)
        if isinstance(text, str) and text.strip():
            parts.append(text)
    if parts:
        return "\n".join(parts)
    return str(response.output[0]) if getattr(response, "output", None) else ""


def _parse_json_object(raw: str) -> dict:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("LLM response did not contain a JSON object.")
        text = text[start : end + 1]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"LLM response was not valid JSON: {error.msg}.") from error
    if not isinstance(payload, dict):
        raise ValueError("LLM response JSON must be an object.")
    return payload


def _validated_request(payload: dict) -> ParsedSchedulingRequest:
    participants = payload.get("participants")
    if not isinstance(participants, list) or not participants:
        raise ValueError("Parsed request must include at least one participant.")
    if any(not isinstance(name, str) or not name.strip() for name in participants):
        raise ValueError("Participant names must be non-empty strings.")
    cleaned_participants = list(dict.fromkeys(name.strip() for name in participants))

    duration = payload.get("duration_minutes", payload.get("duration"))
    if isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0:
        raise ValueError("Parsed meeting duration must be a positive number of minutes.")

    raw_date = payload.get("date")
    if not isinstance(raw_date, str) or not raw_date.strip():
        raise ValueError("Parsed request must include a date as YYYY-MM-DD.")
    try:
        meeting_date = date.fromisoformat(raw_date.strip())
    except ValueError as error:
        raise ValueError("Parsed date must use YYYY-MM-DD.") from error

    preference = payload.get("time_preference")
    if preference is not None:
        if not isinstance(preference, str):
            raise ValueError("Time preference must be 'morning', 'afternoon', or null.")
        preference = preference.strip().lower()
        if preference in {"", "null", "none", "any"}:
            preference = None
        elif preference not in TIME_PREFERENCES:
            raise ValueError("Time preference must be 'morning' or 'afternoon'.")

    return ParsedSchedulingRequest(
        participants=cleaned_participants,
        duration_minutes=duration,
        meeting_date=meeting_date,
        time_preference=preference,
    )
