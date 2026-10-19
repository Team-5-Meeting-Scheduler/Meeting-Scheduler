
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Event:
    person: str
    title: str
    start: datetime
    end: datetime

    def __post_init__(self):
        # Validate person
        if not isinstance(self.person, str) or not self.person.strip():
            raise ValueError("Person cannot be empty or missing.")

        # Validate title
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("Title cannot be empty or missing.")

        # Validate start time
        if not isinstance(self.start, datetime):
            raise ValueError("Start time must be a valid datetime.")

        # Validate end time
        if not isinstance(self.end, datetime):
            raise ValueError("End time must be a valid datetime.")

        # Validate the single-time-zone convention
        # Reject timezone-aware datetime values.
        if self.start.utcoffset() is not None:
            raise ValueError(
                "Start time must not contain timezone information."
            )

        if self.end.utcoffset() is not None:
            raise ValueError(
                "End time must not contain timezone information."
            )

        # Validate meeting duration
        if self.end <= self.start:
            raise ValueError(
                "End time must be later than start time."
            )
