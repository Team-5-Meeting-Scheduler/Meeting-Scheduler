"""Tests for scheduler.rules. Owner: Tejdeep."""

from datetime import datetime, time, timedelta, timezone

import pytest

from scheduler.models import Event
from scheduler.rules import MinimumGapRule, SchedulingRule, WorkingHoursRule


def at(clock: str) -> datetime:
    return datetime.fromisoformat(f"2026-10-23T{clock}")


@pytest.fixture
def existing_events():
    return [Event("Sam", "Existing meeting", at("10:00"), at("11:00"))]


def test_base_rule_cannot_be_instantiated():
    with pytest.raises(TypeError):
        SchedulingRule()


def test_subclass_must_implement_the_rule_interface():
    class IncompleteRule(SchedulingRule):
        pass

    with pytest.raises(TypeError):
        IncompleteRule()


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("09:00", "09:30", True),
        ("16:30", "17:00", True),
        ("09:00", "17:00", True),
        ("16:45", "17:15", False),
        ("08:30", "09:00", False),
        ("17:00", "17:30", False),
        ("08:59:59", "09:30", False),
        ("16:30", "17:00:01", False),
        ("09:07", "09:37", True),
    ],
)
def test_working_hours_boundaries(start, end, expected):
    assert WorkingHoursRule().is_satisfied(at(start), at(end), []) is expected


def test_working_hours_can_be_configured():
    rule = WorkingHoursRule(working_start=time(8, 30), working_end=time(16, 30))

    assert rule.is_satisfied(at("08:30"), at("16:30"), [])
    assert not rule.is_satisfied(at("16:00"), at("17:00"), [])


def test_working_hours_rejects_multiple_days_even_with_valid_clock_times():
    assert not WorkingHoursRule().is_satisfied(
        at("09:00"), datetime(2026, 10, 24, 10), []
    )


def test_working_hours_does_not_check_existing_meeting_conflicts(existing_events):
    assert WorkingHoursRule().is_satisfied(at("10:15"), at("10:45"), existing_events)


@pytest.mark.parametrize(
    ("working_start", "working_end"),
    [
        (time(17), time(9)),
        (time(9), time(9)),
        ("09:00", time(17)),
        (time(9), None),
        (time(9, tzinfo=timezone.utc), time(17)),
        (time(9), time(17, tzinfo=timezone.utc)),
    ],
)
def test_invalid_working_hours_raise_clear_errors(working_start, working_end):
    with pytest.raises(ValueError, match="Working hours"):
        WorkingHoursRule(working_start, working_end)


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("09:30", "10:00", True),
        ("11:00", "11:30", True),
        ("09:30", "10:01", False),
        ("10:59", "11:30", False),
        ("10:15", "10:45", False),
        ("09:00", "12:00", False),
        ("10:00", "11:00", False),
    ],
)
def test_default_gap_allows_touching_but_rejects_overlap(
    start, end, expected, existing_events
):
    rule = MinimumGapRule()

    assert rule.is_satisfied(at(start), at(end), existing_events) is expected


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("11:00", "11:30", False),
        ("11:14:59", "11:45", False),
        ("11:15", "11:45", True),
        ("11:16", "11:45", True),
        ("09:00", "09:45", True),
        ("09:00", "09:45:01", False),
        ("09:00", "10:00", False),
        ("10:15", "10:45", False),
        ("09:00", "12:00", False),
    ],
)
def test_positive_gap_is_enforced_on_both_sides(start, end, expected, existing_events):
    rule = MinimumGapRule(minimum_gap=timedelta(minutes=15))

    assert rule.is_satisfied(at(start), at(end), existing_events) is expected


def test_gap_checks_all_selected_participants_events_in_unsorted_order(existing_events):
    later = Event("Priya", "Later", at("12:00"), at("13:00"))
    events = [later, *existing_events]
    rule = MinimumGapRule(timedelta(minutes=15))

    assert rule.is_satisfied(at("11:15"), at("11:45"), events)
    assert not rule.is_satisfied(at("11:15"), at("11:46"), events)
    assert not rule.is_satisfied(at("11:14"), at("11:45"), events)


def test_gap_uses_full_dates_across_midnight():
    previous_day = Event(
        "Sam", "Late", datetime(2026, 10, 22, 23), datetime(2026, 10, 22, 23, 55)
    )
    rule = MinimumGapRule(timedelta(minutes=15))

    assert not rule.is_satisfied(at("00:05"), at("00:30"), [previous_day])
    assert rule.is_satisfied(at("00:10"), at("00:30"), [previous_day])


def test_gap_allows_valid_slot_in_empty_calendar():
    assert MinimumGapRule(timedelta(minutes=15)).is_satisfied(
        at("09:00"), at("09:30"), []
    )


@pytest.mark.parametrize("minimum_gap", [timedelta(seconds=-1), 15, None])
def test_invalid_minimum_gap_raises_clear_error(minimum_gap):
    with pytest.raises(ValueError, match="nonnegative timedelta"):
        MinimumGapRule(minimum_gap)


@pytest.mark.parametrize("rule", [WorkingHoursRule(), MinimumGapRule()])
@pytest.mark.parametrize(
    ("start", "end"),
    [
        (at("10:00"), at("10:00")),
        (at("11:00"), at("10:00")),
        ("09:00", at("10:00")),
        (at("09:00"), None),
        (at("09:00").replace(tzinfo=timezone.utc), at("10:00")),
        (at("09:00"), at("10:00").replace(tzinfo=timezone.utc)),
        (
            at("09:00").replace(tzinfo=timezone.utc),
            at("10:00").replace(tzinfo=timezone.utc),
        ),
    ],
)
def test_invalid_candidates_return_false(rule, start, end):
    assert rule.is_satisfied(start, end, []) is False


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("11:15", "11:45", True),
        ("11:00", "11:30", False),
        ("16:45", "17:15", False),
    ],
)
def test_rules_can_be_combined_polymorphically(start, end, expected, existing_events):
    rules: list[SchedulingRule] = [
        WorkingHoursRule(),
        MinimumGapRule(timedelta(minutes=15)),
    ]

    assert all(
        rule.is_satisfied(at(start), at(end), existing_events) for rule in rules
    ) is expected


def test_new_rule_can_be_added_without_changing_existing_subclasses(existing_events):
    class ThirtyMinuteLimitRule(SchedulingRule):
        def is_satisfied(self, proposed_start, proposed_end, existing_events):
            return timedelta(0) < proposed_end - proposed_start <= timedelta(minutes=30)

    rules: list[SchedulingRule] = [
        WorkingHoursRule(), MinimumGapRule(), ThirtyMinuteLimitRule()
    ]

    assert all(
        rule.is_satisfied(at("11:00"), at("11:30"), existing_events)
        for rule in rules
    )
    assert not all(
        rule.is_satisfied(at("11:00"), at("12:00"), existing_events)
        for rule in rules
    )


def test_rules_do_not_mutate_events_or_print(existing_events, capsys):
    original = [(id(e), e.person, e.title, e.start, e.end) for e in existing_events]

    for rule in (WorkingHoursRule(), MinimumGapRule(timedelta(minutes=15))):
        assert rule.is_satisfied(at("11:15"), at("11:45"), existing_events)

    assert [(id(e), e.person, e.title, e.start, e.end) for e in existing_events] == original
    assert capsys.readouterr() == ("", "")
