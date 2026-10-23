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


def test_main_prints_the_report_for_json_calendars(tmp_path, capsys):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"

    main(argv(calendars, output))

    assert "MEETING SCHEDULER REPORT" in capsys.readouterr().out


def test_main_prints_the_report_for_csv_calendars(tmp_path, capsys):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    (calendars / "sam.csv").write_text("person,title,start,end\n", encoding="utf-8")
    (calendars / "priya.csv").write_text("person,title,start,end\n", encoding="utf-8")
    output = tmp_path / "report.txt"

    main(argv(calendars, output))

    assert "MEETING SCHEDULER REPORT" in capsys.readouterr().out


def test_main_prints_the_report_for_ics_calendars(tmp_path, capsys):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    ics = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Scheduler tests//EN\n"
        "BEGIN:VEVENT\nUID:1\nSUMMARY:Standup\n"
        "DTSTART:20261023T090000\nDTEND:20261023T093000\nEND:VEVENT\n"
        "END:VCALENDAR\n"
    )
    (calendars / "sam.ics").write_text(ics, encoding="utf-8")
    (calendars / "priya.ics").write_text(
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Scheduler tests//EN\n"
        "END:VCALENDAR\n",
        encoding="utf-8",
    )
    output = tmp_path / "report.txt"

    main(argv(calendars, output))

    assert "MEETING SCHEDULER REPORT" in capsys.readouterr().out


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


def on_day(
    person: str, day: str, start: str, end: str, title: str = "Meeting"
) -> dict:
    return {
        "person": person,
        "title": title,
        "start": f"{day}T{start}",
        "end": f"{day}T{end}",
    }


def test_report_omits_a_conflict_from_another_day(tmp_path):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(
        calendars,
        "Sam",
        [
            on_day("Sam", "2026-10-20", "09:00", "10:00", "Standup"),
            on_day("Sam", "2026-10-20", "09:30", "10:30", "Client"),
        ],
    )
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"

    main(argv(calendars, output))

    report = output.read_text(encoding="utf-8")
    assert "Conflict: 09:30-10:00" not in report
    assert "No calendar conflicts." in report


def test_report_keeps_the_meeting_day_conflict_and_drops_the_others(tmp_path):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(
        calendars,
        "Sam",
        [
            on_day("Sam", "2026-10-20", "09:00", "10:00", "Old Standup"),
            on_day("Sam", "2026-10-20", "09:30", "10:30", "Old Client"),
            on_day("Sam", "2026-10-23", "14:00", "15:00", "Review"),
            on_day("Sam", "2026-10-23", "14:30", "15:30", "One-on-one"),
        ],
    )
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"

    main(argv(calendars, output))

    report = output.read_text(encoding="utf-8")
    assert "Conflict: 14:30-15:00" in report
    assert "Conflict: 09:30-10:00" not in report


def test_report_omits_a_conflict_that_ends_at_the_meeting_day_midnight(tmp_path):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(
        calendars,
        "Sam",
        [
            on_day("Sam", "2026-10-22", "22:00", "23:59", "Late Call"),
            {
                "person": "Sam",
                "title": "Overnight Run",
                "start": "2026-10-22T23:00:00",
                "end": "2026-10-23T00:00:00",
            },
        ],
    )
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"

    main(argv(calendars, output))

    assert "No calendar conflicts." in output.read_text(encoding="utf-8")


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


def test_typed_cli_still_requires_date_without_request(tmp_path):
    with pytest.raises(SystemExit):
        parse_args(
            [
                "--input-dir",
                str(tmp_path),
                "--participants",
                "Sam",
                "--duration",
                "30",
                "--output",
                str(tmp_path / "out.txt"),
            ]
        )


def test_request_mode_does_not_require_typed_scheduling_flags(tmp_path):
    args = parse_args(
        [
            "--input-dir",
            str(tmp_path),
            "--request",
            "30 minutes with Sam and Priya next Tuesday afternoon",
            "--output",
            str(tmp_path / "out.txt"),
        ]
    )
    assert args.request.startswith("30 minutes")
    assert args.date is None
    assert args.participants is None
    assert args.duration is None


