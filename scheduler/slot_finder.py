"""Find available meeting slots. Owner: Vedanshu.

Candidates start every 15 minutes inside 09:00–17:00 on the requested date.
Busy time comes from get_busy_intervals. Working hours and gaps come from
SchedulingRule implementations. Intervals are half-open [start, end).
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from scheduler.conflicts import get_busy_intervals
from scheduler.models import Event
from scheduler.rules import MinimumGapRule, SchedulingRule, WorkingHoursRule

SLOT_INCREMENT = timedelta(minutes=15)
WORK_START = time(9, 0)
WORK_END = time(17, 0)


@dataclass(frozen=True)
class TimeSlot:
    """A half-open meeting interval [start, end) in the shared naive timezone."""

    start: datetime
    end: datetime


def find_available_slots(
    events: list[Event],
    participants: list[str],
    meeting_date: date,
    duration_minutes: int,
    rules: list[SchedulingRule] | None = None,
    known_participants: set[str] | None = None,
) -> list[TimeSlot]:
    """Return chronological slots when every participant is free.

    known_participants lists people who have a calendar, including calendars
    with no events. When omitted, only people present on events are known.
    A requested person outside that set raises ValueError instead of being
    treated as free. Duplicate participant names are ignored.

    rules defaults to WorkingHoursRule and a zero MinimumGapRule. A zero gap
    allows a meeting that only touches a busy interval. Time is O(n log n)
    to merge busy intervals plus O(c * (b + n)) to test candidates.
    """
    _require_events(events)
    _require_duration(duration_minutes)
    _require_participants(participants)
    _require_meeting_date(meeting_date)
    _require_rules(rules)
    _require_known_participants(known_participants)

    requested = list(dict.fromkeys(participants))
    known = (
        set(known_participants)
        if known_participants is not None
        else {event.person for event in events}
    )
    missing = [person for person in requested if person not in known]
    if missing:
        names = ", ".join(missing)
        raise ValueError(f"No calendar found for participant {names}.")

    active_rules = (
        [WorkingHoursRule(), MinimumGapRule()] if rules is None else list(rules)
    )
    day_start = datetime.combine(meeting_date, time.min)
    day_end = day_start + timedelta(days=1)
    requested_people = set(requested)
    day_events = [
        event
        for event in events
        if event.person in requested_people
        and event.start < day_end
        and day_start < event.end
    ]
    busy = get_busy_intervals(day_events, requested)
    duration = timedelta(minutes=duration_minutes)
    window_start = datetime.combine(meeting_date, WORK_START)
    window_end = datetime.combine(meeting_date, WORK_END)

    slots: list[TimeSlot] = []
    candidate = window_start
    while candidate + duration <= window_end:
        candidate_end = candidate + duration
        if not _overlaps_busy(candidate, candidate_end, busy) and all(
            rule.is_satisfied(candidate, candidate_end, day_events)
            for rule in active_rules
        ):
            slots.append(TimeSlot(start=candidate, end=candidate_end))
        candidate += SLOT_INCREMENT
    return slots


def _require_events(events: list[Event]) -> None:
    """Reject a non-list or non-Event collection."""
    if not isinstance(events, list):
        raise TypeError("Events must be a list.")
    if any(not isinstance(event, Event) for event in events):
        raise TypeError("Events must contain Event values.")


def _require_duration(duration_minutes: int) -> None:
    """Reject non-positive or non-integer durations."""
    if (
        isinstance(duration_minutes, bool)
        or not isinstance(duration_minutes, int)
        or duration_minutes <= 0
    ):
        raise ValueError("Meeting duration must be a positive number of minutes.")


def _require_participants(participants: list[str]) -> None:
    """Reject an empty participant list or blank names."""
    if not isinstance(participants, list) or not participants:
        raise ValueError("At least one participant is required.")
    if any(not isinstance(person, str) or not person.strip() for person in participants):
        raise ValueError("Participant names must be non-empty strings.")


def _require_meeting_date(meeting_date: date) -> None:
    """Reject values that are not a plain calendar date."""
    if type(meeting_date) is not date:
        raise ValueError("Meeting date must be a calendar date.")


def _require_rules(rules: list[SchedulingRule] | None) -> None:
    """Reject a rules argument that is not a list of SchedulingRule objects."""
    if rules is None:
        return
    if not isinstance(rules, list) or any(
        not isinstance(rule, SchedulingRule) for rule in rules
    ):
        raise TypeError("Rules must be a list of SchedulingRule objects.")


def _require_known_participants(known_participants: set[str] | None) -> None:
    """Reject a known-participant set that is not a set of non-empty names."""
    if known_participants is None:
        return
    if not isinstance(known_participants, set) or any(
        not isinstance(person, str) or not person.strip() for person in known_participants
    ):
        raise TypeError("Known participants must be a set of non-empty strings.")


def _overlaps_busy(
    start: datetime,
    end: datetime,
    busy: list[tuple[datetime, datetime]],
) -> bool:
    """Half-open overlap against merged busy intervals. Touching is allowed."""
    return any(start < busy_end and busy_start < end for busy_start, busy_end in busy)
