# Meeting Scheduler

A local Python CLI that helps an office manager find a meeting time across
multiple employee calendars. It loads calendars from disk, detects double
bookings, finds shared free slots, and writes a readable report. No external
database, cloud API, or API key is required for the core workflow.

## Customer problem

Scheduling across many people is slow and error-prone when calendars are
checked by hand. Conflicts are easy to miss, and common free times are hard to
spot when several attendees are involved.

## Features

- Load per-person calendars from JSON, CSV, or ICS files
- Validate event fields through the shared `Event` model
- Detect same-person overlapping meetings (double bookings)
- Find shared free slots for selected participants
- Apply working-hours and minimum-gap scheduling rules
- Print and save a conflict and availability report
- Optional natural-language request parsing with an LLM (stretch)

## Architecture

```text
CLI (scheduler/cli.py)
        |
        v
 Calendar loaders  -->  Event objects
        |
  +-----+------+
  |            |
  v            v
Conflicts    Scheduling rules
  |            |
  +-----+------+
        |
        v
   Slot finder
        |
        v
 Report generator  -->  stdout + --output file
```

| Module | Owner | Role |
|---|---|---|
| `scheduler/models.py` | Harshitha | `Event` data model and validation |
| `scheduler/loaders.py` | Harshitha | JSON / CSV / ICS loading |
| `scheduler/ics.py` | Harshitha | ICS `VEVENT` parsing |
| `scheduler/conflicts.py` | Tejdeep | Overlaps, conflicts, busy intervals |
| `scheduler/rules.py` | Tejdeep | `WorkingHoursRule`, `MinimumGapRule` |
| `scheduler/slot_finder.py` | Vedanshu | Shared free-slot search |
| `scheduler/reporting.py` | Vedanshu | Report formatting and file output |
| `scheduler/cli.py` | Vedanshu | CLI orchestration |
| `scheduler/nl_parser.py` | Vedanshu | Optional LLM request parsing |

## Prerequisites

- Python 3.11 or newer
- A virtual environment (recommended)

## Setup and installation

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Core dependencies include `icalendar` for ICS import. For optional
natural-language mode, also install:

```bash
pip install -e ".[dev,nl]"
```

## Project layout

```text
scheduler/                 Application package
  models.py                Event model
  loaders.py               JSON / CSV / ICS loaders
  ics.py                   ICS parsing helpers
  conflicts.py             Conflict detection
  rules.py                 Scheduling rules
  slot_finder.py           Shared free slots
  reporting.py             Report text and file writing
  cli.py                   Command-line interface
  nl_parser.py             Natural-language parsing (stretch)
  __main__.py              python -m scheduler entry point

data/sample_calendars/     Sample JSON and CSV calendars
scripts/                   Calendar generation scripts
tests/                     pytest suite
reports/                   Generated reports (gitignored)
.github/workflows/         CI workflow
```

## Calendar formats

Each employee has one calendar file. Field names are `person`, `title`,
`start`, and `end`. Timestamps use ISO 8601 local time without a timezone
offset, for example `2026-10-20T09:00:00`.

### JSON

```json
[
  {
    "person": "Sam",
    "title": "Team Standup",
    "start": "2026-10-20T09:00:00",
    "end": "2026-10-20T09:30:00"
  }
]
```

### CSV

Header row required:

```csv
person,title,start,end
Sam,Team Standup,2026-10-20T09:00:00,2026-10-20T09:30:00
```

### ICS (stretch)

ICS files use `VEVENT` entries. `SUMMARY` maps to title; `DTSTART` / `DTEND`
map to start and end. The owner is taken from the filename by default
(`sam.ics` → `Sam`), or from an explicit `person=` argument to
`load_ics_calendar`.

When the same stem exists in more than one format, the CLI prefers **JSON,
then CSV, then ICS**, so a person is not imported twice.

## Working hours, timezone, and overlap rules