def _mock_nl_parser(
    monkeypatch,
    *,
    preference="afternoon",
    meeting_date=None,
    participants=None,
    duration=30,
):
    from scheduler.nl_parser import ParsedSchedulingRequest

    parsed = ParsedSchedulingRequest(
        participants=["Sam", "Priya"] if participants is None else participants,
        duration_minutes=duration,
        meeting_date=meeting_date or date(2026, 10, 23),
        time_preference=preference,
    )
    monkeypatch.setattr(
        "scheduler.cli.parse_natural_language_request",
        lambda *args, **kwargs: parsed,
    )
    return parsed


def test_request_mode_writes_the_report_file(tmp_path, monkeypatch):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"
    _mock_nl_parser(monkeypatch)

    main(
        [
            "--input-dir",
            str(calendars),
            "--request",
            "30 minutes with Sam and Priya next Tuesday afternoon",
            "--output",
            str(output),
        ]
    )
    assert output.is_file()


def test_request_mode_report_includes_the_parsed_date(tmp_path, monkeypatch):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"
    _mock_nl_parser(monkeypatch)

    main(
        [
            "--input-dir",
            str(calendars),
            "--request",
            "30 minutes with Sam and Priya afternoon",
            "--output",
            str(output),
        ]
    )
    assert "Date: 2026-10-23" in output.read_text(encoding="utf-8")


def test_request_mode_report_includes_the_parsed_participants(tmp_path, monkeypatch):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"
    _mock_nl_parser(monkeypatch)

    main(
        [
            "--input-dir",
            str(calendars),
            "--request",
            "30 minutes with Sam and Priya afternoon",
            "--output",
            str(output),
        ]
    )
    assert "Participants: Sam, Priya" in output.read_text(encoding="utf-8")


def test_request_mode_afternoon_preference_starts_at_noon(tmp_path, monkeypatch):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"
    _mock_nl_parser(monkeypatch, preference="afternoon")

    main(
        [
            "--input-dir",
            str(calendars),
            "--request",
            "30 minutes with Sam and Priya afternoon",
            "--output",
            str(output),
        ]
    )
    assert "1. 12:00-12:30" in output.read_text(encoding="utf-8")


def test_request_mode_morning_preference_starts_at_opening(tmp_path, monkeypatch):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"
    _mock_nl_parser(monkeypatch, preference="morning")

    main(
        [
            "--input-dir",
            str(calendars),
            "--request",
            "30 minutes with Sam and Priya morning",
            "--output",
            str(output),
        ]
    )
    assert "1. 09:00-09:30" in output.read_text(encoding="utf-8")


def test_request_mode_prints_the_parsed_summary(tmp_path, monkeypatch, capsys):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"
    _mock_nl_parser(monkeypatch)

    main(
        [
            "--input-dir",
            str(calendars),
            "--request",
            "30 minutes with Sam and Priya afternoon",
            "--output",
            str(output),
        ]
    )
    assert "Parsed request:" in capsys.readouterr().out


def test_request_mode_typed_date_overrides_parsed_date(tmp_path, monkeypatch):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"
    _mock_nl_parser(monkeypatch, meeting_date=date(2026, 10, 27))

    main(
        [
            "--input-dir",
            str(calendars),
            "--request",
            "30 minutes with Sam and Priya",
            "--date",
            "2026-10-23",
            "--output",
            str(output),
        ]
    )
    assert "Date: 2026-10-23" in output.read_text(encoding="utf-8")


def test_request_mode_typed_participants_override_parsed_names(tmp_path, monkeypatch):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    write_calendar(calendars, "Alex", free_day("Alex"))
    output = tmp_path / "report.txt"
    _mock_nl_parser(monkeypatch, participants=["Sam", "Priya"])

    main(
        [
            "--input-dir",
            str(calendars),
            "--request",
            "meet Sam and Priya",
            "--participants",
            "Sam",
            "Alex",
            "--output",
            str(output),
        ]
    )
    assert "Participants: Sam, Alex" in output.read_text(encoding="utf-8")


