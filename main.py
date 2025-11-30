import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_MODEL = "gpt-4.1"


def run_step(cmd, description: str, cwd=None):
    print(f"\n▶️ {description}")
    subprocess.run(cmd, check=True, cwd=cwd)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="End-to-end timetable pipeline for a given username."
    )
    parser.add_argument("username", help="Student username (dotted, e.g., k.thang19)")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Model name passed to pdf_parser (default: gpt-4.1).",
    )
    parser.add_argument(
        "--prompt",
        type=Path,
        default=Path("table_prompt.txt"),
        help="Path to the GPT prompt used when parsing PDFs.",
    )
    parser.add_argument(
        "--skip-pdf",
        action="store_true",
        help="Skip PDF -> CSV parsing (expects CSVs to already exist).",
    )
    parser.add_argument(
        "--skip-json",
        action="store_true",
        help="Skip CSV merge (expects merged JSON to already exist).",
    )
    parser.add_argument(
        "--skip-ics",
        action="store_true",
        help="Skip ICS generation.",
    )
    parser.add_argument(
        "--skip-post",
        action="store_true",
        help="Skip post-processing JSON via GPT.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    repo_root = Path(__file__).resolve().parent
    username = args.username

    pdf_parser_path = repo_root / "pdf_parser.py"
    csv_to_json_path = repo_root / "csv_to_json.py"
    ics_path = repo_root / "ics.py"
    push_script = repo_root / "push_to_r2.py"
    postprocess_path = repo_root / "postprocess_json.py"

    if not args.skip_pdf:
        for week in ("a", "b"):
            run_step(
                [
                    sys.executable,
                    str(pdf_parser_path),
                    username,
                    "--week",
                    week,
                    "--model",
                    args.model,
                    "--prompt",
                    str(args.prompt),
                ],
                f"Parsing Week {week.upper()} PDF",
                cwd=repo_root,
            )

    if not args.skip_json:
        run_step(
            [sys.executable, str(csv_to_json_path), username],
            "Merging CSVs into JSON",
            cwd=repo_root,
        )

    if not args.skip_post:
        run_step(
            [sys.executable, str(postprocess_path), username, "--copy-if-no-rules"],
            "Post-processing JSON with user rules",
            cwd=repo_root,
        )

    if not args.skip_ics:
        run_step(
            [sys.executable, str(ics_path), username],
            "Generating ICS file",
            cwd=repo_root,
        )

    run_step(
        [sys.executable, str(push_script), username],
        "Uploading timetable ICS to Cloudflare R2",
        cwd=repo_root,
    )

    print(f"\n✅ Pipeline complete for {username}")


if __name__ == "__main__":
    main()
