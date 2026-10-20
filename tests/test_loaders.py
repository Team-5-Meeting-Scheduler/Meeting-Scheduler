"""Tests for scheduler.loaders. Owner: Harshitha."""

import csv
import json
from datetime import datetime
from pathlib import Path

import pytest

from scheduler.loaders import (
    load_calendars,
    load_csv_calendar,
    load_json_calendar,
)
from scheduler.models import Event


SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_calendars"

EXPECTED_COUNTS = {
    "sam": 5,
    "priya": 4,
    "alex": 5,
    "eliy": 5,
    "justin": 4,
}

FIELDS = ["person", "title", "start", "end"]


def valid_record(**overrides):
    record = {
        "person": "Sam",
        "title": "Team Meeting",
        "start": "2026-10-20T09:00:00",
        "end": "2026-10-20T10:00:00",
    }
    record.update(overrides)
    return record


def write_calendar(directory, filename, records):
    path = directory / filename
    if path.suffix == ".json":
        path.write_text(json.dumps(records), encoding="utf-8")
        return path

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)
    return path


def load_one(path):
    if path.suffix == ".json":
        return load_json_calendar(path)
    return load_csv_calendar(path)


def assert_invalid(path, *snippets):
    with pytest.raises(ValueError) as exc_info:
        load_one(path)

    message = str(exc_info.value)
    assert str(path) in message
    for snippet in snippets:
        assert snippet in message


# -----------------------------------------
# Successful loads
# -----------------------------------------

def test_loads_valid_json(tmp_path):
    path = write_calendar(tmp_path, "sam.json", [valid_record()])

    events = load_json_calendar(str(path))

    assert events == [
        Event(
            person="Sam",
            title="Team Meeting",
            start=datetime(2026, 10, 20, 9, 0),
            end=datetime(2026, 10, 20, 10, 0),
        )
    ]


def test_loads_valid_csv(tmp_path):
    path = write_calendar(tmp_path, "sam.csv", [valid_record()])

    events = load_csv_calendar(path)

    assert events == [
        Event(
            person="Sam",
            title="Team Meeting",
            start=datetime(2026, 10, 20, 9, 0),
            end=datetime(2026, 10, 20, 10, 0),
        )
    ]


def test_loads_multiple_files_for_multiple_attendees(tmp_path):
    sam = write_calendar(tmp_path, "sam.json", [valid_record()])
    priya = write_calendar(
        tmp_path,
        "priya.json",
        [valid_record(person="Priya", title="Documentation")],
    )

    events = load_calendars([sam, priya])

    assert [(event.person, event.title) for event in events] == [
        ("Sam", "Team Meeting"),
        ("Priya", "Documentation"),
    ]


def test_loads_json_and_csv_together(tmp_path):
    json_path = write_calendar(
        tmp_path, "alex.json", [valid_record(person="Alex", title="Team Sync")]
    )
    csv_path = write_calendar(
        tmp_path,
        "eliy.csv",
        [valid_record(person="Eliy", title="Code Review")],
    )

    events = load_calendars([json_path, csv_path])

    assert [(event.person, event.title) for event in events] == [
        ("Alex", "Team Sync"),
        ("Eliy", "Code Review"),
    ]


def test_empty_calendars_return_empty_lists(tmp_path):
    json_path = write_calendar(tmp_path, "empty.json", [])
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("person,title,start,end\n", encoding="utf-8")

    assert load_json_calendar(json_path) == []
    assert load_csv_calendar(csv_path) == []
    assert load_calendars([json_path, csv_path]) == []


def test_json_and_csv_events_match(tmp_path):
    records = [
        valid_record(),
        valid_record(
            person="Priya",
            title="Client Discussion",
            start="2026-10-22T10:30:00",
            end="2026-10-22T11:30:00",
        ),
    ]
    json_path = write_calendar(tmp_path, "calendar.json", records)
    csv_path = write_calendar(tmp_path, "calendar.csv", records)

    assert load_json_calendar(json_path) == load_csv_calendar(csv_path)


