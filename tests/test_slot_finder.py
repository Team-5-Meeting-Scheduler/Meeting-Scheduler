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


def find(events, participants, duration=30, rules=None, known=None, meeting_date=MEETING_DATE):
    return find_available_slots(
        events,
        participants,
        meeting_date,
        duration,
        rules=rules,
        known_participants=PEOPLE if known is None else known,
    )


def shared_events():
    return [
        event("09:00", "10:00", "Sam"),
        event("13:00", "14:00", "Sam"),
        event("10:00", "11:00", "Priya"),
        event("14:00", "15:00", "Priya"),
        event("11:00", "12:00", "Alex"),
    ]


def gap_events():
    return [
        event("09:00", "12:00", "Sam"),
        event("12:30", "17:00", "Sam"),
    ]


def overlap_events():
    return [
        event("10:00", "12:00", "Sam", "A"),
        event("11:00", "13:00", "Sam", "B"),
        event("11:30", "12:30", "Priya", "C"),
    ]


def gap_rules():
    return [WorkingHoursRule(), MinimumGapRule(timedelta(minutes=15))]


def test_free_day_starts_at_opening():
    assert find([], ["Sam", "Priya", "Alex"])[0] == slot("09:00", "09:30")


def test_free_day_ends_at_closing():
    assert find([], ["Sam", "Priya", "Alex"])[-1] == slot("16:30", "17:00")


def test_free_day_slot_count_for_thirty_minutes():
    assert len(find([], ["Sam"], duration=30)) == 31


def test_free_day_slots_use_the_requested_duration():
    slots = find([], ["Sam"], duration=30)
    assert all(item.end - item.start == timedelta(minutes=30) for item in slots)


def test_busy_interval_is_not_offered():
    assert slot("09:00", "10:00") not in find([event("09:00", "10:00")], ["Sam"], duration=60)


def test_slot_can_start_when_a_meeting_ends():
    assert slot("10:00", "11:00") in find([event("09:00", "10:00")], ["Sam"], duration=60)


def test_first_slot_follows_one_participants_meeting():
    assert find([event("09:00", "10:00")], ["Sam"], duration=60)[0] == slot("10:00", "11:00")


def test_shared_gap_starts_at_noon():
    assert find(shared_events(), ["Sam", "Priya", "Alex"], duration=60)[0] == slot("12:00", "13:00")


def test_later_shared_hour_is_available():
    assert slot("15:00", "16:00") in find(shared_events(), ["Sam", "Priya", "Alex"], duration=60)


def test_sam_morning_is_not_shared():
    assert slot("09:00", "10:00") not in find(shared_events(), ["Sam", "Priya", "Alex"], duration=60)


def test_priya_morning_is_not_shared():
    assert slot("10:00", "11:00") not in find(shared_events(), ["Sam", "Priya", "Alex"], duration=60)


def test_sam_afternoon_is_not_shared():
    assert slot("13:00", "14:00") not in find(shared_events(), ["Sam", "Priya", "Alex"], duration=60)


def test_no_shared_slot_returns_empty_list():
    events = [event("09:00", "13:00", "Sam"), event("13:00", "17:00", "Priya")]
    assert find(events, ["Sam", "Priya"]) == []


def test_completely_full_working_day_returns_empty_list():
    assert find([event("09:00", "17:00")], ["Sam"], duration=15) == []


def test_back_to_back_meetings_allow_the_following_slot():
    events = [event("09:00", "10:00", "Sam"), event("10:00", "11:00", "Priya")]
    assert find(events, ["Sam", "Priya"])[0] == slot("11:00", "11:30")


def test_back_to_back_meetings_reject_an_overlapping_slot():
    events = [event("09:00", "10:00", "Sam"), event("10:00", "11:00", "Priya")]
    assert slot("09:30", "10:00") not in find(events, ["Sam", "Priya"])


def test_duration_longer_than_the_gap_returns_empty_list():
    assert find(gap_events(), ["Sam"], duration=45) == []


def test_duration_that_fits_the_gap_returns_that_slot():
    assert find(gap_events(), ["Sam"], duration=30) == [slot("12:00", "12:30")]


def test_meeting_can_start_at_opening():
    assert find([], ["Sam"], duration=15)[0] == slot("09:00", "09:15")


def test_meeting_can_end_at_closing():
    assert find([], ["Sam"])[-1] == slot("16:30", "17:00")


def test_slot_that_would_pass_closing_is_excluded():
    assert find([event("09:00", "16:00")], ["Sam"], duration=90) == []


def test_longest_free_slot_ends_at_closing():
    assert find([], ["Sam"], duration=90)[-1] == slot("15:30", "17:00")


def test_empty_known_calendars_allow_the_full_day():
    assert find([], ["Sam", "Priya"], duration=480, known={"Sam", "Priya"}) == [
        slot("09:00", "17:00")
    ]


def test_unsorted_events_return_the_same_slots():
    ordered = [event("09:00", "10:00", "Sam"), event("15:00", "16:00", "Priya")]
    assert find(ordered, ["Sam", "Priya"]) == find(list(reversed(ordered)), ["Sam", "Priya"])


def test_overlapping_busy_time_still_allows_the_opening_hour():
    assert slot("09:00", "10:00") in find(overlap_events(), ["Sam", "Priya"], duration=60)


