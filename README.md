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
```