def test_preserves_overlapping_and_back_to_back_events(tmp_path):
    records = [
        valid_record(
            person="Priya",
            title="Client Discussion",
            start="2026-10-22T10:30:00",
            end="2026-10-22T11:30:00",
        ),
        valid_record(
            person="Priya",
            title="Team Meeting",
            start="2026-10-22T10:00:00",
            end="2026-10-22T11:00:00",
        ),
        valid_record(
            person="Sam",
            title="Planning",
            start="2026-10-21T09:00:00",
            end="2026-10-21T10:00:00",
        ),
        valid_record(
            person="Sam",
            title="Client Call",
            start="2026-10-21T10:00:00",
            end="2026-10-21T11:00:00",
        ),
    ]
    path = write_calendar(tmp_path, "calendar.json", records)

    events = load_json_calendar(path)

    assert [event.title for event in events] == [
        "Client Discussion",
        "Team Meeting",
        "Planning",
        "Client Call",
    ]
    client, team, planning, call = events
    assert team.start < client.end
    assert client.start < team.end
    assert planning.end == call.start


def test_loads_events_outside_scheduling_rules(tmp_path):
    """Working hours and 15-minute boundaries are not loader rules."""
    path = write_calendar(
        tmp_path,
        "early.json",
        [valid_record(start="2026-10-20T08:07:00", end="2026-10-20T17:30:00")],
    )

    event = load_json_calendar(path)[0]

    assert event.start == datetime(2026, 10, 20, 8, 7)
    assert event.end == datetime(2026, 10, 20, 17, 30)


# -----------------------------------------
# Invalid records
# -----------------------------------------

@pytest.mark.parametrize("filename", ["calendar.json", "calendar.csv"])
@pytest.mark.parametrize("person", ["", "   "])
def test_rejects_empty_person(tmp_path, filename, person):
    path = write_calendar(tmp_path, filename, [valid_record(person=person)])
    location = "index 0" if path.suffix == ".json" else "row 2"

    assert_invalid(path, location, "Person cannot be empty")


def test_rejects_missing_person_in_json(tmp_path):
    record = valid_record()
    del record["person"]
    path = write_calendar(tmp_path, "calendar.json", [valid_record(), record])

    assert_invalid(path, "index 1", "missing person")


@pytest.mark.parametrize("filename", ["calendar.json", "calendar.csv"])
@pytest.mark.parametrize("title", ["", "   "])
def test_rejects_empty_or_whitespace_title(tmp_path, filename, title):
    path = write_calendar(tmp_path, filename, [valid_record(title=title)])
    location = "index 0" if path.suffix == ".json" else "row 2"

    assert_invalid(path, location, "Title cannot be empty")


def test_rejects_missing_title_in_json(tmp_path):
    record = valid_record()
    del record["title"]
    path = write_calendar(tmp_path, "calendar.json", [valid_record(), record])

    assert_invalid(path, "index 1", "missing title")


@pytest.mark.parametrize("filename", ["calendar.json", "calendar.csv"])
@pytest.mark.parametrize("start", ["", "   ", "tomorrow", "2026-13-40T09:00:00"])
def test_rejects_unreadable_timestamps(tmp_path, filename, start):
    path = write_calendar(tmp_path, filename, [valid_record(start=start)])

    assert_invalid(path, "start")


@pytest.mark.parametrize("field_name", ["start", "end"])
def test_rejects_missing_timestamps_in_json(tmp_path, field_name):
    record = valid_record()
    record[field_name] = None
    path = write_calendar(tmp_path, "calendar.json", [record])

    assert_invalid(path, "index 0", f"missing {field_name}")


@pytest.mark.parametrize("filename", ["calendar.json", "calendar.csv"])
@pytest.mark.parametrize(
    "end",
    ["2026-10-20T09:00:00", "2026-10-20T08:00:00"],
)
def test_rejects_end_that_is_not_later(tmp_path, filename, end):
    path = write_calendar(tmp_path, filename, [valid_record(end=end)])

    assert_invalid(path, "later than start time")


@pytest.mark.parametrize("filename", ["calendar.json", "calendar.csv"])
def test_rejects_timezone_aware_timestamps(tmp_path, filename):
    path = write_calendar(
        tmp_path,
        filename,
        [
            valid_record(
                start="2026-10-20T09:00:00+00:00",
                end="2026-10-20T10:00:00+00:00",
            )
        ],
    )

    assert_invalid(path, "must not contain timezone information")


def test_rejects_malformed_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text('[{"person": ]', encoding="utf-8")

    assert_invalid(path, "Malformed JSON")


def test_rejects_json_that_is_not_a_list(tmp_path):
    path = tmp_path / "object.json"
    path.write_text(json.dumps(valid_record()), encoding="utf-8")

    assert_invalid(path, "must contain a list of events")


