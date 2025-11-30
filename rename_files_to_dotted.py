"""Rename timetable artifacts to use dotted usernames (e.g., kthang19 -> k.thang19)."""
from pathlib import Path


def insert_dot_after_first_char(name: str) -> str:
    """Ensure there is a dot after the first character in the base name."""
    if len(name) < 2 or name[1] == ".":
        return name
    return f"{name[0]}.{name[1:]}"


def rename_user_files(user_dir: Path) -> None:
    user_id = user_dir.name
    dotted = insert_dot_after_first_char(user_id)

    for path in sorted(user_dir.iterdir()):
        if not path.is_file():
            continue

        current = path.name
        if current.startswith(dotted):
            print(f"Skip {current} (already dotted)")
            continue

        if not current.startswith(user_id):
            print(f"Skip {current} (does not match user id {user_id})")
            continue

        suffix = current[len(user_id) :]
        target = path.with_name(f"{dotted}{suffix}")

        if target.exists():
            target.unlink()
        path.rename(target)
        print(f"Renamed {current} -> {target.name}")


def main():
    users_dir = Path(__file__).resolve().parent / "users"
    if not users_dir.is_dir():
        raise SystemExit(f"Users directory not found: {users_dir}")

    user_dirs = [p for p in sorted(users_dir.iterdir()) if p.is_dir()]

    for user_dir in user_dirs:
        rename_user_files(user_dir)

        dotted = insert_dot_after_first_char(user_dir.name)
        if dotted == user_dir.name:
            print(f"Folder already dotted: {user_dir.name}")
            continue

        target_dir = user_dir.with_name(dotted)
        if target_dir.exists():
            print(
                f"Skip renaming folder {user_dir.name} -> {target_dir.name} "
                "(target already exists)"
            )
            continue

        user_dir.rename(target_dir)
        print(f"Renamed folder {user_dir.name} -> {target_dir.name}")


if __name__ == "__main__":
    main()
