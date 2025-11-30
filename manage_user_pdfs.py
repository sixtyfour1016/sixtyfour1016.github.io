"""Create or update a user's Week A/B PDFs, archiving any existing ones first."""
import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path


BASE = Path(__file__).resolve().parent
PDF_ROOT = BASE / "pdf"
ARCHIVE_ROOT = BASE / "archive" / "pdf"


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def archive_existing(user: str, version: str):
    """Archive current week_a/week_b PDFs if they exist."""
    user_pdf_dir = PDF_ROOT / user
    if not user_pdf_dir.exists():
        return

    targets = [
        (user_pdf_dir / "week_a.pdf", ARCHIVE_ROOT / user / version / "week_a.pdf"),
        (user_pdf_dir / "week_b.pdf", ARCHIVE_ROOT / user / version / "week_b.pdf"),
    ]

    any_archived = False
    for src, dst in targets:
        if not src.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        any_archived = True
        print(f"Archived {src} -> {dst}")

    if not any_archived:
        print(f"No existing PDFs to archive for {user}")


def copy_new_pdfs(user: str, week_a: Path, week_b: Path):
    user_pdf_dir = PDF_ROOT / user
    user_pdf_dir.mkdir(parents=True, exist_ok=True)

    dest_a = user_pdf_dir / "week_a.pdf"
    dest_b = user_pdf_dir / "week_b.pdf"

    shutil.copy2(week_a, dest_a)
    print(f"Copied {week_a} -> {dest_a}")

    shutil.copy2(week_b, dest_b)
    print(f"Copied {week_b} -> {dest_b}")


def main():
    parser = argparse.ArgumentParser(
        description="Add a new user with Week A/B PDFs or update an existing user's PDFs (archiving old ones)."
    )
    parser.add_argument("user", help="Dotted username, e.g., k.thang19")
    parser.add_argument("--week-a", type=Path, required=True, help="Path to Week A PDF")
    parser.add_argument("--week-b", type=Path, required=True, help="Path to Week B PDF")
    parser.add_argument(
        "--version",
        help="Optional archive version label (default: current UTC timestamp).",
    )
    args = parser.parse_args()

    if not args.week_a.exists():
        raise SystemExit(f"Week A PDF not found: {args.week_a}")
    if not args.week_b.exists():
        raise SystemExit(f"Week B PDF not found: {args.week_b}")

    ver = args.version or timestamp()
    archive_existing(args.user, ver)
    copy_new_pdfs(args.user, args.week_a, args.week_b)
    print("✅ Done")


if __name__ == "__main__":
    main()