def test_rejects_json_event_that_is_not_an_object(tmp_path):
    path = tmp_path / "calendar.json"
    path.write_text(json.dumps(["not an event"]), encoding="utf-8")

    assert_invalid(path, "index 0", "expected an object")


@pytest.mark.parametrize("column", FIELDS)
def test_rejects_csv_missing_required_columns(tmp_path, column):
    path = tmp_path / "calendar.csv"
    columns = [name for name in FIELDS if name != column]
    path.write_text(",".join(columns) + "\n", encoding="utf-8")

    assert_invalid(path, "missing required columns", column)


def test_rejects_csv_without_header(tmp_path):
    path = tmp_path / "calendar.csv"
    path.write_text("", encoding="utf-8")

    assert_invalid(path, "missing a header row")


def test_rejects_csv_row_with_too_few_fields(tmp_path):
    path = tmp_path / "calendar.csv"
    path.write_text("person,title,start,end\nSam\n", encoding="utf-8")

    assert_invalid(path, "row 2", "missing title")


def test_rejects_csv_row_with_extra_values(tmp_path):
    path = tmp_path / "calendar.csv"
    path.write_text(
        "person,title,start,end\n"
        "Sam,Team Meeting,2026-10-20T09:00:00,2026-10-20T10:00:00\n"
        "Priya,Planning,2026-10-21T09:00:00,2026-10-21T10:00:00,Room A\n",
        encoding="utf-8",
    )

    assert_invalid(
        path,
        "row 3",
        "more values than the header defines",
    )


def test_reports_csv_reader_errors(tmp_path, monkeypatch):
    path = write_calendar(tmp_path, "calendar.csv", [valid_record()])

    def fail_reader(*args, **kwargs):
        raise csv.Error("line contains NUL")

    monkeypatch.setattr(csv, "DictReader", fail_reader)

    assert_invalid(path, "Invalid CSV", "line contains NUL")


# -----------------------------------------
# File errors
# -----------------------------------------

@pytest.mark.parametrize("filename", ["missing.json", "missing.csv"])
def test_missing_file(tmp_path, filename):
    path = tmp_path / filename

    with pytest.raises(FileNotFoundError) as exc_info:
        load_calendars([path])

    assert str(path) in str(exc_info.value)


@pytest.mark.parametrize("filename", ["locked.json", "locked.csv"])
def test_unreadable_file(tmp_path, monkeypatch, filename):
    path = tmp_path / filename
    path.write_text("[]", encoding="utf-8")
    real_open = Path.open

    def fail_open(self, *args, **kwargs):
        if self == path:
            raise PermissionError("permission denied")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_open)

    with pytest.raises(PermissionError) as exc_info:
        load_one(path)

    message = str(exc_info.value)
    assert str(path) in message
    assert "Could not read" in message


@pytest.mark.parametrize("filename", ["notes.txt", "calendar"])
def test_rejects_unsupported_extensions(tmp_path, filename):
    path = tmp_path / filename
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_calendars([path])

    message = str(exc_info.value)
    assert "Unsupported" in message
    assert str(path) in message


# -----------------------------------------
# Sample calendars from MEE-8
# -----------------------------------------

def test_sample_calendars_load_and_match():
    for person, count in EXPECTED_COUNTS.items():
        json_events = load_json_calendar(SAMPLE_DIR / f"{person}.json")
        csv_events = load_csv_calendar(SAMPLE_DIR / f"{person}.csv")

        assert json_events == csv_events
        assert len(json_events) == count
        assert all(isinstance(event, Event) for event in json_events)
        assert all(event.person.lower() == person for event in json_events)

    sam = load_json_calendar(SAMPLE_DIR / "sam.json")
    assert sam[0] == Event(
        person="Sam",
        title="Team Standup",
        start=datetime.fromisoformat("2026-10-20T09:00:00"),
        end=datetime.fromisoformat("2026-10-20T09:30:00"),
    )
    planning = next(event for event in sam if event.title == "Planning")
    client_call = next(event for event in sam if event.title == "Client Call")
    assert planning.end == client_call.start

    priya = load_json_calendar(SAMPLE_DIR / "priya.json")
    team = next(event for event in priya if event.title == "Team Meeting")
    client = next(event for event in priya if event.title == "Client Discussion")
    assert team.start < client.end
    assert client.start < team.end
