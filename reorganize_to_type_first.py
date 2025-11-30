"""Reorganize /users into type-first layout: ics/, json/, csv/, pdf/."""
from pathlib import Path

BASE = Path(__file__).resolve().parent
USERS_DIR = BASE / "users"
ICS_DIR = BASE / "ics"
JSON_DIR = BASE / "json"
CSV_DIR = BASE / "csv"
PDF_DIR = BASE / "pdf"

PDF_EXTS = {".pdf", ".jpg", ".jpeg", ".png"}


def ensure_dirs():
    for d in (ICS_DIR, JSON_DIR, CSV_DIR, PDF_DIR):
        d.mkdir(exist_ok=True)


def week_tag(name: str) -> str | None:
    if "_week_a" in name:
        return "week_a"
    if "_week_b" in name:
        return "week_b"
    return None


def move_file(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    src.rename(dst)
    print(f"Moved {src} -> {dst}")


def reorganize_user(user_dir: Path):
    user = user_dir.name
    for path in sorted(user_dir.iterdir()):
        if not path.is_file():
            continue

        suffix = path.suffix.lower()
        tag = week_tag(path.stem)

        if suffix == ".ics":
            move_file(path, ICS_DIR / f"{user}.ics")
        elif suffix == ".json":
            move_file(path, JSON_DIR / user / f"{user}.json")
        elif tag and suffix == ".csv":
            move_file(path, CSV_DIR / user / f"{tag}.csv")
        elif tag and suffix in PDF_EXTS:
            move_file(path, PDF_DIR / user / f"{tag}{suffix}")
        else:
            print(f"Skip {path} (unrecognized)")

    try:
        user_dir.rmdir()
        print(f"Removed empty folder {user_dir}")
    except OSError:
        # Folder not empty
        pass


def main():
    if not USERS_DIR.is_dir():
        raise SystemExit(f"Users directory not found: {USERS_DIR}")

    ensure_dirs()
    for user_dir in sorted(USERS_DIR.iterdir()):
        if user_dir.is_dir():
            reorganize_user(user_dir)


if __name__ == "__main__":
    main()
