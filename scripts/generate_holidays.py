"""Write the list of Victorian public holidays that dbt loads as a seed file.

The dates come from the `holidays` library. Run this again to add a new year:

    python scripts/generate_holidays.py

The result, dbt/seeds/vic_public_holidays.csv, is committed to the repository,
so building the warehouse does not need this script or the library.
"""

import csv
from pathlib import Path

import holidays

FIRST_YEAR: int = 2024
LAST_YEAR: int = 2027
OUTPUT_PATH: Path = Path("dbt/seeds/vic_public_holidays.csv")


def main() -> None:
    victoria = holidays.Australia(subdiv="VIC", years=range(FIRST_YEAR, LAST_YEAR + 1))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["holiday_date", "holiday_name"])
        for holiday_date, holiday_name in sorted(victoria.items()):
            writer.writerow([holiday_date.isoformat(), holiday_name])
    print(f"Wrote {len(victoria)} holidays to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
