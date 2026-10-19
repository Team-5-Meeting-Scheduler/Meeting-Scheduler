
from datetime import datetime, timezone

import pytest

from scheduler.models import Event


# -----------------------------------------
# 1. Valid event tests
# -----------------------------------------

def test_valid_event():
    event = Event(
        person="Sam",
        title="Team Meeting",
        start=datetime(2026, 10, 20, 9, 0),
        end=datetime(2026, 10, 20, 10, 0),
    )

    assert event.person == "Sam"
    assert event.title == "Team Meeting"
    assert event.start == datetime(2026, 10, 20, 9, 0)
    assert event.end == datetime(2026, 10, 20, 10, 0)


def test_different_calendar_date():
    event = Event(
        person="Priya",
        title="Project Review",
        start=datetime(2026, 11, 15, 14, 0),
        end=datetime(2026, 11, 15, 15, 0),
    )

    assert event.start.month == 11
    assert event.start.day == 15


def test_meeting_ends_at_five():
    event = Event(
        person="Alex",
        title="End of Day Review",
        start=datetime(2026, 10, 20, 16, 30),
        end=datetime(2026, 10, 20, 17, 0),
    )

    assert event.end.hour == 17


# -----------------------------------------
# 2. Person validation tests
# -----------------------------------------

def test_empty_person():
    with pytest.raises(ValueError):
        Event(
            person="",
            title="Meeting",
            start=datetime(2026, 10, 20, 9, 0),
            end=datetime(2026, 10, 20, 10, 0),
        )


def test_person_only_spaces():
    with pytest.raises(ValueError):
        Event(
            person="   ",
            title="Meeting",
            start=datetime(2026, 10, 20, 9, 0),
            end=datetime(2026, 10, 20, 10, 0),
        )


def test_missing_person():
    with pytest.raises(TypeError):
        Event(
            title="Meeting",
            start=datetime(2026, 10, 20, 9, 0),
            end=datetime(2026, 10, 20, 10, 0),
        )


def test_invalid_person_type():
    with pytest.raises(ValueError):
        Event(
            person=123,
            title="Meeting",
            start=datetime(2026, 10, 20, 9, 0),
            end=datetime(2026, 10, 20, 10, 0),
        )


# -----------------------------------------
# 3. Title validation tests
# -----------------------------------------

def test_empty_title():
    with pytest.raises(ValueError):
        Event(
            person="Sam",
            title="",
            start=datetime(2026, 10, 20, 9, 0),
            end=datetime(2026, 10, 20, 10, 0),
        )


def test_title_only_spaces():
    with pytest.raises(ValueError):
        Event(
            person="Sam",
            title="   ",
            start=datetime(2026, 10, 20, 9, 0),
            end=datetime(2026, 10, 20, 10, 0),
        )


def test_invalid_title_type():
    with pytest.raises(ValueError):
        Event(
            person="Sam",
            title=123,
            start=datetime(2026, 10, 20, 9, 0),
            end=datetime(2026, 10, 20, 10, 0),
        )


# -----------------------------------------
# 4. Invalid time tests
# -----------------------------------------

def test_invalid_start_time():
    with pytest.raises(ValueError):
        Event(
            person="Sam",
            title="Meeting",
            start="invalid time",
            end=datetime(2026, 10, 20, 10, 0),
        )


def test_invalid_end_time():
    with pytest.raises(ValueError):
        Event(
            person="Sam",
            title="Meeting",
            start=datetime(2026, 10, 20, 9, 0),
            end="invalid time",
        )


def test_missing_start_value():
    with pytest.raises(ValueError):
        Event(
            person="Sam",
            title="Meeting",
            start=None,
            end=datetime(2026, 10, 20, 10, 0),
        )


def test_missing_end_value():
    with pytest.raises(ValueError):
        Event(
            person="Sam",
            title="Meeting",
            start=datetime(2026, 10, 20, 9, 0),
            end=None,
        )


# -----------------------------------------
# 5. Meeting duration tests
# -----------------------------------------

def test_end_before_start():
    with pytest.raises(ValueError):
        Event(
            person="Sam",
            title="Meeting",
            start=datetime(2026, 10, 20, 11, 0),
            end=datetime(2026, 10, 20, 10, 0),
        )


def test_start_equals_end():
    with pytest.raises(ValueError):
        Event(
            person="Sam",
            title="Meeting",
            start=datetime(2026, 10, 20, 10, 0),
            end=datetime(2026, 10, 20, 10, 0),
        )


def test_end_date_before_start_date():
    with pytest.raises(ValueError):
        Event(
            person="Sam",
            title="Meeting",
            start=datetime(2026, 11, 15, 9, 0),
            end=datetime(2026, 11, 14, 10, 0),
        )


# -----------------------------------------
# 6. Calendar edge-case tests
# -----------------------------------------

def test_back_to_back_meetings():
    first = Event(
        person="Sam",
        title="Meeting 1",
        start=datetime(2026, 10, 20, 9, 0),
        end=datetime(2026, 10, 20, 10, 0),
    )

    second = Event(
        person="Sam",
        title="Meeting 2",
        start=datetime(2026, 10, 20, 10, 0),
        end=datetime(2026, 10, 20, 11, 0),
    )

    assert first.end == second.start


def test_double_booking_events_are_allowed():
    first = Event(
        person="Sam",
        title="Meeting 1",
        start=datetime(2026, 10, 20, 9, 0),
        end=datetime(2026, 10, 20, 10, 0),
    )

    second = Event(
        person="Sam",
        title="Meeting 2",
        start=datetime(2026, 10, 20, 9, 30),
        end=datetime(2026, 10, 20, 10, 30),
    )

    assert first.start < second.end
    assert second.start < first.end


def test_event_outside_working_hours():
    event = Event(
        person="Sam",
        title="Early Meeting",
        start=datetime(2026, 10, 20, 8, 0),
        end=datetime(2026, 10, 20, 9, 0),
    )

    assert event.start.hour == 8


def test_event_at_non_15_minute_time():
    event = Event(
        person="Sam",
        title="Existing Meeting",
        start=datetime(2026, 10, 20, 9, 10),
        end=datetime(2026, 10, 20, 9, 40),
    )

    assert event.start.minute == 10


# -----------------------------------------
# 7. Time-zone validation tests
# -----------------------------------------

def test_timezone_aware_start_rejected():
    with pytest.raises(ValueError):
        Event(
            person="Sam",
            title="Meeting",
            start=datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc),
            end=datetime(2026, 10, 20, 10, 0),
        )


def test_timezone_aware_end_rejected():
    with pytest.raises(ValueError):
        Event(
            person="Sam",
            title="Meeting",
            start=datetime(2026, 10, 20, 9, 0),
            end=datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc),
        )
