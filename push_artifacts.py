import argparse
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage, commit, and push timetable artifacts for a user (type-first layout)."
    )
    parser.add_argument("username", help="Student username (dotted, e.g., k.thang19)")
    parser.add_argument(
        "--message",
        default=None,
        help="Optional commit message override.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Path to the git repository root.",
    )
    return parser.parse_args()


def run_git(cmd, cwd: Path):
    subprocess.run(["git", *cmd], check=True, cwd=cwd)


def main():
    args = parse_args()
    repo_root = args.repo_root
    username = args.username

    targets = [
        repo_root / "csv" / username / "week_a.csv",
        repo_root / "csv" / username / "week_b.csv",
        repo_root / "json" / username / f"{username}.json",
        repo_root / "ics" / f"{username}.ics",
    ]
    existing = [str(p) for p in targets if p.exists()]

    if not existing:
        print("ℹ️ No timetable artifacts found to stage.")
        return

    print("▶️ Staging timetable artifacts")
    run_git(["add", "--", *existing], repo_root)

    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=repo_root,
    )
    if diff.returncode == 0:
        print("ℹ️ No staged changes to commit.")
        return

    commit_msg = args.message or f"Update timetable artifacts for {username}"
    print("▶️ Committing changes")
    run_git(["commit", "-m", commit_msg], repo_root)

    print("▶️ Pushing changes")
    run_git(["push"], repo_root)

if __name__ == "__main__":
    main()
