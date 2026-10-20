"""Reusable scheduling constraints. Owner: Tejdeep.

Candidates use timezone-naive datetimes in the same agreed time zone as Event.
The slot finder must pass validated events for only the selected participants.
Invalid candidates return False; invalid rule configuration raises ValueError.
Combine rules with all(rule.is_satisfied(start, end, events) for rule in rules).
"""

from abc import ABC, abstractmethod
from datetime import datetime, time, timedelta

from scheduler.models import Event


def _is_valid_slot(start: datetime, end: datetime) -> bool:
    """Require timezone-naive datetime boundaries and a positive duration."""
    return (
        isinstance(start, datetime)
        and isinstance(end, datetime)
        and start.utcoffset() is None
        and end.utcoffset() is None
        and start < end
    )


class SchedulingRule(ABC):
    """A constraint that can be evaluated for any proposed meeting slot."""

    @abstractmethod
    def is_satisfied(
        self,
        proposed_start: datetime,
        proposed_end: datetime,
        existing_events: list[Event],
    ) -> bool:
        """Return whether the candidate satisfies this rule, without mutation.

        Implementations must return False for invalid candidates, including
        nonpositive duration and timezone-aware boundaries.
        """


class WorkingHoursRule(SchedulingRule):
    """Require a meeting to fit within one day's working hours.

    Default boundaries are 09:00 and 17:00; starting at opening or ending at
    closing is allowed. Overnight working hours are unsupported. Evaluation
    takes O(1) time and space, independently of existing events.
    """

    def __init__(
        self, working_start: time = time(9), working_end: time = time(17)
    ) -> None:
        if (
            not isinstance(working_start, time)
            or not isinstance(working_end, time)
            or working_start.tzinfo is not None
            or working_end.tzinfo is not None
            or working_start >= working_end
        ):
            raise ValueError(
                "Working hours must be timezone-naive times with start before end."
            )
        self.working_start = working_start
        self.working_end = working_end

    def is_satisfied(
        self,
        proposed_start: datetime,
        proposed_end: datetime,
        existing_events: list[Event],
    ) -> bool:
        if not _is_valid_slot(proposed_start, proposed_end):
            return False
        return (
            proposed_start.date() == proposed_end.date()
            and self.working_start <= proposed_start.time()
            and proposed_end.time() <= self.working_end
        )


class MinimumGapRule(SchedulingRule):
    """Require a configurable timedelta gap before or after every event.

    The default zero gap permits back-to-back meetings but rejects overlaps.
    A gap exactly equal to the minimum is allowed. Evaluation takes O(n) time
    and O(1) space for n existing events. This rule does not set working hours.
    """

    def __init__(self, minimum_gap: timedelta = timedelta(0)) -> None:
        if not isinstance(minimum_gap, timedelta) or minimum_gap < timedelta(0):
            raise ValueError("Minimum gap must be a nonnegative timedelta.")
        self.minimum_gap = minimum_gap

    def is_satisfied(
        self,
        proposed_start: datetime,
        proposed_end: datetime,
        existing_events: list[Event],
    ) -> bool:
        if not _is_valid_slot(proposed_start, proposed_end):
            return False
        return all(
            event.start - proposed_end >= self.minimum_gap
            or proposed_start - event.end >= self.minimum_gap
            for event in existing_events
        )
