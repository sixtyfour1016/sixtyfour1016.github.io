#!/usr/bin/env python3
import json
import sys
import os
from datetime import datetime, timedelta, date
import re
import hashlib

# === CONFIGURATION ===
START_DATE = date(2025, 11, 10)  # Monday (Week A start)
END_DATE = date(2026, 7, 8)
TERMS = [
    (date(2025, 9, 4), date(2025, 12, 16), [(date(2025, 10, 20), date(2025, 10, 31))]),
    (date(2026, 1, 8), date(2026, 3, 27), [(date(2026, 2, 16), date(2026, 2, 20))]),
    (date(2026, 4, 21), date(2026, 7, 8), [(date(2026, 5, 25), date(2026, 5, 29))]),
]
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIME_FMT = "%H:%M"
TZID = "Europe/London"

# -------------------
# Utilities
# -------------------
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

def is_real_period(period_label: str) -> bool:
    """Return True for 'Period N' where N is an integer. Avoid merging lunches/registration/etc."""
    if not period_label:
        return False
    m = re.match(r"Period\s+(\d+)$", period_label.strip(), flags=re.IGNORECASE)
    return bool(m)

def normalize_teacher_name(raw: str) -> str:
    """
    Normalise teacher names:
    - Remove newlines, join split last-name fragments (heuristic: if a token == 'on' appearing alone after
      a likely last-name fragment, join without space).
    - Collapse repeated whitespace.
    - Ensure final tokenization matches expected pattern: Title + maybe initials + Lastname.
    """
    if raw is None:
        return ""
    s = raw.replace("\r", "\n")  # unify
    # Replace multiple newlines with a single space first
    s = s.replace("\n", " ").strip()
    # collapse multi-spaces
    s = re.sub(r"\s+", " ", s)
    # Heuristic: fix cases like 'MacMah on' that came from PDF splitting into 'MacMah\non'
    tokens = s.split(" ")
    fixed_tokens = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.lower() == "on" and fixed_tokens:
            # append 'on' without extra space to previous token
            fixed_tokens[-1] = fixed_tokens[-1] + "on"
            i += 1
            continue
        fixed_tokens.append(tok)
        i += 1
    result = " ".join(fixed_tokens).strip()
    return result

def validate_time_str(t: str):
    try:
        datetime.strptime(t, TIME_FMT)
        return True
    except Exception:
        return False

def validate_json_schema(timetable):
    """
    Validate the combined timetable JSON.
    Returns list of error strings (empty => OK).
    Expects structure:
    { "Week A": { "Monday": [ { period, start, end, lesson, teacher, room }, ... ], ... }, "Week B": { ... } }
    """
    errors = []
    if not isinstance(timetable, dict):
        errors.append("Top-level JSON must be an object.")
        return errors

    for week_key in ("Week A", "Week B"):
        if week_key not in timetable:
            errors.append(f"Missing top-level key: {week_key}")
            continue
        if not isinstance(timetable[week_key], dict):
            errors.append(f"{week_key} must be an object mapping day->list")
            continue

        for day, entries in timetable[week_key].items():
            if day not in DAY_NAMES:
                errors.append(f"{week_key}: unexpected day name: '{day}'")
            if not isinstance(entries, list):
                errors.append(f"{week_key}/{day} must be a list")
                continue
            for idx, e in enumerate(entries):
                context = f"{week_key}/{day}[{idx}]"
                if not isinstance(e, dict):
                    errors.append(f"{context} is not an object")
                    continue
                # required fields
                for field in ("period", "start", "end", "lesson", "teacher", "room"):
                    if field not in e:
                        errors.append(f"{context} missing required field '{field}'")
                # time format
                if "start" in e and not validate_time_str(e["start"]):
                    errors.append(f"{context} has invalid start time: {e.get('start')!r}")
                if "end" in e and not validate_time_str(e["end"]):
                    errors.append(f"{context} has invalid end time: {e.get('end')!r}")
                # logical ordering
                if "start" in e and "end" in e and validate_time_str(e["start"]) and validate_time_str(e["end"]):
                    st = datetime.strptime(e["start"], TIME_FMT)
                    en = datetime.strptime(e["end"], TIME_FMT)
                    if en <= st:
                        errors.append(f"{context} end time {e['end']} is not after start time {e['start']}")
    return errors

