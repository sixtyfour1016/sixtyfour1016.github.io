import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List

CSV_HEADER = ["Day", "Period", "Start", "End", "Lesson", "Teacher", "Room"]


def load_week(csv_path: Path) -> Dict[str, List[dict]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    week: Dict[str, List[dict]] = {}
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != CSV_HEADER:
            raise ValueError(
                f"{csv_path} has unexpected headers {reader.fieldnames}. "
                f"Expected {CSV_HEADER}."
            )
        for row in reader:
            day = row["Day"].strip()
            if not day:
                day = "Unknown"
            entry = {
                "period": row["Period"].strip() or "N/A",
                "start": row["Start"].strip() or "N/A",
                "end": row["End"].strip() or "N/A",
                "lesson": row["Lesson"].strip() or "N/A",
                "teacher": row["Teacher"].strip() or "N/A",
                "room": row["Room"].strip() or "N/A",
            }
            week.setdefault(day, []).append(entry)
    return week


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge Week A/B CSVs into a single timetable JSON file."
    )
    parser.add_argument("username", help="Student username (dotted, e.g., k.thang19)")
    parser.add_argument(
        "--week-a",
        type=Path,
        help="Optional override for Week A CSV path.",
    )
    parser.add_argument(
        "--week-b",
        type=Path,
        help="Optional override for Week B CSV path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional override for the merged JSON output path.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    repo_root = Path(__file__).resolve().parent
    csv_dir = repo_root / "csv" / args.username
    json_dir = repo_root / "json" / args.username

    csv_a = args.week_a or csv_dir / "week_a.csv"
    csv_b = args.week_b or csv_dir / "week_b.csv"
    output = args.output or json_dir / "raw.json"

    data = {
        "Week A": load_week(csv_a),
        "Week B": load_week(csv_b),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"✅ Wrote merged timetable JSON to {output}")


if __name__ == "__main__":
    main()
