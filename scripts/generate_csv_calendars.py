import csv
from pathlib import Path

from generate_json_calendars import get_sample_calendars


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "sample_calendars"


def generate_csv_calendars():
    """Generate CSV calendars for all five people."""

    calendars = get_sample_calendars()

    # Creating the folder can fail if the path is not writable.
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print(
            f"Error: could not create output directory '{OUTPUT_DIR}': {error}"
        )
        raise

    for person, events in calendars.items():
        file_path = OUTPUT_DIR / f"{person}.csv"

        events = sorted(events, key=lambda event: event["start"])

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=["person", "title", "start", "end"],
                )

                writer.writeheader()
                writer.writerows(events)
        except OSError as error:
            print(f"Error: could not write CSV file '{file_path}': {error}")
            raise
        except csv.Error as error:
            print(
                f"Error: could not write CSV rows to '{file_path}': {error}"
            )
            raise

        print(f"Created {file_path.name} ({len(events)} events)")

    print("All CSV calendars generated successfully!")


if __name__ == "__main__":
    generate_csv_calendars()
