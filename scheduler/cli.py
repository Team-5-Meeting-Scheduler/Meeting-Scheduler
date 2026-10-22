"""Command-line entry point. Owner: Vedanshu.

Loads calendars, detects conflicts, finds shared free slots, and writes a report.
Expected failures print Error: ... and exit with status 2.

Typed flags are the default path and work without an API key. Optional
--request uses an LLM only to convert natural language into those same fields.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from scheduler.conflicts import find_conflicts
from scheduler.loaders import load_calendars
from scheduler.models import Event
from scheduler.nl_parser import (
    filter_slots_by_time_preference,
    parse_natural_language_request,
)
from scheduler.reporting import format_report, write_report
from scheduler.rules import MinimumGapRule, WorkingHoursRule
from scheduler.slot_finder import find_available_slots


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and run the scheduling workflow."""
    args = parse_args(argv)
    try:
        run(args)
    except (ValueError, TypeError, OSError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(2) from None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Build and parse the CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="python -m scheduler",
        description=(
            "Find a meeting time that works across participant calendars "
            "and write a conflict and availability report."
        ),
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing JSON, CSV, or ICS calendar files.",
    )
    parser.add_argument(
        "--timezone",
        help="Agreed IANA time zone for zoned ICS import, e.g. America/New_York.",
    )
    parser.add_argument(
        "--request",
        help=(
            "Natural-language scheduling request. Requires an API key. "
            "When set, --date, --participants, and --duration are optional."
        ),
    )
    parser.add_argument(
        "--date",
        type=_parse_date,
        help="Requested meeting date as YYYY-MM-DD.",
    )
    parser.add_argument(
        "--participants",
        nargs="+",
        help="Employees attending the meeting.",
    )
    parser.add_argument(
        "--duration",
        type=_parse_duration,
        help="Meeting length in minutes.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Destination path for the generated report.",
    )
    args = parser.parse_args(argv)
    _validate_mode(args, parser)
    return args


def run(args: argparse.Namespace) -> None:
    """Execute loading, conflict detection, slot finding, and reporting."""
    events, known_participants = _load_input_directory(
        Path(args.input_dir), local_timezone=args.timezone
    )
    meeting_date, participants, duration, time_preference = _resolve_request(
        args, known_participants
    )

    slots = find_available_slots(
        events,
        participants,
        meeting_date,
        duration,
        rules=[WorkingHoursRule(), MinimumGapRule()],
        known_participants=known_participants,
    )
    slots = filter_slots_by_time_preference(slots, time_preference)
    selected = set(participants)
    conflicts = [
        conflict
        for conflict in find_conflicts(events)
        if conflict.person in selected
    ]
    report = format_report(
        meeting_date,
        participants,
        duration,
        conflicts,
        slots,
    )
    write_report(report, args.output)
    print(f"Report written to {args.output}")


def _validate_mode(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.request:
        return
    missing = []
    if args.date is None:
        missing.append("--date")
    if not args.participants:
        missing.append("--participants")
    if args.duration is None:
        missing.append("--duration")
    if missing:
        parser.error(
            "the following arguments are required unless --request is used: "
            + ", ".join(missing)
        )


def _resolve_request(
    args: argparse.Namespace, known_participants: set[str]
) -> tuple[date, list[str], int, str | None]:
    if not args.request:
        return (
            args.date,
            list(dict.fromkeys(args.participants)),
            args.duration,
            None,
        )

    parsed = parse_natural_language_request(
        args.request,
        known_participants=known_participants,
    )
    participants = (
        list(dict.fromkeys(args.participants))
        if args.participants
        else parsed.participants
    )
    meeting_date = args.date or parsed.meeting_date
    duration = args.duration if args.duration is not None else parsed.duration_minutes
    print(
        "Parsed request: "
        f"date={meeting_date.isoformat()}, "
        f"participants={', '.join(participants)}, "
        f"duration={duration} minutes"
        + (
            f", time_preference={parsed.time_preference}"
            if parsed.time_preference
            else ""
        )
    )
    return meeting_date, participants, duration, parsed.time_preference


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Invalid date. Expected YYYY-MM-DD."
        ) from error


def _parse_duration(value: str) -> int:
    try:
        duration = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Meeting duration must be a positive number of minutes."
        ) from error
    if duration <= 0:
        raise argparse.ArgumentTypeError(
            "Meeting duration must be a positive number of minutes."
        )
    return duration


def _load_input_directory(
    input_dir: Path, *, local_timezone: str | None = None
) -> tuple[list[Event], set[str]]:
    """Load calendars from a directory and the set of known people."""
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: '{input_dir}'.")
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: '{input_dir}'.")

    calendar_paths = _calendar_paths(input_dir)
    if not calendar_paths:
        raise ValueError(
            f"No calendar files found in '{input_dir}'. Use .json, .csv, or .ics."
        )

    events: list[Event] = []
    known_participants: set[str] = set()
    for path in calendar_paths:
        file_events = load_calendars([path], local_timezone=local_timezone)
        events.extend(file_events)
        if file_events:
            known_participants.update(event.person for event in file_events)
        else:
            known_participants.add(_person_from_stem(path.stem))
    return events, known_participants


def _calendar_paths(input_dir: Path) -> list[Path]:
    """Return calendars once per stem, preferring JSON, then CSV, then ICS."""
    json_files = {path.stem: path for path in sorted(input_dir.glob("*.json"))}
    csv_files = {path.stem: path for path in sorted(input_dir.glob("*.csv"))}
    ics_files = {
        path.stem: path for path in sorted(input_dir.iterdir())
        if path.is_file() and path.suffix.lower() == ".ics"
    }
    paths: list[Path] = []
    for stem in sorted(set(json_files) | set(csv_files) | set(ics_files)):
        if stem in json_files:
            paths.append(json_files[stem])
        elif stem in csv_files:
            paths.append(csv_files[stem])
        else:
            paths.append(ics_files[stem])
    return paths


def _person_from_stem(stem: str) -> str:
    """Map an empty calendar filename to a person name."""
    if not stem:
        return stem
    return stem[0].upper() + stem[1:]
