"""Tests for scheduler.conflicts. Owner: Tejdeep."""

from datetime import datetime

import pytest

from scheduler.conflicts import events_overlap
from scheduler.models import Event


def at(clock: str) -> datetime:
    return datetime.fromisoformat(f"2026-10-23T{clock}")


def event(start: str, end: str, person: str = "Sam") -> Event:
    return Event(person=person, title="Meeting", start=at(start), end=at(end))


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        (("09:00", "10:00"), ("11:00", "12:00"), False),
        (("09:00", "10:00"), ("09:30", "10:30"), True),
        (("09:00", "12:00"), ("10:00", "11:00"), True),
        (("09:00", "10:00"), ("09:00", "10:00"), True),
        (("09:00", "10:00"), ("10:00", "11:00"), False),
        (("09:00", "10:00"), ("09:00", "09:30"), True),
        (("09:00", "10:00"), ("09:30", "10:00"), True),
        (("09:00", "10:00:01"), ("10:00", "11:00"), True),
    ],
    ids=[
        "no-overlap", "partial-overlap", "containment", "identical-times",
        "back-to-back", "shared-start", "shared-end", "one-second-overlap",
    ],
)
def test_overlap_is_symmetric(first, second, expected):
    first_event, second_event = event(*first), event(*second)

    assert events_overlap(first_event, second_event) is expected
    assert events_overlap(second_event, first_event) is expected


def test_overlap_uses_full_dates_across_midnight():
    overnight = Event("Sam", "Late", at("23:30"), datetime(2026, 10, 24, 0, 30))
    next_day = Event(
        "Sam", "Early", datetime(2026, 10, 24, 0, 15), datetime(2026, 10, 24, 1)
    )

    assert events_overlap(overnight, next_day)


def test_same_clock_times_on_different_days_do_not_overlap():
    today = event("09:00", "10:00")
    tomorrow = Event(
        "Sam", "Tomorrow", datetime(2026, 10, 24, 9), datetime(2026, 10, 24, 10)
    )

    assert not events_overlap(today, tomorrow)


def test_overlap_is_independent_of_person():
    sam = event("09:00", "10:00")
    priya = event("09:30", "10:30", person="Priya")

    assert events_overlap(sam, priya)
