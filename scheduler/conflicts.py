"""Detect overlapping events. Owner: Tejdeep.

Intervals are half-open [start, end). Events use the shared model's
timezone-naive datetimes in the team's agreed local time zone.
"""

from scheduler.models import Event


def events_overlap(event_a: Event, event_b: Event) -> bool:
    """Return whether two validated events overlap, regardless of person.

    Events that only touch at an endpoint do not overlap. Time and space
    complexity are O(1). This function does not modify either event.
    """
    return event_a.start < event_b.end and event_b.start < event_a.end
