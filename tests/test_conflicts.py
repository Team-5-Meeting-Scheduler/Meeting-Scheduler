"""Tests for scheduler.conflicts. Owner: Tejdeep."""

from datetime import datetime

import pytest

from scheduler.conflicts import (
    Conflict,
    events_overlap,
    find_conflicts,
    get_busy_intervals,
)
from scheduler.models import Event


def at(clock: str) -> datetime:
    return datetime.fromisoformat(f"2026-10-23T{clock}")


def event(
    start: str, end: str, person: str = "Sam", title: str = "Meeting"
) -> Event:
    return Event(person=person, title=title, start=at(start), end=at(end))


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


def test_conflict_returns_person_titles_and_exact_overlap_without_printing(capsys):
    standup = event("09:00", "10:00", title="Standup")
    client = event("09:30", "10:30", title="Client Meeting")
    lunch = event("12:00", "13:00", title="Lunch")

    conflicts = find_conflicts([client, lunch, standup])

    assert conflicts == [Conflict("Sam", standup, client, at("09:30"), at("10:00"))]
    assert conflicts[0].event_a.title == "Standup"
    assert conflicts[0].event_b.title == "Client Meeting"
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    "events",
    [
        [],
        [event("09:00", "10:00")],
        [event("09:00", "10:00"), event("10:00", "11:00")],
        [event("09:00", "10:00"), event("11:00", "12:00")],
    ],
    ids=["empty", "single", "back-to-back", "separated"],
)
def test_calendars_without_conflicts(events):
    assert find_conflicts(events) == []


def test_different_people_are_busy_without_being_double_booked():
    events = [
        event("09:00", "10:00", person="Sam"),
        event("09:30", "10:30", person="Priya"),
    ]

    assert find_conflicts(events) == []
    assert get_busy_intervals(events, ["Sam", "Priya"]) == [
        (at("09:00"), at("10:30"))
    ]


def test_multiple_people_have_independent_conflicts_in_deterministic_order():
    sam_a = event("09:00", "10:00", title="Sam A")
    sam_b = event("09:30", "10:30", title="Sam B")
    priya_a = event("09:00", "10:00", person="Priya", title="Priya A")
    priya_b = event("09:30", "10:30", person="Priya", title="Priya B")

    conflicts = find_conflicts([sam_b, priya_b, sam_a, priya_a])

    assert conflicts == [
        Conflict("Priya", priya_a, priya_b, at("09:30"), at("10:00")),
        Conflict("Sam", sam_a, sam_b, at("09:30"), at("10:00")),
    ]


def test_nested_events_report_every_pair_once_even_after_a_short_event_ends():
    long = event("09:00", "14:00", title="Long")
    middle = event("09:30", "11:00", title="Middle")
    last = event("10:30", "12:00", title="Last")
    later = event("12:00", "13:00", title="Later")

    conflicts = find_conflicts([last, long, middle, later])

    assert conflicts == [
        Conflict("Sam", long, middle, at("09:30"), at("11:00")),
        Conflict("Sam", long, last, at("10:30"), at("12:00")),
        Conflict("Sam", long, later, at("12:00"), at("13:00")),
        Conflict("Sam", middle, last, at("10:30"), at("11:00")),
    ]


def test_identical_records_are_reported_as_one_overlapping_pair():
    first = event("09:00", "10:00")
    second = event("09:00", "10:00")

    conflicts = find_conflicts([first, second])

    assert conflicts == [Conflict("Sam", first, second, at("09:00"), at("10:00"))]
    assert conflicts[0].event_a is first
    assert conflicts[0].event_b is second


def test_conflicts_use_full_dates_including_overnight_events():
    overnight = Event("Sam", "Late", at("23:30"), datetime(2026, 10, 24, 0, 30))
    next_day = Event(
        "Sam", "Early", datetime(2026, 10, 24, 0, 15), datetime(2026, 10, 24, 1)
    )
    following_day = Event(
        "Sam", "Following", datetime(2026, 10, 25, 0), datetime(2026, 10, 25, 1)
    )

    assert find_conflicts([following_day, next_day, overnight]) == [
        Conflict(
            "Sam", overnight, next_day,
            datetime(2026, 10, 24, 0, 15), datetime(2026, 10, 24, 0, 30),
        )
    ]


@pytest.mark.parametrize("participants", [[], ["Unknown"]])
def test_busy_intervals_for_no_selected_people(participants):
    assert get_busy_intervals([event("09:00", "10:00")], participants) == []


def test_empty_busy_calendar():
    assert get_busy_intervals([], ["Sam"]) == []


def test_single_busy_event():
    assert get_busy_intervals([event("09:00", "10:00")], ["Sam"]) == [
        (at("09:00"), at("10:00"))
    ]


def test_busy_union_filters_people_and_merges_touching_nested_and_duplicate_times():
    events = [
        event("14:00", "15:00"),
        event("10:00", "11:00", person="Priya"),
        event("08:00", "17:00", person="Alex"),
        event("09:00", "10:00"),
        event("09:00", "10:00"),
        event("09:15", "09:30"),
        event("10:30", "12:00", person="Priya"),
    ]

    assert get_busy_intervals(events, ["Sam", "Priya", "Sam"]) == [
        (at("09:00"), at("12:00")),
        (at("14:00"), at("15:00")),
    ]


def test_busy_intervals_retain_full_dates_without_clipping_to_working_hours():
    overnight = Event(
        "Sam", "Overnight", datetime(2026, 10, 22, 23), at("08:00")
    )
    next_day = Event(
        "Sam", "Tomorrow", datetime(2026, 10, 24, 9), datetime(2026, 10, 24, 10)
    )

    assert get_busy_intervals([next_day, overnight], ["Sam"]) == [
        (datetime(2026, 10, 22, 23), at("08:00")),
        (datetime(2026, 10, 24, 9), datetime(2026, 10, 24, 10)),
    ]


def test_conflict_detection_and_busy_union_do_not_mutate_inputs():
    events = [event("10:00", "11:00"), event("09:00", "10:30")]
    original = [(id(e), e.person, e.title, e.start, e.end) for e in events]
    participants = ["Sam", "Priya"]

    find_conflicts(events)
    get_busy_intervals(events, participants)

    assert [(id(e), e.person, e.title, e.start, e.end) for e in events] == original
    assert participants == ["Sam", "Priya"]
