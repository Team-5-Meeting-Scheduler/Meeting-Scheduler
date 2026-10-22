"""End-to-end scheduler tests. Owner: Vedanshu."""

import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from scheduler.cli import main
from scheduler.conflicts import find_conflicts
from scheduler.loaders import load_calendars
from scheduler.reporting import format_report
from scheduler.rules import MinimumGapRule, WorkingHoursRule
from scheduler.slot_finder import find_available_slots

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "sample_calendars"
MEETING_DATE = date(2026, 10, 20)
PARTICIPANTS = ["Sam", "Priya"]
DURATION = 30


@pytest.fixture
def sample_calendars(tmp_path):
    """Copy sample calendars so the suite never writes into project data."""
    input_dir = tmp_path / "calendars"
    shutil.copytree(SAMPLE_DIR, input_dir)
    return input_dir


@pytest.fixture
def sample_events(sample_calendars):
    return load_calendars(_preferred_calendar_paths(sample_calendars))


@pytest.fixture
def end_to_end_report(tmp_path, sample_calendars):
    """Run the CLI once against sample calendars and return the report path."""
    output = tmp_path / "reports" / "schedule.txt"
    main(_cli_argv(sample_calendars, output))
    return output


@pytest.fixture
def expected_report(sample_events):
    return _build_report(sample_events, MEETING_DATE, PARTICIPANTS, DURATION)


def _cli_argv(input_dir, output, meeting_date=MEETING_DATE, participants=None, duration=DURATION):
    return [
        "--input-dir",
        str(input_dir),
        "--date",
        meeting_date.isoformat() if isinstance(meeting_date, date) else meeting_date,
        "--participants",
        *(PARTICIPANTS if participants is None else participants),
        "--duration",
        str(duration),
        "--output",
        str(output),
    ]


def _preferred_calendar_paths(input_dir: Path) -> list[Path]:
    json_files = {path.stem: path for path in sorted(input_dir.glob("*.json"))}
    csv_files = {path.stem: path for path in sorted(input_dir.glob("*.csv"))}
    paths: list[Path] = []
    for stem in sorted(set(json_files) | set(csv_files)):
        paths.append(json_files[stem] if stem in json_files else csv_files[stem])
    return paths


def _build_report(events, meeting_date, participants, duration):
    known = {event.person for event in events}
    slots = find_available_slots(
        events,
        participants,
        meeting_date,
        duration,
        rules=[WorkingHoursRule(), MinimumGapRule()],
        known_participants=known,
    )
    selected = set(participants)
    conflicts = [
        conflict
        for conflict in find_conflicts(events)
        if conflict.person in selected
    ]
    return format_report(meeting_date, participants, duration, conflicts, slots)


def _write_json(directory: Path, person: str, events: list[dict]) -> None:
    (directory / f"{person.lower()}.json").write_text(
        json.dumps(events), encoding="utf-8"
    )


def test_sample_calendars_load_through_the_loader(sample_events):
    assert {event.person for event in sample_events} >= {"Sam", "Priya", "Alex"}


def test_sample_calendars_include_events_on_the_meeting_date(sample_events):
    assert any(event.start.date() == MEETING_DATE for event in sample_events)


def test_conflict_detection_finds_priya_overlap_in_sample_data(sample_events):
    conflicts = find_conflicts(sample_events)
    assert any(
        conflict.person == "Priya"
        and conflict.overlap_start.isoformat() == "2026-10-22T10:30:00"
        for conflict in conflicts
    )


def test_slot_finder_returns_shared_slots_for_sample_attendees(sample_events):
    known = {event.person for event in sample_events}
    slots = find_available_slots(
        sample_events,
        PARTICIPANTS,
        MEETING_DATE,
        DURATION,
        known_participants=known,
    )
    assert slots[0].start.isoformat() == "2026-10-20T10:00:00"


def test_end_to_end_creates_the_report_file(end_to_end_report):
    assert end_to_end_report.is_file()


def test_end_to_end_report_includes_the_requested_date(end_to_end_report):
    assert f"Date: {MEETING_DATE.isoformat()}" in end_to_end_report.read_text(
        encoding="utf-8"
    )


def test_end_to_end_report_includes_the_participants(end_to_end_report):
    assert "Participants: Sam, Priya" in end_to_end_report.read_text(encoding="utf-8")


def test_end_to_end_report_includes_the_duration(end_to_end_report):
    assert f"Duration: {DURATION} minutes" in end_to_end_report.read_text(
        encoding="utf-8"
    )


def test_end_to_end_report_matches_loaders_conflicts_and_slots(
    end_to_end_report, expected_report
):
    assert end_to_end_report.read_text(encoding="utf-8") == expected_report


def test_end_to_end_report_includes_the_first_shared_slot(end_to_end_report):
    assert "1. 10:00-10:30" in end_to_end_report.read_text(encoding="utf-8")