def test_overlapping_busy_time_blocks_the_merged_interval():
    assert slot("11:00", "12:00") not in find(overlap_events(), ["Sam", "Priya"], duration=60)


def test_slot_after_merged_busy_time_is_available():
    assert slot("13:00", "14:00") in find(overlap_events(), ["Sam", "Priya"], duration=60)


def test_minimum_gap_rejects_a_touching_slot_before_the_meeting():
    assert slot("09:30", "10:00") not in find([event("10:00", "11:00")], ["Sam"], rules=gap_rules())


def test_minimum_gap_allows_an_exact_gap_before_the_meeting():
    assert slot("09:15", "09:45") in find([event("10:00", "11:00")], ["Sam"], rules=gap_rules())


def test_minimum_gap_rejects_a_touching_slot_after_the_meeting():
    assert slot("11:00", "11:30") not in find([event("10:00", "11:00")], ["Sam"], rules=gap_rules())


def test_minimum_gap_allows_an_exact_gap_after_the_meeting():
    assert slot("11:15", "11:45") in find([event("10:00", "11:00")], ["Sam"], rules=gap_rules())


def test_default_rules_allow_a_slot_that_ends_when_a_meeting_starts():
    assert slot("09:30", "10:00") in find([event("10:00", "11:00")], ["Sam"])


def test_default_rules_allow_a_slot_that_starts_when_a_meeting_ends():
    assert slot("11:00", "11:30") in find([event("10:00", "11:00")], ["Sam"])


def test_zero_duration_raises():
    with pytest.raises(ValueError, match="positive"):
        find([], ["Sam"], duration=0)


def test_negative_duration_raises():
    with pytest.raises(ValueError, match="positive"):
        find([], ["Sam"], duration=-15)


def test_boolean_duration_raises():
    with pytest.raises(ValueError, match="positive"):
        find([], ["Sam"], duration=True)


def test_empty_participant_list_raises():
    with pytest.raises(ValueError, match="participant"):
        find([], [])


def test_blank_participant_name_raises():
    with pytest.raises(ValueError, match="non-empty"):
        find([], [" "])


def test_unknown_participant_raises():
    with pytest.raises(ValueError, match="Alex"):
        find([event("09:00", "10:00", "Sam")], ["Sam", "Alex"], known={"Sam"})


def test_unknown_participant_raises_when_known_set_is_omitted():
    with pytest.raises(ValueError, match="Alex"):
        find_available_slots(
            [event("09:00", "10:00", "Sam")],
            ["Alex"],
            MEETING_DATE,
            30,
        )


def test_all_attendees_must_be_free_for_a_shared_slot():
    events = [
        event("09:00", "09:30", "Sam"),
        event("09:15", "09:45", "Priya"),
    ]
    assert slot("09:00", "09:30") not in find(events, ["Sam", "Priya"])


def test_shared_slot_exists_when_every_attendee_is_free():
    events = [
        event("09:00", "09:30", "Sam"),
        event("09:15", "09:45", "Priya"),
    ]
    assert slot("09:45", "10:15") in find(events, ["Sam", "Priya"])


def test_slot_starting_before_opening_is_never_returned():
    slots = find([], ["Sam"], duration=30)
    assert all(item.start.time() >= at("09:00").time() for item in slots)


def test_slot_ending_after_closing_is_never_returned():
    slots = find([], ["Sam"], duration=30)
    assert all(item.end.time() <= at("17:00").time() for item in slots)


def test_datetime_meeting_date_raises():
    with pytest.raises(ValueError, match="calendar date"):
        find([], ["Sam"], meeting_date=at("09:00"))


def test_non_event_entry_raises():
    with pytest.raises(TypeError, match="Event"):
        find(["09:00-10:00"], ["Sam"])


def test_non_rule_entry_raises():
    with pytest.raises(TypeError, match="SchedulingRule"):
        find([], ["Sam"], rules=["working hours"])


def test_known_participants_must_be_a_set():
    with pytest.raises(TypeError, match="Known participants"):
        find([], ["Sam"], known=["Sam"])


def test_participant_order_does_not_change_slots():
    events = [event("12:00", "13:00", "Priya"), event("09:00", "09:30", "Alex")]
    assert find(events, ["Alex", "Priya", "Sam"]) == find(events, ["Sam", "Priya", "Alex"])


def test_slots_are_chronological():
    events = [event("12:00", "13:00", "Priya"), event("09:00", "09:30", "Alex")]
    slots = find(events, ["Sam", "Priya", "Alex"])
    assert slots == sorted(slots, key=lambda item: item.start)


def test_slot_starts_are_on_fifteen_minute_boundaries():
    slots = find([event("09:07", "09:20")], ["Sam"], duration=15)
    assert all(item.start.minute % 15 == 0 and item.start.second == 0 for item in slots)


def test_events_on_another_day_do_not_block_the_requested_date():
    other = event("09:00", "17:00", "Sam", day=date(2026, 10, 24))
    assert find([other], ["Sam"])[0] == slot("09:00", "09:30")


def test_unselected_person_does_not_block_the_slot():
    assert slot("09:00", "09:30") in find([event("09:00", "10:00", "Priya")], ["Sam"])


def test_duplicate_participant_names_are_ignored():
    assert find([event("10:00", "11:00")], ["Sam", "Sam"]) == find(
        [event("10:00", "11:00")], ["Sam"]
    )
