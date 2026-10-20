"""Tests for scheduler.slot_finder. Owner: Vedanshu."""

from datetime import date, datetime, timedelta

import pytest

from scheduler.models import Event
from scheduler.rules import MinimumGapRule, WorkingHoursRule
from scheduler.slot_finder import TimeSlot, find_available_slots

MEETING_DATE = date(2026, 10, 23)
PEOPLE = {"Sam", "Priya", "Alex"}


def at(clock: str, day: date = MEETING_DATE) -> datetime:
    return datetime.fromisoformat(f"{day.isoformat()}T{clock}")


def event(
    start: str,
    end: str,
    person: str = "Sam",
    title: str = "Meeting",
    day: date = MEETING_DATE,
) -> Event:
    return Event(person=person, title=title, start=at(start, day), end=at(end, day))


def slot(start: str, end: str) -> TimeSlot:
    return TimeSlot(start=at(start), end=at(end))


def find(events, participants, duration=30, rules=None, known=None):
    return find_available_slots(
        events,
        participants,
        MEETING_DATE,
        duration,
        rules=rules,
        known_participants=PEOPLE if known is None else known,
    )


def test_all_participants_free_covers_the_working_day():
    slots = find([], ["Sam", "Priya", "Alex"], duration=30)
    assert slots[0] == slot("09:00", "09:30")
    assert slots[-1] == slot("16:30", "17:00")
    assert all(
        current.end - current.start == timedelta(minutes=30) for current in slots
    )
    assert len(slots) == 31


def test_one_participant_meeting_blocks_that_interval():
    slots = find([event("09:00", "10:00")], ["Sam"], duration=60)
    assert slot("09:00", "10:00") not in slots
    assert slot("10:00", "11:00") in slots
    assert slots[0] == slot("10:00", "11:00")


def test_different_busy_intervals_require_everyone_free():
    events = [
        event("09:00", "10:00", "Sam"),
        event("13:00", "14:00", "Sam"),
        event("10:00", "11:00", "Priya"),
        event("14:00", "15:00", "Priya"),
        event("11:00", "12:00", "Alex"),
    ]
    slots = find(events, ["Sam", "Priya", "Alex"], duration=60)
    assert slots[0] == slot("12:00", "13:00")
    assert slot("15:00", "16:00") in slots
    assert slot("09:00", "10:00") not in slots
    assert slot("10:00", "11:00") not in slots
    assert slot("13:00", "14:00") not in slots


def test_no_shared_slot_returns_empty_list():
    events = [
        event("09:00", "13:00", "Sam"),
        event("13:00", "17:00", "Priya"),
    ]
    assert find(events, ["Sam", "Priya"], duration=30) == []


def test_completely_full_working_day():
    assert find([event("09:00", "17:00")], ["Sam"], duration=15) == []


def test_back_to_back_meetings_allow_a_touching_slot():
    events = [
        event("09:00", "10:00", "Sam"),
        event("10:00", "11:00", "Priya"),
    ]
    slots = find(events, ["Sam", "Priya"], duration=30)
    assert slots[0] == slot("11:00", "11:30")
    assert slot("09:30", "10:00") not in slots


def test_duration_longer_than_the_gap_is_rejected():
    events = [
        event("09:00", "12:00", "Sam"),
        event("12:30", "17:00", "Sam"),
    ]
    slots = find(events, ["Sam"], duration=45)
    assert slots == []
    shorter = find(events, ["Sam"], duration=30)
    assert shorter == [slot("12:00", "12:30")]


def test_meeting_can_start_at_opening():
    slots = find([], ["Sam"], duration=15)
    assert slots[0] == slot("09:00", "09:15")


def test_meeting_can_end_at_closing():
    slots = find([], ["Sam"], duration=30)
    assert slots[-1] == slot("16:30", "17:00")


def test_meeting_that_would_pass_closing_is_excluded():
    slots = find([event("09:00", "16:00")], ["Sam"], duration=90)
    assert slots == []
    assert all(item.end <= at("17:00") for item in find([], ["Sam"], duration=90))


def test_empty_calendars_are_free_when_people_are_known():
    slots = find([], ["Sam", "Priya"], duration=480, known={"Sam", "Priya"})
    assert slots == [slot("09:00", "17:00")]


def test_unsorted_events_do_not_change_results():
    ordered = [
        event("09:00", "10:00", "Sam", "Standup"),
        event("15:00", "16:00", "Priya", "Review"),
    ]
    shuffled = list(reversed(ordered))
    assert find(ordered, ["Sam", "Priya"]) == find(shuffled, ["Sam", "Priya"])


def test_overlapping_busy_intervals_are_merged():
    events = [
        event("10:00", "12:00", "Sam", "A"),
        event("11:00", "13:00", "Sam", "B"),
        event("11:30", "12:30", "Priya", "C"),
    ]
    slots = find(events, ["Sam", "Priya"], duration=60)
    assert slot("09:00", "10:00") in slots
    assert slot("10:00", "11:00") not in slots
    assert slot("12:00", "13:00") not in slots
    assert slots[0] == slot("09:00", "10:00")
    assert slot("13:00", "14:00") in slots


def test_nonzero_minimum_gap_blocks_nearby_slots():
    rules = [WorkingHoursRule(), MinimumGapRule(timedelta(minutes=15))]
    slots = find(
        [event("10:00", "11:00")],
        ["Sam"],
        duration=30,
        rules=rules,
    )
    assert slot("09:30", "10:00") not in slots
    assert slot("09:15", "09:45") in slots
    assert slot("09:00", "09:30") in slots
    assert slot("11:00", "11:30") not in slots
    assert slot("11:15", "11:45") in slots


def test_default_rules_allow_back_to_back():
    slots = find([event("10:00", "11:00")], ["Sam"], duration=30, rules=None)
    assert slot("09:30", "10:00") in slots
    assert slot("11:00", "11:30") in slots


def test_invalid_duration_raises():
    with pytest.raises(ValueError, match="positive"):
        find([], ["Sam"], duration=0)
    with pytest.raises(ValueError, match="positive"):
        find([], ["Sam"], duration=-15)


def test_unknown_participant_raises():
    with pytest.raises(ValueError, match="Alex"):
        find([event("09:00", "10:00", "Sam")], ["Sam", "Alex"], known={"Sam"})


def test_slots_are_ordered_and_repeatable():
    events = [event("12:00", "13:00", "Priya"), event("09:00", "09:30", "Alex")]
    first = find(events, ["Alex", "Priya", "Sam"])
    second = find(events, ["Sam", "Priya", "Alex"])
    assert first == second
    assert first == sorted(first, key=lambda item: item.start)
    assert all(
        item.start.minute % 15 == 0 and item.start.second == 0 for item in first
    )


def test_events_on_another_day_are_ignored():
    other = event("09:00", "17:00", "Sam", day=date(2026, 10, 24))
    slots = find([other], ["Sam"], duration=30)
    assert slots[0] == slot("09:00", "09:30")
    assert len(slots) == 31
