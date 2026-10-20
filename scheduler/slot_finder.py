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
    if (
        isinstance(duration_minutes, bool)
        or not isinstance(duration_minutes, int)
        or duration_minutes <= 0
    ):
        raise ValueError("Meeting duration must be a positive number of minutes.")
    if not participants:
        raise ValueError("At least one participant is required.")

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


def _overlaps_busy(
    start: datetime,
    end: datetime,
    busy: list[tuple[datetime, datetime]],
) -> bool:
    """Half-open overlap against merged busy intervals. Touching is allowed."""
    return any(start < busy_end and busy_start < end for busy_start, busy_end in busy)
