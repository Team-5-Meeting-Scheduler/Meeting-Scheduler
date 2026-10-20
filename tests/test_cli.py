"""Tests for scheduler.cli. Owner: Vedanshu."""

import json
from datetime import date
from pathlib import Path

import pytest

from scheduler.cli import main, parse_args, run


def write_calendar(directory: Path, person: str, events: list[dict]) -> Path:
    path = directory / f"{person.lower()}.json"
    path.write_text(json.dumps(events), encoding="utf-8")
    return path


def free_day(person: str) -> list[dict]:
    return []


def busy(person: str, start: str, end: str, title: str = "Meeting") -> dict:
    return {
        "person": person,
        "title": title,
        "start": f"2026-10-23T{start}",
        "end": f"2026-10-23T{end}",
    }


def argv(input_dir, output, participants=None, meeting_date="2026-10-23", duration="30"):
    return [
        "--input-dir",
        str(input_dir),
        "--date",
        meeting_date,
        "--participants",
        *(["Sam", "Priya"] if participants is None else participants),
        "--duration",
        duration,
        "--output",
        str(output),
    ]


def test_parse_args_reads_the_input_directory(tmp_path):
    args = parse_args(argv(tmp_path, tmp_path / "out.txt"))
    assert args.input_dir == str(tmp_path)


def test_parse_args_reads_the_meeting_date(tmp_path):
    args = parse_args(argv(tmp_path, tmp_path / "out.txt"))
    assert args.date == date(2026, 10, 23)


def test_parse_args_reads_the_participants(tmp_path):
    args = parse_args(argv(tmp_path, tmp_path / "out.txt", participants=["Sam", "Alex"]))
    assert args.participants == ["Sam", "Alex"]


def test_parse_args_reads_the_duration(tmp_path):
    args = parse_args(argv(tmp_path, tmp_path / "out.txt", duration="45"))
    assert args.duration == 45


def test_parse_args_reads_the_output_path(tmp_path):
    output = tmp_path / "reports" / "schedule.txt"
    args = parse_args(argv(tmp_path, output))
    assert args.output == str(output)


def test_parse_args_rejects_an_invalid_date(tmp_path):
    with pytest.raises(SystemExit):
        parse_args(argv(tmp_path, tmp_path / "out.txt", meeting_date="10-23-2026"))


def test_parse_args_rejects_a_zero_duration(tmp_path):
    with pytest.raises(SystemExit):
        parse_args(argv(tmp_path, tmp_path / "out.txt", duration="0"))


def test_parse_args_rejects_a_negative_duration(tmp_path):
    with pytest.raises(SystemExit):
        parse_args(argv(tmp_path, tmp_path / "out.txt", duration="-15"))


def test_help_mentions_the_input_directory(capsys):
    with pytest.raises(SystemExit) as raised:
        parse_args(["--help"])
    assert raised.value.code == 0
    assert "--input-dir" in capsys.readouterr().out


def test_main_writes_a_report_file(tmp_path, capsys):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"

    main(argv(calendars, output))

    assert output.is_file()


def test_main_prints_the_output_path(tmp_path, capsys):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"

    main(argv(calendars, output))

    assert f"Report written to {output}" in capsys.readouterr().out


def test_report_includes_the_requested_date(tmp_path):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"

    main(argv(calendars, output))

    assert "Date: 2026-10-23" in output.read_text(encoding="utf-8")


def test_report_includes_the_participants(tmp_path):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"

    main(argv(calendars, output))

    assert "Participants: Sam, Priya" in output.read_text(encoding="utf-8")


def test_report_includes_a_suggested_slot(tmp_path):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"

    main(argv(calendars, output))

    assert "1. 09:00-09:30" in output.read_text(encoding="utf-8")


def test_report_includes_a_detected_conflict(tmp_path):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(
        calendars,
        "Sam",
        [
            busy("Sam", "09:00", "10:00", "Standup"),
            busy("Sam", "09:30", "10:30", "Client"),
        ],
    )
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"

    main(argv(calendars, output))

    assert "Conflict: 09:30-10:00" in output.read_text(encoding="utf-8")


def test_main_rejects_a_missing_input_directory(tmp_path, capsys):
    missing = tmp_path / "missing"
    output = tmp_path / "report.txt"

    with pytest.raises(SystemExit) as raised:
        main(argv(missing, output))

    assert raised.value.code == 2
    assert "Input directory not found" in capsys.readouterr().err


def test_main_rejects_a_file_used_as_input_directory(tmp_path, capsys):
    not_a_dir = tmp_path / "calendars.txt"
    not_a_dir.write_text("nope", encoding="utf-8")
    output = tmp_path / "report.txt"

    with pytest.raises(SystemExit) as raised:
        main(argv(not_a_dir, output))

    assert raised.value.code == 2
    assert "not a directory" in capsys.readouterr().err


def test_main_rejects_an_empty_input_directory(tmp_path, capsys):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    output = tmp_path / "report.txt"

    with pytest.raises(SystemExit) as raised:
        main(argv(calendars, output))

    assert raised.value.code == 2
    assert "No calendar files found" in capsys.readouterr().err


def test_main_rejects_an_unknown_participant(tmp_path, capsys):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    output = tmp_path / "report.txt"

    with pytest.raises(SystemExit) as raised:
        main(argv(calendars, output, participants=["Sam", "Alex"]))

    assert raised.value.code == 2
    assert "Alex" in capsys.readouterr().err


def test_main_prints_an_invalid_date_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as raised:
        main(argv(tmp_path, tmp_path / "out.txt", meeting_date="tomorrow"))

    assert raised.value.code == 2


def test_main_prints_a_non_positive_duration_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as raised:
        main(argv(tmp_path, tmp_path / "out.txt", duration="0"))

    assert raised.value.code == 2


def test_prefers_json_when_a_csv_twin_exists(tmp_path):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", [busy("Sam", "09:00", "10:00", "FromJSON")])
    (calendars / "sam.csv").write_text(
        "person,title,start,end\n"
        "Sam,FromCSV,2026-10-23T09:00:00,2026-10-23T17:00:00\n",
        encoding="utf-8",
    )
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"

    main(argv(calendars, output))
    text = output.read_text(encoding="utf-8")

    assert "1. 10:00-10:30" in text


def test_loads_csv_when_json_is_absent(tmp_path):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    (calendars / "sam.csv").write_text(
        "person,title,start,end\n",
        encoding="utf-8",
    )
    (calendars / "priya.csv").write_text(
        "person,title,start,end\n",
        encoding="utf-8",
    )
    output = tmp_path / "report.txt"

    main(argv(calendars, output))

    assert "Date: 2026-10-23" in output.read_text(encoding="utf-8")


def test_empty_calendar_file_still_counts_as_known(tmp_path):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"

    main(argv(calendars, output, participants=["Sam", "Priya"]))

    assert "No shared meeting time is available." not in output.read_text(encoding="utf-8")


def test_run_creates_a_missing_output_directory(tmp_path):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "reports" / "schedule.txt"
    args = parse_args(argv(calendars, output))

    run(args)

    assert output.is_file()