# -------------------
# Merging logic
# -------------------
def merge_double_lessons(lessons):
    """
    Merge adjacent lessons that:
      - are both 'Period N' (real periods)
      - have same lesson name (exact match after stripping)
      - have same teacher (after normalisation)
      - have same room
      - the next lesson's start == current lesson's end
    Does NOT merge if room differs (per your instruction).
    """
    if not lessons:
        return []

    # Normalise and filter
    normed = []
    for e in lessons:
        period = e.get("period", "")
        lesson_name = (e.get("lesson") or e.get("lesson name") or e.get("subject") or "").strip()
        teacher_raw = e.get("teacher", "")
        teacher = normalize_teacher_name(teacher_raw)
        room = (e.get("room") or "").strip()
        start = e.get("start", "").strip()
        end = e.get("end", "").strip()
        normed.append({
            "period": period,
            "lesson": lesson_name,
            "teacher": teacher,
            "room": room,
            "start": start,
            "end": end
        })

    # Validate times and sort (skip invalid entries)
    def time_key(x):
        try:
            return datetime.strptime(x["start"], TIME_FMT)
        except Exception:
            return datetime.strptime("00:00", TIME_FMT)

    lessons_sorted = sorted(normed, key=time_key)

    merged = []
    current = lessons_sorted[0].copy()

    for nxt in lessons_sorted[1:]:
        # Only merge if both are numbered periods
        if not (is_real_period(current["period"]) and is_real_period(nxt["period"])):
            merged.append(current)
            current = nxt.copy()
            continue

        same_subject = (nxt["lesson"] == current["lesson"])
        same_teacher = (nxt["teacher"] == current["teacher"])
        same_room = (nxt["room"] == current["room"])
        touching_times = (nxt["start"] == current["end"])

        if same_subject and same_teacher and same_room and touching_times:
            # merge by extending end and combining period labels
            current["end"] = nxt["end"]
            current["period"] = f"{current['period']} + {nxt['period']}"
        else:
            merged.append(current)
            current = nxt.copy()

    merged.append(current)
    return merged

# -------------------
# ICS building
# -------------------
def escape_ics_text(s: str) -> str:
    if s is None:
        return ""
    # Escape backslashes, semicolons, commas, and CRLF -> per RFC 5545
    s = str(s)
    s = s.replace("\\", "\\\\")
    s = s.replace("\n", "\\n")
    s = s.replace(";", "\\;")
    s = s.replace(",", "\\,")
    return s

def format_dt(dt: datetime) -> str:
    # Format without Z; we will use TZID parameter on DTSTART/DTEND lines
    return dt.strftime("%Y%m%dT%H%M%S")

def build_ics_event(entry, d: date) -> str:
    # entry has fields: period, lesson, teacher, room, start, end (times in HH:MM)
    start_dt = datetime.strptime(f"{d.isoformat()} {entry['start']}", "%Y-%m-%d %H:%M")
    end_dt = datetime.strptime(f"{d.isoformat()} {entry['end']}", "%Y-%m-%d %H:%M")

    uid_source = f"{entry['lesson']}|{entry['teacher']}|{entry['start']}|{entry['end']}|{d.isoformat()}"
    uid = hashlib.md5(uid_source.encode("utf-8")).hexdigest() + "@school"

    summary = f"{entry['lesson']} ({entry['teacher']})"
    summary_esc = escape_ics_text(summary)
    loc = escape_ics_text(entry.get("room", ""))

    # Use TZID for start/end
    dtstart_line = f"DTSTART;TZID={TZID}:{format_dt(start_dt)}"
    dtend_line = f"DTEND;TZID={TZID}:{format_dt(end_dt)}"
    dtstamp_line = f"DTSTAMP:{format_dt(datetime.utcnow())}Z"

    vevent = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"SUMMARY:{summary_esc}",
        f"LOCATION:{loc}",
        dtstart_line,
        dtend_line,
        dtstamp_line,
        "END:VEVENT"
    ]
    return "\n".join(vevent) + "\n"

# -------------------
# Main flow
# -------------------
def main():
    if len(sys.argv) < 2:
        print("Usage: python ics_generator.py <username>")
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

    # Validate JSON BEFORE creating ICS
    errors = validate_json_schema(timetable)
    if errors:
        print("Validation errors found in timetable JSON:")
        for err in errors:
            print(" -", err)
        print("Fix the JSON and re-run.")
        sys.exit(2)

    week_flag = "Week A"
    d = START_DATE

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"PRODID:-//{escape_ics_text(username)}'s School Timetable 2025–26//mx//",
    ]

    # Iterate days; flip week_flag at start of Monday if this Monday is a teaching day (in_term)
    while d <= END_DATE:
        # Flip week parity at the start of the day for Mondays that are teaching days (but not the START_DATE)
        if d.weekday() == 0 and d != START_DATE and in_term(d):
            week_flag = "Week B" if week_flag == "Week A" else "Week A"

        if in_term(d):
            weekday = DAY_NAMES[d.weekday()]
            week_obj = timetable.get(week_flag, {})
            day_entries = week_obj.get(weekday, [])
            if day_entries:
                # Merge double lessons using robust logic
                merged = merge_double_lessons(day_entries)
                for entry in merged:
                    lesson_name = (entry.get("lesson") or "").strip()
                    if not lesson_name:
                        continue
                    if lesson_name.upper() == "N/A" or "IGNORE" in lesson_name.upper():
                        continue
                    # Build VEVENT
                    ics_lines.append(build_ics_event(entry, d))

        d += timedelta(days=1)

    ics_lines.append("END:VCALENDAR")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(ics_lines))

    print(f"✅ Created {output_file} from {json_file}")

if __name__ == "__main__":
    main()
