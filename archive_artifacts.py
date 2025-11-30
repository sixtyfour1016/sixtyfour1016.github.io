"""Archive current artifacts into timestamped folders before updates."""
import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path


BASE = Path(__file__).resolve().parent
ICS_DIR = BASE / "ics"
JSON_DIR = BASE / "json"
CSV_DIR = BASE / "csv"
PDF_DIR = BASE / "pdf"
ARCHIVE_DIR = BASE / "archive"


def timestamp_version() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def gather_users_from_dirs() -> set[str]:
    users: set[str] = set()
    for root in (ICS_DIR, JSON_DIR, CSV_DIR, PDF_DIR):
        if root.exists():
            for p in root.iterdir():
                if p.is_dir():
                    users.add(p.name)
                elif root is ICS_DIR and p.is_file() and p.suffix == ".ics":
                    users.add(p.stem)
    return users


def archive_user(user: str, version: str):
    mappings = [
        (ICS_DIR / f"{user}.ics", ARCHIVE_DIR / "ics" / user / version / f"{user}.ics"),
        (JSON_DIR / user / "raw.json", ARCHIVE_DIR / "json" / user / version / "raw.json"),
        (JSON_DIR / user / f"{user}.json", ARCHIVE_DIR / "json" / user / version / f"{user}.json"),
        (CSV_DIR / user / "week_a.csv", ARCHIVE_DIR / "csv" / user / version / "week_a.csv"),
        (CSV_DIR / user / "week_b.csv", ARCHIVE_DIR / "csv" / user / version / "week_b.csv"),
        (PDF_DIR / user / "week_a.pdf", ARCHIVE_DIR / "pdf" / user / version / "week_a.pdf"),
        (PDF_DIR / user / "week_b.pdf", ARCHIVE_DIR / "pdf" / user / version / "week_b.pdf"),
    ]

    any_copied = False
    for src, dst in mappings:
        if not src.exists():
            print(f"Skip missing {src}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        any_copied = True
        print(f"Archived {src} -> {dst}")

    if not any_copied:
        print(f"ℹ️ No artifacts found for {user}")


def main():
    parser = argparse.ArgumentParser(
        description="Archive current timetable artifacts into versioned folders."
    )
    parser.add_argument(
        "user",
        nargs="*",
        help="Usernames to archive (dotted). If omitted, use --all to archive every detected user.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Archive all detected users.",
    )
    parser.add_argument(
        "--version",
        help="Version label for the archive (default: UTC timestamp).",
    )
    args = parser.parse_args()

    if not args.user and not args.all:
        raise SystemExit("Provide usernames or use --all.")

    version = args.version or timestamp_version()
    users = set(args.user)
    if args.all:
        users |= gather_users_from_dirs()

    if not users:
        raise SystemExit("No users to archive.")

    for user in sorted(users):
        archive_user(user, version)


if __name__ == "__main__":
    main()
