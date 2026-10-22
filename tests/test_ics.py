"""ICS imports use the same Event model and scheduling pipeline as JSON/CSV."""

from datetime import datetime
import json

import pytest

from scheduler.cli import main
from scheduler.conflicts import find_conflicts
from scheduler.loaders import load_calendars, load_ics_calendar
from scheduler.models import Event


BASIC = (
    "BEGIN:VEVENT\nUID:meeting-1\nSUMMARY:Team meeting\n"
    "DTSTART:20261023T090000\nDTEND:20261023T100000\nEND:VEVENT\n"
)


def write_ics(tmp_path, content=BASIC, name="sam.ics"):
    path = tmp_path / name
    path.write_text(
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Scheduler tests//EN\n"
        + content + "END:VCALENDAR\n",
        encoding="utf-8",
    )
    return path


def test_floating_times_map_to_shared_event_and_filename_owner(tmp_path):
    events = load_ics_calendar(str(write_ics(tmp_path)))

    assert events == [
        Event("Sam", "Team meeting", datetime(2026, 10, 23, 9), datetime(2026, 10, 23, 10))
    ]


def test_explicit_owner_is_not_replaced_by_organizer_or_attendees(tmp_path):
    body = BASIC.replace(
        "SUMMARY:Team meeting",
        'SUMMARY:Team meeting\nORGANIZER;CN=Someone Else:mailto:organizer@example.com\n'
        'ATTENDEE;CN=Priya:mailto:priya@example.com',
    )

    assert load_ics_calendar(write_ics(tmp_path, body), person="Alex Chen")[0].person == "Alex Chen"


def test_folded_and_escaped_summary_is_decoded(tmp_path):
    body = BASIC.replace("SUMMARY:Team meeting", "SUMMARY:Project\\, review\\; next\n steps\\nAgenda")

    assert load_ics_calendar(write_ics(tmp_path, body))[0].title == "Project, review; nextsteps\nAgenda"


def test_multiple_events_preserve_input_order_and_double_bookings(tmp_path):
    second = BASIC.replace("meeting-1", "meeting-2").replace(
        "SUMMARY:Team meeting", "SUMMARY:Client meeting"
    ).replace("090000", "093000").replace("100000", "103000")

    events = load_ics_calendar(write_ics(tmp_path, second + BASIC))

    assert [event.title for event in events] == ["Client meeting", "Team meeting"]
    assert len(find_conflicts(events)) == 1


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("DTSTART:20261023T130000Z", "DTEND:20261023T140000Z"),
        (
            "DTSTART;TZID=Europe/London:20261023T140000",
            "DTEND;TZID=Europe/London:20261023T150000",
        ),
        (
            "DTSTART;TZID=America/New_York:20261023T090000",
            "DTEND;TZID=America/New_York:20261023T100000",
        ),
    ],
)
def test_zoned_times_convert_to_explicit_team_zone_before_removing_tzinfo(tmp_path, start, end):
    body = BASIC.replace("DTSTART:20261023T090000", start).replace("DTEND:20261023T100000", end)

    imported = load_ics_calendar(write_ics(tmp_path, body), local_timezone="America/New_York")[0]

    assert imported.start == datetime(2026, 10, 23, 9)
    assert imported.end == datetime(2026, 10, 23, 10)
    assert imported.start.tzinfo is imported.end.tzinfo is None


def test_conversion_can_change_calendar_date(tmp_path):
    body = BASIC.replace("20261023T090000", "20261023T010000Z").replace(
        "20261023T100000", "20261023T020000Z"
    )

    imported = load_ics_calendar(write_ics(tmp_path, body), local_timezone="America/New_York")[0]

    assert imported.start == datetime(2026, 10, 22, 21)
    assert imported.end == datetime(2026, 10, 22, 22)


def test_zoned_events_require_explicit_target_timezone(tmp_path):
    body = BASIC.replace("090000", "090000Z").replace("100000", "100000Z")

    with pytest.raises(ValueError, match="local_timezone"):
        load_ics_calendar(write_ics(tmp_path, body))


@pytest.mark.parametrize("zone", ["Unknown/Zone", "", 123])
def test_invalid_target_timezone_is_rejected(tmp_path, zone):
    with pytest.raises(ValueError, match="Unknown local time zone"):
        load_ics_calendar(write_ics(tmp_path), local_timezone=zone)


@pytest.mark.parametrize("explicit_end", [False, True])
def test_all_day_dates_have_exclusive_midnight_end(tmp_path, explicit_end):
    body = BASIC.replace("DTSTART:20261023T090000", "DTSTART;VALUE=DATE:20261023")
    body = body.replace(
        "DTEND:20261023T100000\n",
        "DTEND;VALUE=DATE:20261024\n" if explicit_end else "",
    )

    imported = load_ics_calendar(write_ics(tmp_path, body))[0]

    assert imported.start == datetime(2026, 10, 23)
    assert imported.end == datetime(2026, 10, 24)


@pytest.mark.parametrize("content", ["", "BEGIN:VTODO\nSUMMARY:Task\nEND:VTODO\n"])
def test_empty_calendars_and_non_event_components_return_no_events(tmp_path, content):
    assert load_ics_calendar(write_ics(tmp_path, content)) == []


