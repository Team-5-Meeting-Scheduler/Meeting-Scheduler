"""Detect overlapping events, double bookings, and busy time. Owner: Tejdeep.

Intervals are half-open [start, end). Events use the shared model's
timezone-naive datetimes in the team's agreed local time zone.
"""

from dataclasses import dataclass
from datetime import datetime

from scheduler.models import Event


def events_overlap(event_a: Event, event_b: Event) -> bool:
    """Return whether two validated events overlap, regardless of person.

    Events that only touch at an endpoint do not overlap. Time and space
    complexity are O(1). This function does not modify either event.
    """
    return event_a.start < event_b.end and event_b.start < event_a.end


@dataclass(frozen=True)
class Conflict:
    """An overlapping event pair for one person, with titles on the events."""

    person: str
    event_a: Event
    event_b: Event
    overlap_start: datetime
    overlap_end: datetime


def find_conflicts(events: list[Event]) -> list[Conflict]:
    """Return each same-person overlapping pair once, without modifying input.

    Events must already satisfy model validation. Each input entry represents
    an event, so identical records are not silently discarded. Results are
    ordered by person, then by event start, end, and title.

    Sorting lets each search stop at the first later event starting at or
    after the current event's end. Time is O(n log n + k), where k is the
    number of conflicts (potentially O(n²)). Space is O(n + k).
    """
    calendars: dict[str, list[Event]] = {}
    for event in events:
        calendars.setdefault(event.person, []).append(event)

    conflicts: list[Conflict] = []
    for person in sorted(calendars):
        calendar = sorted(
            calendars[person],
            key=lambda event: (event.start, event.end, event.title),
        )
        for index, event_a in enumerate(calendar):
            for next_index in range(index + 1, len(calendar)):
                event_b = calendar[next_index]
                if event_b.start >= event_a.end:
                    break
                if events_overlap(event_a, event_b):
                    conflicts.append(
                        Conflict(
                            person=person,
                            event_a=event_a,
                            event_b=event_b,
                            overlap_start=max(event_a.start, event_b.start),
                            overlap_end=min(event_a.end, event_b.end),
                        )
                    )
    return conflicts


def get_busy_intervals(
    events: list[Event], participants: list[str]
) -> list[tuple[datetime, datetime]]:
    """Return the sorted union of busy time for the selected participants.

    Merge overlapping and touching intervals across selected people's events.
    An empty participant list selects nobody. Events must already be validated;
    input is unchanged. Returned intervals retain their full dates, without
    clipping to a day or working hours or adding gaps for scheduling rules.

    Time is O(n + p + m log m), space O(m + p), where n is the total event
    count, m is the selected event count, and p is the participant count.
    """
    selected_people = set(participants)
    intervals = sorted(
        (event.start, event.end)
        for event in events
        if event.person in selected_people
    )
    merged: list[tuple[datetime, datetime]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            previous_start, previous_end = merged[-1]
            merged[-1] = (previous_start, max(previous_end, end))
        else:
            merged.append((start, end))
    return merged
