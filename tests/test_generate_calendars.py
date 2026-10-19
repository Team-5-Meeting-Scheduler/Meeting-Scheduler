import csv
import json
import sys
from datetime import datetime, time
from pathlib import Path

import pytest


# Allow tests to import scripts from the project.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import generate_json_calendars as json_generator
import generate_csv_calendars as csv_generator


PEOPLE = {"sam", "priya", "alex", "eliy", "justin"}

EXPECTED_COUNTS = {
    "sam": 5,
    "priya": 4,
    "alex": 5,
    "eliy": 5,
    "justin": 4,
}


@pytest.fixture
def generated_files(tmp_path, monkeypatch):
    """
    Generate JSON and CSV files in a temporary directory.
    The real data/sample_calendars folder is not changed.
    """
    monkeypatch.setattr(json_generator, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(csv_generator, "OUTPUT_DIR", tmp_path)

    json_generator.generate_json_calendars()
    csv_generator.generate_csv_calendars()

    return tmp_path


def read_json(directory, person):
    path = directory / f"{person}.json"

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def read_csv(directory, person):
    path = directory / f"{person}.csv"

    with open(path, "r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def test_five_json_files_created(generated_files):
    """Each person must have a separate JSON calendar."""
    files = {
        path.stem
        for path in generated_files.glob("*.json")
    }

    assert files == PEOPLE


def test_five_csv_files_created(generated_files):
    """Each person must have a separate CSV calendar."""
    files = {
        path.stem
        for path in generated_files.glob("*.csv")
    }

    assert files == PEOPLE


def test_expected_event_counts(generated_files):
    """Check the number of events for each person."""
    for person, count in EXPECTED_COUNTS.items():
        assert len(read_json(generated_files, person)) == count
        assert len(read_csv(generated_files, person)) == count


def test_json_and_csv_contain_same_events(generated_files):
    """Both formats should contain identical calendar data."""
    for person in PEOPLE:
        json_events = read_json(generated_files, person)
        csv_events = read_csv(generated_files, person)

        assert json_events == csv_events


def test_required_event_fields(generated_files):
    """Every event must have the four required fields."""
    required_fields = {"person", "title", "start", "end"}

    for person in PEOPLE:
        for event in read_json(generated_files, person):
            assert set(event.keys()) == required_fields


def test_correct_person_in_each_file(generated_files):
    """A person's calendar must contain only their events."""
    for person in PEOPLE:
        for event in read_json(generated_files, person):
            assert event["person"].lower() == person


def test_valid_datetime_and_duration(generated_files):
    """All events must have valid timestamps and positive duration."""
    for person in PEOPLE:
        for event in read_json(generated_files, person):
            start = datetime.fromisoformat(event["start"])
            end = datetime.fromisoformat(event["end"])

            assert start < end
            assert start.tzinfo is None
            assert end.tzinfo is None


def test_events_within_working_hours(generated_files):
    """Sample meetings should stay between 09:00 and 17:00."""
    work_start = time(9, 0)
    work_end = time(17, 0)

    for person in PEOPLE:
        for event in read_json(generated_files, person):
            start = datetime.fromisoformat(event["start"])
            end = datetime.fromisoformat(event["end"])

            assert work_start <= start.time()
            assert end.time() <= work_end
            assert start.date() == end.date()


def test_events_sorted_by_start_time(generated_files):
    """Events should be stored in chronological order."""
    for person in PEOPLE:
        events = read_json(generated_files, person)
        starts = [event["start"] for event in events]

        assert starts == sorted(starts)


def test_back_to_back_meetings(generated_files):
    """Sam's two meetings touch without overlapping."""
    events = read_json(generated_files, "sam")

    planning = next(
        event for event in events
        if event["title"] == "Planning"
    )
    client_call = next(
        event for event in events
        if event["title"] == "Client Call"
    )

    assert planning["end"] == client_call["start"]


def test_double_booking(generated_files):
    """Priya has two intentionally overlapping meetings."""
    events = read_json(generated_files, "priya")

    team_meeting = next(
        event for event in events
        if event["title"] == "Team Meeting"
    )
    client_discussion = next(
        event for event in events
        if event["title"] == "Client Discussion"
    )

    first_start = datetime.fromisoformat(team_meeting["start"])
    first_end = datetime.fromisoformat(team_meeting["end"])
    second_start = datetime.fromisoformat(client_discussion["start"])
    second_end = datetime.fromisoformat(client_discussion["end"])

    assert first_start < second_end
    assert second_start < first_end


def test_nearly_full_day(generated_files):
    """Alex has only 30 minutes free during the working day."""
    events = [
        event
        for event in read_json(generated_files, "alex")
        if event["start"].startswith("2026-10-23")
    ]

    total_busy_minutes = sum(
        int(
            (
                datetime.fromisoformat(event["end"])
                - datetime.fromisoformat(event["start"])
            ).total_seconds() / 60
        )
        for event in events
    )

    working_day_minutes = 8 * 60
    free_minutes = working_day_minutes - total_busy_minutes

    assert free_minutes == 30


def test_normal_day_without_overlaps(generated_files):
    """Sam's October 20 calendar has no overlapping meetings."""
    events = [
        event
        for event in read_json(generated_files, "sam")
        if event["start"].startswith("2026-10-20")
    ]

    for previous, current in zip(events, events[1:]):
        assert previous["end"] <= current["start"]


def test_generator_can_run_twice(generated_files):
    """Running the generators again should not duplicate events."""
    json_generator.generate_json_calendars()
    csv_generator.generate_csv_calendars()

    for person, count in EXPECTED_COUNTS.items():
        assert len(read_json(generated_files, person)) == count
        assert len(read_csv(generated_files, person)) == count
