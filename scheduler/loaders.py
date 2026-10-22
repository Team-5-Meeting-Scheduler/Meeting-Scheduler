"""Load JSON, CSV, and ICS calendars into Event objects. Owner: Harshitha."""

import csv
import json
from datetime import datetime
from pathlib import Path

from scheduler.ics import parse_ics_events
from scheduler.models import Event


REQUIRED_FIELDS = ("person", "title", "start", "end")


def load_json_calendar(path: str | Path) -> list[Event]:
    """Load a JSON list of events.

    Each object needs person, title, start, and end. Timestamp strings are
    converted to datetimes, then checked by Event. This loader does not apply
    working hours or remove overlapping meetings.
    """
    file_path = _existing_file(path)
    try:
        payload = json.loads(_read_text(file_path))
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Malformed JSON in '{file_path}': {error.msg} "
            f"(line {error.lineno}, column {error.colno})."
        ) from error

    if not isinstance(payload, list):
        raise ValueError(
            f"JSON calendar '{file_path}' must contain a list of events."
        )

    return [
        _event_from_record(record, file_path, f"index {index}")
        for index, record in enumerate(payload)
    ]


def load_csv_calendar(path: str | Path) -> list[Event]:
    """Load a CSV calendar.

    The header row must include person, title, start, and end. Each later row
    becomes one Event. A row with more values than the header defines is
    rejected. Working hours and overlaps are left as they are.
    """
    file_path = _existing_file(path)
    try:
        with file_path.open(encoding="utf-8", newline="") as file:
            try:
                reader = csv.DictReader(file)
                fieldnames = reader.fieldnames
                rows = list(reader)
            except csv.Error as error:
                raise ValueError(
                    f"Invalid CSV in '{file_path}': {error}"
                ) from error

        if not fieldnames:
            raise ValueError(
                f"CSV calendar '{file_path}' is missing a header row."
            )

        missing = [
            name for name in REQUIRED_FIELDS if name not in fieldnames
        ]
        if missing:
            columns = ", ".join(missing)
            raise ValueError(
                f"CSV calendar '{file_path}' is missing required "
                f"columns: {columns}."
            )
    except UnicodeDecodeError as error:
        raise ValueError(
            f"Could not decode calendar file '{file_path}' as UTF-8: {error}"
        ) from error
    except OSError as error:
        raise type(error)(
            f"Could not read calendar file '{file_path}': {error}"
        ) from error

    events = []
    for row_number, row in enumerate(rows, start=2):
        # DictReader stores fields past the header under the None key.
        if row.get(None):
            raise ValueError(
                f"Invalid event in '{file_path}' at row {row_number}: "
                "row contains more values than the header defines."
            )
        events.append(
            _event_from_record(row, file_path, f"row {row_number}")
        )
    return events


def load_ics_calendar(
    path: str | Path, person: str | None = None, *, local_timezone: str | None = None
) -> list[Event]:
    """Load basic ICS events for one calendar owner.

    Supply person for an exact name; otherwise use the filename stem with its
    first letter capitalized, matching the CLI's empty-calendar convention.
    Zoned ICS timestamps require the team's explicit IANA local_timezone.
    """
    file_path = _existing_file(path)
    owner = (
        person if person is not None
        else file_path.stem[:1].upper() + file_path.stem[1:]
    )
    try:
        return parse_ics_events(
            _read_text(file_path), owner, local_timezone=local_timezone
        )
    except ValueError as error:
        raise ValueError(f"Invalid ICS calendar '{file_path}': {error}") from error


def load_calendars(
    paths: list[str | Path], *, local_timezone: str | None = None
) -> list[Event]:
    """Load JSON, CSV, and ICS calendars in path order.

    ICS owners come from filenames; local_timezone applies only to ICS import.
    """
    events: list[Event] = []
    for path in paths:
        events.extend(_load_file(path, local_timezone=local_timezone))
    return events


def _load_file(path: str | Path, *, local_timezone: str | None = None) -> list[Event]:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix == ".json":
        return load_json_calendar(file_path)
    if suffix == ".csv":
        return load_csv_calendar(file_path)
    if suffix == ".ics":
        return load_ics_calendar(file_path, local_timezone=local_timezone)

    extension = suffix or "(none)"
    raise ValueError(
        f"Unsupported calendar file extension '{extension}' "
        f"for '{file_path}'. Use .json, .csv, or .ics."
    )


def _existing_file(path: str | Path) -> Path:
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Calendar file not found: '{file_path}'.")
    return file_path


def _read_text(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(
            f"Could not decode calendar file '{file_path}' as UTF-8: {error}"
        ) from error
    except OSError as error:
        raise type(error)(
            f"Could not read calendar file '{file_path}': {error}"
        ) from error


def _event_from_record(
    record: object, file_path: Path, location: str
) -> Event:
    if not isinstance(record, dict):
        raise ValueError(
            f"Invalid event in '{file_path}' at {location}: "
            "expected an object with person, title, start, and end."
        )

    missing = [
        field
        for field in REQUIRED_FIELDS
        if field not in record or record[field] is None
    ]
    if missing:
        names = ", ".join(missing)
        raise ValueError(
            f"Invalid event in '{file_path}' at {location}: missing {names}."
        )

    start = _parse_timestamp(record["start"], file_path, location, "start")
    end = _parse_timestamp(record["end"], file_path, location, "end")

    try:
        return Event(
            person=record["person"],
            title=record["title"],
            start=start,
            end=end,
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid event in '{file_path}' at {location}: {error}"
        ) from error


def _parse_timestamp(
    value: object, file_path: Path, location: str, field_name: str
) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Invalid event in '{file_path}' at {location}: "
            f"{field_name} timestamp is missing or unreadable."
        )

    try:
        return datetime.fromisoformat(value.strip())
    except ValueError as error:
        raise ValueError(
            f"Invalid event in '{file_path}' at {location}: "
            f"{field_name} timestamp '{value}' is not a valid "
            "ISO 8601 datetime."
        ) from error
