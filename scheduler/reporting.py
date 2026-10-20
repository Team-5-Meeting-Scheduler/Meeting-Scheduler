"""Write scheduling reports. Owner: Vedanshu.

Formatting only. Conflicts come from find_conflicts and slots come from
find_available_slots. This module does not detect overlaps or search calendars.
"""

from datetime import date, datetime
from pathlib import Path

from scheduler.conflicts import Conflict
from scheduler.slot_finder import TimeSlot


def format_report(
    meeting_date: date,
    participants: list[str],
    duration_minutes: int,
    conflicts: list[Conflict],
    slots: list[TimeSlot],
) -> str:
    """Return a plain-text report for the office manager.

    Slots are printed in the order given. The slot finder returns them
    earliest first, so the list is the suggested meeting times.

    Raises ValueError for an invalid date, participant list, or duration.
    Raises TypeError when conflicts or slots are not the expected records.
    """
    _require_meeting_date(meeting_date)
    _require_participants(participants)
    _require_duration(duration_minutes)
    _require_records(conflicts, "Conflicts", Conflict)
    _require_records(slots, "Slots", TimeSlot)
    names = ", ".join(participants)
    lines = [
        "====================================",
        "     MEETING SCHEDULER REPORT",
        "====================================",
        "",
        f"Date: {meeting_date.isoformat()}",
        f"Participants: {names}",
        f"Duration: {duration_minutes} minutes",
        "",
        "------------------------------------",
        "CALENDAR CONFLICTS",
        "------------------------------------",
        "",
        _conflict_section(conflicts),
        "------------------------------------",
        "SUGGESTED MEETING TIMES",
        "------------------------------------",
        "",
        _slot_section(slots),
        "====================================",
        "",
    ]
    return "\n".join(lines)


def write_report(report: str, output_path: str | Path) -> None:
    """Save a formatted report, creating parent directories when needed.

    Raises ValueError when the destination is missing or is a directory.
    Raises OSError when the file cannot be written.
    """
    if not isinstance(report, str):
        raise TypeError("Report text must be a string.")
    if not isinstance(output_path, (str, Path)) or not str(output_path).strip():
        raise ValueError("Report output path is required.")
    path = Path(output_path)
    if path.is_dir():
        raise IsADirectoryError(f"Report output path is a directory: '{path}'.")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
    except OSError as error:
        raise OSError(f"Could not write report to '{path}': {error}") from error


def _require_meeting_date(meeting_date: date) -> None:
    if type(meeting_date) is not date:
        raise ValueError("Meeting date must be a calendar date.")


def _require_participants(participants: list[str]) -> None:
    if not isinstance(participants, list) or not participants:
        raise ValueError("At least one participant is required.")
    if any(not isinstance(person, str) or not person.strip() for person in participants):
        raise ValueError("Participant names must be non-empty strings.")


def _require_duration(duration_minutes: int) -> None:
    if (
        isinstance(duration_minutes, bool)
        or not isinstance(duration_minutes, int)
        or duration_minutes <= 0
    ):
        raise ValueError("Meeting duration must be a positive number of minutes.")


def _require_records(records: list, label: str, record_type: type) -> None:
    if not isinstance(records, list):
        raise TypeError(f"{label} must be a list.")
    if any(not isinstance(record, record_type) for record in records):
        raise TypeError(f"{label} must contain {record_type.__name__} values.")


def _conflict_section(conflicts: list[Conflict]) -> str:
    if not conflicts:
        return "No calendar conflicts.\n"

    grouped: dict[str, list[Conflict]] = {}
    for conflict in conflicts:
        grouped.setdefault(conflict.person, []).append(conflict)

    blocks: list[str] = []
    for person, person_conflicts in grouped.items():
        lines = [f"{person}:"]
        for conflict in person_conflicts:
            lines.append(f"  {_event_line(conflict.event_a)}")
            lines.append(f"  {_event_line(conflict.event_b)}")
            lines.append(
                "  Conflict: "
                f"{_clock(conflict.overlap_start)}-{_clock(conflict.overlap_end)}"
            )
            lines.append("")
        blocks.append("\n".join(lines).rstrip())
    return "\n\n".join(blocks) + "\n"


def _slot_section(slots: list[TimeSlot]) -> str:
    if not slots:
        return "No shared meeting time is available.\n"
    lines = [
        f"{index}. {_clock(item.start)}-{_clock(item.end)}"
        for index, item in enumerate(slots, start=1)
    ]
    return "\n".join(lines) + "\n"


def _event_line(event) -> str:
    return f"{event.title}: {_clock(event.start)}-{_clock(event.end)}"


def _clock(moment: datetime) -> str:
    return moment.strftime("%H:%M")