@pytest.mark.parametrize("property_line", ["STATUS:CANCELLED", "TRANSP:TRANSPARENT"])
def test_non_busy_events_are_not_imported(tmp_path, property_line):
    body = BASIC.replace("END:VEVENT", property_line + "\nEND:VEVENT")

    assert load_ics_calendar(write_ics(tmp_path, body)) == []


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("SUMMARY:Team meeting\n", "", "SUMMARY"),
        ("SUMMARY:Team meeting", "SUMMARY:   ", "Title"),
        ("DTSTART:20261023T090000\n", "", "DTSTART"),
        ("DTEND:20261023T100000\n", "", "DTEND"),
        ("20261023T090000", "invalid", "DTSTART"),
        ("20261023T090000", "20260230T090000", "DTSTART"),
        ("20261023T100000", "20261023T090000", "later than start"),
        ("20261023T100000", "20261023T080000", "later than start"),
        (
            "DTSTART:20261023T090000", "DTSTART;VALUE=DATE:20261023",
            "both be DATE or DATE-TIME",
        ),
        ("20261023T090000", "20261023T090000Z", "consistent time zones"),
        (
            "DTSTART:20261023T090000", "DTSTART;TZID=Unknown/Zone:20261023T090000",
            "Unresolved DTSTART",
        ),
        ("SUMMARY:Team meeting", "SUMMARY:One\nSUMMARY:Two", "Duplicate SUMMARY"),
        (
            "DTSTART:20261023T090000", "DTSTART:20261023T090000\nDTSTART:20261023T093000",
            "Duplicate DTSTART",
        ),
    ],
)
def test_malformed_events_fail_with_path_and_event_index(tmp_path, old, new, message):
    path = write_ics(tmp_path, BASIC.replace(old, new))

    with pytest.raises(ValueError, match=message) as error:
        load_ics_calendar(path)

    assert str(path) in str(error.value)
    assert "VEVENT 1" in str(error.value)


@pytest.mark.parametrize(
    "property_line",
    ["RRULE:FREQ=DAILY", "RDATE:20261024T090000", "EXDATE:20261024T090000",
     "RECURRENCE-ID:20261023T090000", "DURATION:PT1H"],
)
def test_unsupported_features_fail_instead_of_silently_losing_busy_time(tmp_path, property_line):
    body = BASIC.replace("END:VEVENT", property_line + "\nEND:VEVENT")

    with pytest.raises(ValueError, match="not supported"):
        load_ics_calendar(write_ics(tmp_path, body))


@pytest.mark.parametrize("content", ["", "not a calendar", "BEGIN:VCALENDAR\n", BASIC])
def test_malformed_calendar_is_rejected(tmp_path, content):
    path = tmp_path / "broken.ics"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="ICS") as error:
        load_ics_calendar(path)

    assert str(path) in str(error.value)


def test_bad_event_after_valid_event_fails_entire_import(tmp_path):
    path = write_ics(tmp_path, BASIC + BASIC.replace("20261023T090000", "bad"))

    with pytest.raises(ValueError, match="VEVENT 2"):
        load_ics_calendar(path)


@pytest.mark.parametrize("person", ["", "   ", 123])
def test_invalid_owner_is_rejected_even_for_empty_calendar(tmp_path, person):
    with pytest.raises(ValueError, match="Person"):
        load_ics_calendar(write_ics(tmp_path, ""), person=person)


def test_missing_file_raises_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="missing.ics"):
        load_ics_calendar(tmp_path / "missing.ics")


def test_invalid_utf8_is_rejected(tmp_path):
    path = tmp_path / "bad.ics"
    path.write_bytes(b"\xff\xfe")

    with pytest.raises(ValueError, match="UTF-8"):
        load_ics_calendar(path)


def test_json_csv_and_ics_can_be_loaded_together(tmp_path):
    sam = write_ics(tmp_path, name="sam.ICS")
    record = {
        "person": "Priya", "title": "Review",
        "start": "2026-10-23T09:00:00", "end": "2026-10-23T10:00:00",
    }
    priya = tmp_path / "priya.json"
    priya.write_text(json.dumps([record]), encoding="utf-8")
    alex = tmp_path / "alex.csv"
    alex.write_text(
        "person,title,start,end\nAlex,Work,2026-10-23T10:00:00,2026-10-23T11:00:00\n",
        encoding="utf-8",
    )

    assert [event.person for event in load_calendars([sam, priya, alex])] == ["Sam", "Priya", "Alex"]


def test_cli_generates_report_from_zoned_ics_input(tmp_path, capsys):
    body = BASIC.replace("090000", "130000Z").replace("100000", "140000Z")
    write_ics(tmp_path, body, name="sam.ICS")
    output = tmp_path / "report.txt"

    main([
        "--input-dir", str(tmp_path), "--date", "2026-10-23",
        "--participants", "Sam", "--duration", "30", "--output", str(output),
        "--timezone", "America/New_York",
    ])

    report = output.read_text(encoding="utf-8")
    assert "Sam" in report
    assert "10:00-10:30" in report
    assert "09:00-09:30" not in report
    assert "Report written" in capsys.readouterr().out


def test_cli_reports_missing_timezone_without_writing_report(tmp_path, capsys):
    body = BASIC.replace("090000", "090000Z").replace("100000", "100000Z")
    write_ics(tmp_path, body)
    output = tmp_path / "report.txt"

    with pytest.raises(SystemExit) as error:
        main([
            "--input-dir", str(tmp_path), "--date", "2026-10-23",
            "--participants", "Sam", "--duration", "30", "--output", str(output),
        ])

    assert error.value.code == 2
    assert "local_timezone" in capsys.readouterr().err
    assert not output.exists()


def test_cli_prefers_existing_json_over_ics_twin(tmp_path):
    # The malformed duplicate must not be imported alongside the preferred JSON.
    (tmp_path / "sam.ics").write_text("not a calendar", encoding="utf-8")
    (tmp_path / "sam.json").write_text("[]", encoding="utf-8")
    output = tmp_path / "report.txt"

    main([
        "--input-dir", str(tmp_path), "--date", "2026-10-23",
        "--participants", "Sam", "--duration", "30", "--output", str(output),
    ])

    assert "09:00-09:30" in output.read_text(encoding="utf-8")
