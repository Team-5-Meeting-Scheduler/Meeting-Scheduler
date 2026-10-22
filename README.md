# Meeting Scheduler

Find a meeting time that works across participant calendars.

## Layout

```
scheduler/          Package
  models.py         Calendar and meeting models          (Harshitha)
  loaders.py        Load sample calendars                (Harshitha)
  conflicts.py      Overlap detection                    (Tejdeep)
  rules.py          Scheduling constraints               (Tejdeep)
  slot_finder.py    Available slot search                (Vedanshu)
  reporting.py      Report output                        (Vedanshu)
  cli.py            Command-line interface               (Vedanshu)
  __main__.py       `python -m scheduler`                (Vedanshu)

scripts/
  generate_calendars.py                                  (Harshitha)

data/sample_calendars/   Input calendars
tests/                   pytest modules
reports/                 Generated reports (gitignored)
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run tests locally

From the repository root, with the virtual environment activated:

```bash
pytest
```

To run one file:

```bash
pytest tests/test_models.py
```

GitHub Actions runs `pytest` on every pull request. A failing test fails the workflow.

## ICS calendar import (STRETCH-01)

Install project dependencies with `pip install -e ".[dev]"` (or
`pip install -r requirements.txt`) to include the `icalendar` parser.

ICS files contain `VEVENT` entries. `SUMMARY` becomes the Event title;
`DTSTART` and `DTEND` become its start and end. The shared Event model is
unchanged. Import one person's calendar with an explicit owner:

```python
from scheduler.loaders import load_ics_calendar

events = load_ics_calendar(
    "data/calendars/sam.ics",
    person="Sam",
    local_timezone="America/New_York",
)
```

The normal loader and CLI also accept `.ics` files. They derive the owner
from the filename, capitalizing only its first letter: `sam.ics` maps to `Sam`.
Use filenames matching participant names, or pass `person` to the direct loader.
An ICS organizer or attendee is not automatically the calendar owner.

```bash
python -m scheduler --input-dir data/calendars --date 2026-10-23 \
  --participants Sam Priya --duration 30 --output reports/schedule.txt \
  --timezone America/New_York
```

UTC (`Z`) and `TZID` timestamps require an explicit target time zone. The
loader converts them to that zone and removes timezone information to match
the project's agreed local-time model. Floating times already represent that
local time. All-day dates become midnight-to-midnight events with an exclusive
end date; an omitted end date means one day. Timed events require `DTEND`.

Malformed events fail the entire import with the file path and event number.
Recurring events and `DURATION` are explicitly unsupported in this basic parser;
they raise errors rather than silently omit busy time. Cancelled and transparent
events are skipped. Folded lines, escaped text, multiple events, and empty
calendars are supported. For files sharing a stem, the CLI prefers JSON, then
CSV, then ICS, so alternate exports are not imported twice.