def test_request_mode_typed_duration_overrides_parsed_duration(tmp_path, monkeypatch):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    output = tmp_path / "report.txt"
    _mock_nl_parser(monkeypatch, duration=30, preference=None)

    main(
        [
            "--input-dir",
            str(calendars),
            "--request",
            "30 minutes with Sam and Priya",
            "--duration",
            "60",
            "--output",
            str(output),
        ]
    )
    assert "Duration: 60 minutes" in output.read_text(encoding="utf-8")


def test_request_mode_runtime_error_exits_with_status_two(
    tmp_path, monkeypatch, capsys
):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    monkeypatch.setattr(
        "scheduler.cli.parse_natural_language_request",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("Natural-language mode requires AZURE_OPENAI_API_KEY")
        ),
    )

    with pytest.raises(SystemExit) as raised:
        main(
            [
                "--input-dir",
                str(calendars),
                "--request",
                "30 minutes with Sam and Priya",
                "--output",
                str(tmp_path / "report.txt"),
            ]
        )

    assert raised.value.code == 2


def test_request_mode_runtime_error_prints_error_prefix(
    tmp_path, monkeypatch, capsys
):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    monkeypatch.setattr(
        "scheduler.cli.parse_natural_language_request",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("Natural-language mode requires AZURE_OPENAI_API_KEY")
        ),
    )

    with pytest.raises(SystemExit):
        main(
            [
                "--input-dir",
                str(calendars),
                "--request",
                "30 minutes with Sam and Priya",
                "--output",
                str(tmp_path / "report.txt"),
            ]
        )

    assert "Error: Natural-language mode requires AZURE_OPENAI_API_KEY" in (
        capsys.readouterr().err
    )


def test_request_mode_value_error_exits_with_status_two(
    tmp_path, monkeypatch, capsys
):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(calendars, "Sam", free_day("Sam"))
    write_calendar(calendars, "Priya", free_day("Priya"))
    monkeypatch.setattr(
        "scheduler.cli.parse_natural_language_request",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("No calendar found for participant Alex.")
        ),
    )

    with pytest.raises(SystemExit) as raised:
        main(
            [
                "--input-dir",
                str(calendars),
                "--request",
                "meet Alex",
                "--output",
                str(tmp_path / "report.txt"),
            ]
        )

    assert raised.value.code == 2


def test_request_mode_skips_morning_when_calendars_are_busy_before_noon(
    tmp_path, monkeypatch
):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(
        calendars,
        "Sam",
        [busy("Sam", "09:00", "12:00", "Morning block")],
    )
    write_calendar(
        calendars,
        "Priya",
        [busy("Priya", "09:00", "12:00", "Morning block")],
    )
    output = tmp_path / "report.txt"
    _mock_nl_parser(monkeypatch, preference="afternoon")

    main(
        [
            "--input-dir",
            str(calendars),
            "--request",
            "30 minutes with Sam and Priya afternoon",
            "--output",
            str(output),
        ]
    )
    text = output.read_text(encoding="utf-8")
    assert "1. 12:00-12:30" in text


def test_request_mode_with_busy_mornings_omits_morning_slot_lines(
    tmp_path, monkeypatch
):
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    write_calendar(
        calendars,
        "Sam",
        [busy("Sam", "09:00", "12:00", "Morning block")],
    )
    write_calendar(
        calendars,
        "Priya",
        [busy("Priya", "09:00", "12:00", "Morning block")],
    )
    output = tmp_path / "report.txt"
    _mock_nl_parser(monkeypatch, preference="afternoon")

    main(
        [
            "--input-dir",
            str(calendars),
            "--request",
            "30 minutes with Sam and Priya afternoon",
            "--output",
            str(output),
        ]
    )
    suggested = output.read_text(encoding="utf-8").split("SUGGESTED MEETING TIMES", 1)[1]
    assert "09:" not in suggested


def test_help_mentions_natural_language_request(capsys):
    with pytest.raises(SystemExit) as raised:
        parse_args(["--help"])
    assert raised.value.code == 0
    assert "--request" in capsys.readouterr().out
