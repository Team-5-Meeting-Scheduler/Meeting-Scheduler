import json
from datetime import datetime
from pathlib import Path


# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "sample_calendars"

# All calendar times use the same agreed local time zone.
# Timestamps do not include UTC offsets.


def create_event(person, title, date, start_time, end_time):
    """
    Create a calendar event with the required fields:
    person, title, start, end.
    """
    start = datetime.fromisoformat(f"{date}T{start_time}")
    end = datetime.fromisoformat(f"{date}T{end_time}")

    if end <= start:
        raise ValueError("Event end time must be later than start time.")

    return {
        "person": person,
        "title": title,
        "start": start.isoformat(),
        "end": end.isoformat(),
    }


def get_sample_calendars():
    """
    Return sample calendars for five people.

    Scenarios:
    1. Normal day
    2. Back-to-back meetings
    3. Double-booked meetings
    4. Nearly-full working day
    """

    calendars = {
        "sam": [
            # NORMAL DAY - October 20
            create_event(
                "Sam", "Team Standup",
                "2026-10-20", "09:00", "09:30"
            ),
            create_event(
                "Sam", "Project Review",
                "2026-10-20", "11:00", "12:00"
            ),
            create_event(
                "Sam", "Sprint Discussion",
                "2026-10-20", "14:00", "15:00"
            ),

            # BACK-TO-BACK - October 21
            create_event(
                "Sam", "Planning",
                "2026-10-21", "09:00", "10:00"
            ),
            create_event(
                "Sam", "Client Call",
                "2026-10-21", "10:00", "11:00"
            ),
        ],

        "priya": [
            # NORMAL DAY - October 20
            create_event(
                "Priya", "Daily Standup",
                "2026-10-20", "09:30", "10:00"
            ),
            create_event(
                "Priya", "Documentation",
                "2026-10-20", "13:00", "14:00"
            ),

            # DOUBLE BOOKING - October 22
            create_event(
                "Priya", "Team Meeting",
                "2026-10-22", "10:00", "11:00"
            ),
            create_event(
                "Priya", "Client Discussion",
                "2026-10-22", "10:30", "11:30"
            ),
        ],

        "alex": [
            # NEARLY-FULL DAY - October 23
            create_event(
                "Alex", "Morning Work",
                "2026-10-23", "09:00", "11:00"
            ),
            create_event(
                "Alex", "Project Work",
                "2026-10-23", "11:15", "13:00"
            ),
            create_event(
                "Alex", "Team Sessions",
                "2026-10-23", "13:00", "15:00"
            ),
            create_event(
                "Alex", "Afternoon Review",
                "2026-10-23", "15:15", "17:00"
            ),

            # NORMAL DAY - October 20
            create_event(
                "Alex", "Team Sync",
                "2026-10-20", "10:00", "11:00"
            ),
        ],

        "eliy": [
            # NORMAL DAY - October 20
            create_event(
                "Eliy", "Sprint Planning",
                "2026-10-20", "09:00", "10:00"
            ),
            create_event(
                "Eliy", "Code Review",
                "2026-10-20", "11:00", "12:00"
            ),
            create_event(
                "Eliy", "Team Discussion",
                "2026-10-20", "14:00", "15:00"
            ),

            # BACK-TO-BACK - October 21
            create_event(
                "Eliy", "Design Review",
                "2026-10-21", "10:00", "11:00"
            ),
            create_event(
                "Eliy", "Project Update",
                "2026-10-21", "11:00", "12:00"
            ),
        ],

        "justin": [
            # NORMAL DAY - October 20
            create_event(
                "Justin", "Daily Standup",
                "2026-10-20", "09:30", "10:00"
            ),
            create_event(
                "Justin", "Client Meeting",
                "2026-10-20", "13:00", "14:00"
            ),

            # DOUBLE BOOKING - October 22
            create_event(
                "Justin", "Product Review",
                "2026-10-22", "14:00", "15:00"
            ),
            create_event(
                "Justin", "Manager Meeting",
                "2026-10-22", "14:30", "15:30"
            ),
        ],
    }

    return calendars


def generate_json_calendars():
    """Write each person's calendar to a separate JSON file."""

    calendars = get_sample_calendars()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for person, events in calendars.items():
        file_path = OUTPUT_DIR / f"{person}.json"

        # Keep events ordered by their starting time.
        events = sorted(events, key=lambda event: event["start"])

        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(events, file, indent=4)

        print(f"Created {file_path.name} ({len(events)} events)")

    print("All JSON calendars generated successfully!")


if __name__ == "__main__":
    generate_json_calendars()