def test_end_to_end_report_has_a_suggested_times_section(end_to_end_report):
    assert "SUGGESTED MEETING TIMES" in end_to_end_report.read_text(encoding="utf-8")


def test_end_to_end_report_does_not_claim_no_slots_exist(end_to_end_report):
    assert "No shared meeting time is available." not in end_to_end_report.read_text(
        encoding="utf-8"
    )


def test_end_to_end_report_has_a_conflicts_section(end_to_end_report):
    assert "CALENDAR CONFLICTS" in end_to_end_report.read_text(encoding="utf-8")


def test_module_entry_point_writes_the_report(tmp_path, sample_calendars):
    output = tmp_path / "module_report.txt"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scheduler",
            *_cli_argv(sample_calendars, output),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert result.returncode == 0
    assert output.is_file()


def test_fixture_shared_slot_is_available_to_all_attendees(tmp_path):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    _write_json(
        calendars,
        "Sam",
        [
            {
                "person": "Sam",
                "title": "Busy",
                "start": "2026-10-23T09:00:00",
                "end": "2026-10-23T10:00:00",
            }
        ],
    )
    _write_json(
        calendars,
        "Priya",
        [
            {
                "person": "Priya",
                "title": "Busy",
                "start": "2026-10-23T10:00:00",
                "end": "2026-10-23T11:00:00",
            }
        ],
    )
    output = tmp_path / "report.txt"
    main(_cli_argv(calendars, output, meeting_date="2026-10-23"))
    assert "1. 11:00-11:30" in output.read_text(encoding="utf-8")


def test_fixture_full_day_reports_no_shared_slot(tmp_path):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    _write_json(
        calendars,
        "Sam",
        [
            {
                "person": "Sam",
                "title": "All Day",
                "start": "2026-10-23T09:00:00",
                "end": "2026-10-23T17:00:00",
            }
        ],
    )
    _write_json(calendars, "Priya", [])
    output = tmp_path / "report.txt"
    main(_cli_argv(calendars, output, meeting_date="2026-10-23"))
    assert "No shared meeting time is available." in output.read_text(encoding="utf-8")


def test_fixture_duration_longer_than_gap_reports_no_slot(tmp_path):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    _write_json(
        calendars,
        "Sam",
        [
            {
                "person": "Sam",
                "title": "Morning",
                "start": "2026-10-23T09:00:00",
                "end": "2026-10-23T12:00:00",
            },
            {
                "person": "Sam",
                "title": "Afternoon",
                "start": "2026-10-23T12:30:00",
                "end": "2026-10-23T17:00:00",
            },
        ],
    )
    _write_json(calendars, "Priya", [])
    output = tmp_path / "report.txt"
    main(_cli_argv(calendars, output, meeting_date="2026-10-23", duration=45))
    assert "No shared meeting time is available." in output.read_text(encoding="utf-8")


def test_fixture_empty_calendars_offer_opening_slot(tmp_path):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    _write_json(calendars, "Sam", [])
    _write_json(calendars, "Priya", [])
    output = tmp_path / "report.txt"
    main(_cli_argv(calendars, output, meeting_date="2026-10-23"))
    assert "1. 09:00-09:30" in output.read_text(encoding="utf-8")


def test_fixture_working_hours_include_closing_slot(tmp_path):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    _write_json(calendars, "Sam", [])
    _write_json(calendars, "Priya", [])
    output = tmp_path / "report.txt"
    main(_cli_argv(calendars, output, meeting_date="2026-10-23"))
    assert "16:30-17:00" in output.read_text(encoding="utf-8")


def test_fixture_conflict_appears_in_the_saved_report(tmp_path):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    _write_json(
        calendars,
        "Sam",
        [
            {
                "person": "Sam",
                "title": "Standup",
                "start": "2026-10-23T09:00:00",
                "end": "2026-10-23T10:00:00",
            },
            {
                "person": "Sam",
                "title": "Client",
                "start": "2026-10-23T09:30:00",
                "end": "2026-10-23T10:30:00",
            },
        ],
    )
    _write_json(calendars, "Priya", [])
    output = tmp_path / "report.txt"
    main(_cli_argv(calendars, output, meeting_date="2026-10-23"))
    assert "Conflict: 09:30-10:00" in output.read_text(encoding="utf-8")


def test_sample_conflict_day_includes_priya_overlap(tmp_path, sample_calendars):
    output = tmp_path / "conflict_day.txt"
    main(
        _cli_argv(
            sample_calendars,
            output,
            meeting_date=date(2026, 10, 22),
            participants=["Priya", "Sam"],
        )
    )
    assert "Conflict: 10:30-11:00" in output.read_text(encoding="utf-8")


