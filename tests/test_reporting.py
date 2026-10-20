"""Tests for scheduler.reporting. Owner: Vedanshu."""

from datetime import date, datetime

import pytest

from scheduler.conflicts import Conflict
from scheduler.models import Event
from scheduler.reporting import format_report, write_report
from scheduler.slot_finder import TimeSlot

MEETING_DATE = date(2026, 10, 23)


def at(clock: str) -> datetime:
    return datetime.fromisoformat(f"2026-10-23T{clock}")


def conflict() -> Conflict:
    standup = Event("Sam", "Daily Standup", at("09:00"), at("10:00"))
    client = Event("Sam", "Client Meeting", at("09:30"), at("10:30"))
    return Conflict(
        person="Sam",
        event_a=standup,
        event_b=client,
        overlap_start=at("09:30"),
        overlap_end=at("10:00"),
    )


def report(conflicts=None, slots=None, participants=None, duration=30) -> str:
    return format_report(
        MEETING_DATE,
        ["Sam", "Priya"] if participants is None else participants,
        duration,
        [] if conflicts is None else conflicts,
        [] if slots is None else slots,
    )


def test_report_includes_the_requested_date():
    assert "Date: 2026-10-23" in report()


def test_report_includes_the_requested_participants():
    assert "Participants: Sam, Priya, Alex" in report(participants=["Sam", "Priya", "Alex"])


def test_report_includes_the_requested_duration():
    assert "Duration: 45 minutes" in report(duration=45)


def test_report_names_the_attendee_in_a_conflict():
    assert "Sam:" in report(conflicts=[conflict()])


def test_report_includes_the_first_conflicting_event():
    assert "Daily Standup: 09:00-10:00" in report(conflicts=[conflict()])


def test_report_includes_the_second_conflicting_event():
    assert "Client Meeting: 09:30-10:30" in report(conflicts=[conflict()])


def test_report_includes_the_overlap_window():
    assert "Conflict: 09:30-10:00" in report(conflicts=[conflict()])


def test_report_lists_suggested_slots_in_given_order():
    slots = [
        TimeSlot(at("12:00"), at("12:30")),
        TimeSlot(at("12:15"), at("12:45")),
    ]
    text = report(slots=slots)
    assert text.index("1. 12:00-12:30") < text.index("2. 12:15-12:45")


def test_report_says_when_there_are_no_conflicts():
    assert "No calendar conflicts." in report(conflicts=[])


def test_report_says_when_no_slots_exist():
    assert "No shared meeting time is available." in report(slots=[])


def test_write_report_saves_the_text(tmp_path):
    destination = tmp_path / "schedule.txt"
    write_report("Date: 2026-10-23\n", destination)
    assert destination.read_text(encoding="utf-8") == "Date: 2026-10-23\n"


def test_report_keeps_participant_order():
    assert "Participants: Priya, Sam" in report(participants=["Priya", "Sam"])


def test_report_has_a_conflicts_heading():
    assert "CALENDAR CONFLICTS" in report()


def test_report_has_a_suggested_times_heading():
    assert "SUGGESTED MEETING TIMES" in report()


def test_report_omits_the_empty_conflict_message_when_conflicts_exist():
    assert "No calendar conflicts." not in report(conflicts=[conflict()])


def test_report_omits_the_empty_slot_message_when_slots_exist():
    slots = [TimeSlot(at("12:00"), at("12:30"))]
    assert "No shared meeting time is available." not in report(slots=slots)


def test_report_lists_every_suggested_slot():
    slots = [
        TimeSlot(at("12:00"), at("12:30")),
        TimeSlot(at("15:00"), at("15:30")),
        TimeSlot(at("16:30"), at("17:00")),
    ]
    assert "1. 12:00-12:30\n2. 15:00-15:30\n3. 16:30-17:00" in report(slots=slots)


def test_report_numbers_the_earliest_slot_first():
    slots = [TimeSlot(at("12:00"), at("12:30"))]
    assert "1. 12:00-12:30" in report(slots=slots)


def test_report_shows_a_second_attendees_conflict():
    priya = Conflict(
        person="Priya",
        event_a=Event("Priya", "Design Review", at("14:00"), at("15:00")),
        event_b=Event("Priya", "Interview", at("14:30"), at("15:30")),
        overlap_start=at("14:30"),
        overlap_end=at("15:00"),
    )
    assert "Priya:" in report(conflicts=[conflict(), priya])


def test_report_shows_each_conflict_for_the_same_attendee():
    later = Conflict(
        person="Sam",
        event_a=Event("Sam", "Planning", at("13:00"), at("14:00")),
        event_b=Event("Sam", "Demo", at("13:30"), at("14:30")),
        overlap_start=at("13:30"),
        overlap_end=at("14:00"),
    )
    assert "Conflict: 13:30-14:00" in report(conflicts=[conflict(), later])


def test_report_prints_a_conflict_once():
    text = report(conflicts=[conflict()])
    assert text.count("Conflict: 09:30-10:00") == 1


def test_write_report_creates_a_missing_directory(tmp_path):
    destination = tmp_path / "reports" / "schedule.txt"
    write_report("saved\n", destination)
    assert destination.is_file()


def test_format_report_rejects_an_empty_participant_list():
    with pytest.raises(ValueError, match="participant"):
        report(participants=[])


def test_format_report_rejects_a_blank_participant_name():
    with pytest.raises(ValueError, match="non-empty"):
        report(participants=["Sam", " "])


def test_format_report_rejects_a_non_positive_duration():
    with pytest.raises(ValueError, match="positive"):
        report(duration=0)


def test_format_report_rejects_a_datetime_as_the_meeting_date():
    with pytest.raises(ValueError, match="calendar date"):
        format_report(at("09:00"), ["Sam"], 30, [], [])


def test_format_report_rejects_a_non_conflict_entry():
    with pytest.raises(TypeError, match="Conflict"):
        report(conflicts=["Sam is busy"])


def test_format_report_rejects_a_non_slot_entry():
    with pytest.raises(TypeError, match="TimeSlot"):
        report(slots=[(at("12:00"), at("12:30"))])


def test_write_report_rejects_a_directory_destination(tmp_path):
    with pytest.raises(IsADirectoryError, match="directory"):
        write_report("saved\n", tmp_path)


def test_write_report_rejects_an_empty_path():
    with pytest.raises(ValueError, match="path"):
        write_report("saved\n", "  ")


def test_write_report_rejects_non_text():
    with pytest.raises(TypeError, match="string"):
        write_report(None, "reports/schedule.txt")


def test_write_report_replaces_an_existing_file(tmp_path):
    destination = tmp_path / "schedule.txt"
    destination.write_text("old\n", encoding="utf-8")
    write_report("new\n", destination)
    assert destination.read_text(encoding="utf-8") == "new\n"
