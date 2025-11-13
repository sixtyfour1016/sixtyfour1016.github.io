import json
import sys
import os
from datetime import datetime, timedelta, date

# === CONFIGURATION ===
START_DATE = date(2025, 11, 10)  # Monday (Week A start)
TERMS = [
    (date(2025, 9, 4), date(2025, 12, 16), [(date(2025, 10, 20), date(2025, 10, 31))]),
    (date(2026, 1, 8), date(2026, 3, 27), [(date(2026, 2, 16), date(2026, 2, 20))]),
    (date(2026, 4, 21), date(2026, 7, 8), [(date(2026, 5, 25), date(2026, 5, 29))]),
]
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def in_term(d: date) -> bool:
    for start, end, half_terms in TERMS:
        if start <= d <= end:
            if any(hs <= d <= he for hs, he in half_terms):
                return False
            return True
    return False


def load_timetable(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def merge_double_lessons(lessons):
    if not lessons:
        return []
    lessons_sorted = sorted(lessons, key=lambda x: datetime.strptime(x["start"], "%H:%M"))
    merged = []
    current = lessons_sorted[0]
    for nxt in lessons_sorted[1:]:
        if (
            nxt["lesson"] == current["lesson"]
            and nxt["teacher"] == current["teacher"]
            and nxt["room"] == current["room"]
            and nxt["start"] == current["end"]
        ):
            current["end"] = nxt["end"]
            current["period"] += f" + {nxt['period']}"
        else:
            merged.append(current)
            current = nxt
    merged.append(current)
    return merged


def format_dt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def build_ics_event(entry, d: date) -> str:
    start_dt = datetime.strptime(f"{d} {entry['start']}", "%Y-%m-%d %H:%M")
    end_dt = datetime.strptime(f"{d} {entry['end']}", "%Y-%m-%d %H:%M")
    uid = f"{hash((entry['lesson'], entry['teacher'], start_dt))}@school"
    summary = f"{entry['lesson']} ({entry['teacher']})"
    desc = f"{entry['period']} – {entry['room']}"
    loc = entry["room"]
    return (
        "BEGIN:VEVENT\n"
        f"UID:{uid}\n"
        f"SUMMARY:{summary}\n"
        f"DESCRIPTION:{desc}\n"
        f"LOCATION:{loc}\n"
        f"DTSTART:{format_dt(start_dt)}\n"
        f"DTEND:{format_dt(end_dt)}\n"
        f"DTSTAMP:{format_dt(datetime.now())}\n"
        "END:VEVENT\n"
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: python ics.py <username>")
        sys.exit(1)

    username = sys.argv[1]
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users", username)

    json_file = os.path.join(base_dir, f"{username}.json")
    output_file = os.path.join(base_dir, f"{username}.ics")

    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok=True)

    if not os.path.exists(json_file):
        print(f"❌ Input file not found: {json_file}")
        sys.exit(1)

    timetable = load_timetable(json_file)
    week_flag = "Week A"
    d = START_DATE

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{username}'s School Timetable 2025–26//mx//",
    ]

    while d <= date(2026, 7, 8):
        if in_term(d):
            weekday = DAY_NAMES[d.weekday()]
            if weekday in timetable.get(week_flag, {}):
                merged = merge_double_lessons(timetable[week_flag][weekday])
                for entry in merged:
                    if not entry.get("lesson") or "Ignore" in entry.get("lesson", ""):
                        continue
                    ics_lines.append(build_ics_event(entry, d))

        d += timedelta(days=1)
        if d.weekday() == 0:
            week_flag = "Week B" if week_flag == "Week A" else "Week A"

    ics_lines.append("END:VCALENDAR")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(ics_lines))

    print(f"✅ Created {output_file} from {json_file}")


if __name__ == "__main__":
    main()