def _mock_nl_for_sample(monkeypatch):
    from scheduler.nl_parser import ParsedSchedulingRequest

    monkeypatch.setattr(
        "scheduler.cli.parse_natural_language_request",
        lambda *args, **kwargs: ParsedSchedulingRequest(
            participants=PARTICIPANTS,
            duration_minutes=DURATION,
            meeting_date=MEETING_DATE,
            time_preference=None,
        ),
    )


def test_nl_end_to_end_creates_report_from_sample_calendars(
    tmp_path, sample_calendars, monkeypatch
):
    _mock_nl_for_sample(monkeypatch)
    output = tmp_path / "nl_report.txt"
    main(
        [
            "--input-dir",
            str(sample_calendars),
            "--request",
            "30 minutes with Sam and Priya on 2026-10-20",
            "--output",
            str(output),
        ]
    )
    assert output.is_file()


def test_nl_end_to_end_report_matches_typed_engine_output(
    tmp_path, sample_calendars, expected_report, monkeypatch
):
    _mock_nl_for_sample(monkeypatch)
    output = tmp_path / "nl_report.txt"
    main(
        [
            "--input-dir",
            str(sample_calendars),
            "--request",
            "30 minutes with Sam and Priya on 2026-10-20",
            "--output",
            str(output),
        ]
    )
    assert output.read_text(encoding="utf-8") == expected_report


def test_nl_end_to_end_report_includes_first_shared_slot(
    tmp_path, sample_calendars, monkeypatch
):
    _mock_nl_for_sample(monkeypatch)
    output = tmp_path / "nl_report.txt"
    main(
        [
            "--input-dir",
            str(sample_calendars),
            "--request",
            "30 minutes with Sam and Priya on 2026-10-20",
            "--output",
            str(output),
        ]
    )
    assert "1. 10:00-10:30" in output.read_text(encoding="utf-8")


def test_typed_cli_still_works_without_an_api_key(
    tmp_path, sample_calendars, monkeypatch
):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    output = tmp_path / "typed_report.txt"
    main(_cli_argv(sample_calendars, output))
    assert output.is_file()


def _write_ics(directory: Path, person: str, body: str) -> None:
    (directory / f"{person.lower()}.ics").write_text(
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Scheduler tests//EN\n"
        + body
        + "END:VCALENDAR\n",
        encoding="utf-8",
    )


def test_nl_end_to_end_works_with_ics_only_calendars(tmp_path, monkeypatch):
    from scheduler.nl_parser import ParsedSchedulingRequest

    calendars = tmp_path / "calendars"
    calendars.mkdir()
    event = (
        "BEGIN:VEVENT\nUID:sam-1\nSUMMARY:Standup\n"
        "DTSTART:20261023T090000\nDTEND:20261023T093000\nEND:VEVENT\n"
    )
    _write_ics(calendars, "Sam", event)
    _write_ics(
        calendars,
        "Priya",
        "BEGIN:VEVENT\nUID:priya-1\nSUMMARY:Focus\n"
        "DTSTART:20261023T100000\nDTEND:20261023T110000\nEND:VEVENT\n",
    )
    monkeypatch.setattr(
        "scheduler.cli.parse_natural_language_request",
        lambda *args, **kwargs: ParsedSchedulingRequest(
            participants=["Sam", "Priya"],
            duration_minutes=30,
            meeting_date=date(2026, 10, 23),
            time_preference=None,
        ),
    )
    output = tmp_path / "ics_nl_report.txt"

    main(
        [
            "--input-dir",
            str(calendars),
            "--request",
            "30 minutes with Sam and Priya on 2026-10-23",
            "--output",
            str(output),
        ]
    )
    assert output.is_file()


def test_nl_end_to_end_ics_report_includes_a_shared_slot(tmp_path, monkeypatch):
    from scheduler.nl_parser import ParsedSchedulingRequest

    calendars = tmp_path / "calendars"
    calendars.mkdir()
    _write_ics(
        calendars,
        "Sam",
        "BEGIN:VEVENT\nUID:sam-1\nSUMMARY:Standup\n"
        "DTSTART:20261023T090000\nDTEND:20261023T093000\nEND:VEVENT\n",
    )
    _write_ics(
        calendars,
        "Priya",
        "BEGIN:VEVENT\nUID:priya-1\nSUMMARY:Focus\n"
        "DTSTART:20261023T100000\nDTEND:20261023T110000\nEND:VEVENT\n",
    )
    monkeypatch.setattr(
        "scheduler.cli.parse_natural_language_request",
        lambda *args, **kwargs: ParsedSchedulingRequest(
            participants=["Sam", "Priya"],
            duration_minutes=30,
            meeting_date=date(2026, 10, 23),
            time_preference=None,
        ),
    )
    output = tmp_path / "ics_nl_report.txt"

    main(
        [
            "--input-dir",
            str(calendars),
            "--request",
            "30 minutes with Sam and Priya on 2026-10-23",
            "--output",
            str(output),
        ]
    )
    assert "1. 09:30-10:00" in output.read_text(encoding="utf-8")