- Working hours: **09:00–17:00** on the requested date
- One shared local timezone for everyone (timezone-naive datetimes)
- Meeting starts on **15-minute** boundaries
- Intervals are half-open: `[start, end)`
- Boundary-touching meetings do **not** overlap

  Example: `09:00–10:00` and `10:00–11:00` are allowed back-to-back.

- Overlap condition:

  ```python
  a.start < b.end and b.start < a.end
  ```

- Default scheduling rules:
  - `WorkingHoursRule` — slot must fit inside 09:00–17:00
  - `MinimumGapRule(0)` — no required buffer; back-to-back is allowed

Timezone-aware values are rejected by the `Event` model. Zoned ICS timestamps
are converted with `--timezone` (IANA name such as `America/New_York`) and
stored as naive local times.

## How meeting slots are generated

1. Keep events for the requested participants on the meeting date
2. Merge busy intervals with `get_busy_intervals`
3. Propose starts every 15 minutes from 09:00 while the slot still ends by 17:00
4. Reject candidates that overlap busy time
5. Apply configured scheduling rules
6. Return remaining slots in chronological order

## CLI usage

Typed mode (no API key):

```bash
python -m scheduler \
  --input-dir data/sample_calendars \
  --date 2026-10-20 \
  --participants Sam Priya \
  --duration 30 \
  --output reports/schedule.txt
```

The full report is printed to the terminal and saved to `--output`.

With ICS time-zone conversion:

```bash
python -m scheduler \
  --input-dir data/sample_calendars \
  --date 2026-10-20 \
  --participants Sam Priya \
  --duration 30 \
  --output reports/schedule.txt \
  --timezone America/New_York
```

Show help:

```bash
python -m scheduler --help
```

### Arguments

| Argument | Required | Purpose |
|---|---|---|
| `--input-dir` | yes | Directory of `.json`, `.csv`, and/or `.ics` calendars |
| `--date` | yes\* | Meeting date `YYYY-MM-DD` |
| `--participants` | yes\* | Attendee names |
| `--duration` | yes\* | Meeting length in minutes |
| `--output` | yes | Report file path |
| `--timezone` | no | IANA zone for zoned ICS import |
| `--request` | no | Natural-language request (needs API key) |

\* Not required when `--request` is used (unless you override parsed values).

## Sample output

```text
====================================
     MEETING SCHEDULER REPORT
====================================

Date: 2026-10-20
Participants: Sam, Priya
Duration: 30 minutes

------------------------------------
CALENDAR CONFLICTS
------------------------------------

No calendar conflicts.

------------------------------------
SUGGESTED MEETING TIMES
------------------------------------

1. 10:00-10:30
2. 10:15-10:45
...
====================================

Report written to reports/schedule.txt
```

## Running tests

From the repository root, with the virtual environment activated:

```bash
pytest
```

One file:

```bash
pytest tests/test_slot_finder.py
```

## GitHub Actions CI

On every push and pull request, `.github/workflows/tests.yml`:

1. Checks out the repository
2. Sets up Python 3.12
3. Installs `pip install -e ".[dev,nl]"`
4. Runs `pytest`

A failing test fails the workflow check.

## Natural-language requests (stretch)

Optional `--request` uses Azure OpenAI only to turn a sentence into
`participants`, `duration_minutes`, `date`, and `time_preference`. Conflict
detection and slot search stay in Python.

```bash
pip install -e ".[dev,nl]"
cp .env.example .env
# fill AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_KEY
```

```bash
python -m scheduler \
  --input-dir data/sample_calendars \
  --request "30 minutes with Sam and Priya on 2026-10-20 afternoon" \
  --output reports/nl_schedule.txt
```

`morning` keeps slots before 12:00; `afternoon` keeps 12:00 and later. Typed
flags can override parsed values. Core typed CLI still works without an API key.

## Known limitations

- One shared naive timezone; no per-person zones in the core model
- Slot search is limited to 09:00–17:00 on a single requested date
- ICS recurrence and `DURATION` are unsupported
- When JSON and CSV exist for the same person, only JSON is loaded

## Optional future enhancements

- Richer time preferences (for example evening windows)
- Multi-day search ranges
- Calendar write-back after a slot is chosen
