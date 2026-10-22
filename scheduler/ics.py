"""Convert basic iCalendar VEVENTs to the shared, timezone-naive Event model."""

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from icalendar import Calendar
from icalendar.cal import Component

from scheduler.models import Event


def parse_ics_events(
    content: str, person: str, *, local_timezone: str | None = None
) -> list[Event]:
    """Parse one person's calendar, failing rather than returning partial data.

    SUMMARY maps to title. Floating times already represent the team's local
    time; UTC/TZID times require local_timezone and are converted before their
    tzinfo is removed. DATE events become midnight-to-midnight intervals, with
    an exclusive DTEND (one day by default). Person is the calendar owner, not
    its organizer or attendees. Recurrence and DURATION are unsupported.
    Cancelled and transparent events do not occupy time and are skipped.
    """
    if not isinstance(person, str) or not person.strip():
        raise ValueError("Person must be a non-empty string.")
    target_zone = None
    if local_timezone is not None:
        try:
            target_zone = ZoneInfo(local_timezone)
        except (ZoneInfoNotFoundError, ValueError, TypeError) as error:
            raise ValueError(f"Unknown local time zone: {local_timezone!r}.") from error

    try:
        calendar = Calendar.from_ical(content)
    except (ValueError, TypeError) as error:
        raise ValueError(f"Malformed ICS: {error}") from error
    if calendar.name != "VCALENDAR":
        raise ValueError("ICS must contain one VCALENDAR component.")
    if calendar.errors:
        raise ValueError(f"Malformed ICS: {calendar.errors}")

    events: list[Event] = []
    for index, component in enumerate(calendar.walk("VEVENT"), start=1):
        try:
            if component.errors:
                raise ValueError(f"Invalid properties: {component.errors}")
            if any(
                name in component
                for name in ("RRULE", "RDATE", "EXDATE", "EXRULE", "RECURRENCE-ID")
            ):
                raise ValueError("Recurring events are not supported.")
            if "DURATION" in component:
                raise ValueError("DURATION is not supported; supply DTEND instead.")
            if str(component.get("STATUS", "")).upper() == "CANCELLED":
                continue
            if str(component.get("TRANSP", "")).upper() == "TRANSPARENT":
                continue
            summary = _single_property(component, "SUMMARY")
            start = _event_time(component, "DTSTART")
            if "DTEND" in component:
                end = _event_time(component, "DTEND")
            elif type(start) is date:
                end = start + timedelta(days=1)
            else:
                raise ValueError("Missing DTEND for a timed event.")
            if type(start) is not type(end):
                raise ValueError("DTSTART and DTEND must both be DATE or DATE-TIME.")
            if isinstance(start, datetime) and (
                (start.utcoffset() is None) != (end.utcoffset() is None)
            ):
                raise ValueError("DTSTART and DTEND must use consistent time zones.")
            events.append(
                Event(
                    person=person,
                    title=str(summary),
                    start=_local_datetime(start, target_zone),
                    end=_local_datetime(end, target_zone),
                )
            )
        except (ValueError, TypeError, OverflowError) as error:
            raise ValueError(f"Invalid VEVENT {index}: {error}") from error
    return events


def _single_property(component: Component, name: str) -> Any:
    value = component.get(name)
    if value is None:
        raise ValueError(f"Missing {name}.")
    if isinstance(value, list):
        raise ValueError(f"Duplicate {name} properties.")
    return value


def _event_time(component: Component, name: str) -> date | datetime:
    prop = _single_property(component, name)
    value = getattr(prop, "dt", None)
    if not isinstance(value, (date, datetime)):
        raise ValueError(f"Invalid {name}: expected DATE or DATE-TIME.")
    if (
        isinstance(value, datetime)
        and prop.params.get("TZID")
        and value.utcoffset() is None
    ):
        raise ValueError(f"Unresolved {name} time zone: {prop.params['TZID']}.")
    return value


def _local_datetime(value: date | datetime, zone: ZoneInfo | None) -> datetime:
    if not isinstance(value, datetime):
        return datetime.combine(value, time.min)
    if value.utcoffset() is None:
        return value
    if zone is None:
        raise ValueError("Zoned timestamps require an explicit local_timezone.")
    return value.astimezone(zone).replace(tzinfo=None)
