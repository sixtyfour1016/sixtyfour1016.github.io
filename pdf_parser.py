import argparse
import os
from pathlib import Path
from typing import Iterable
from dotenv import load_dotenv

from openai import OpenAI

load_dotenv()

DEFAULT_MODEL = "gpt-4.1-mini"
CSV_HEADER = ["Day", "Period", "Start", "End", "Lesson", "Teacher", "Room"]


def load_prompt(prompt_path: Path) -> str:
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8").strip()


def _extract_value(possible) -> str:
    if possible is None:
        return ""
    if isinstance(possible, str):
        return possible
    value = getattr(possible, "value", None)
    if isinstance(value, str):
        return value
    return ""


def extract_text_blocks(response) -> Iterable[str]:
    """
    Responses API may nest text inside output -> content -> text.
    Yield every text fragment we can find.
    """
    if hasattr(response, "output"):
        for output in response.output:
            for item in getattr(output, "content", []):
                text = _extract_value(getattr(item, "text", None))
                if text:
                    yield text
    if hasattr(response, "content"):
        for item in getattr(response, "content", []):
            text = _extract_value(getattr(item, "text", None))
            if text:
                yield text
    # Fallback for legacy completion style responses
    text = _extract_value(getattr(response, "output_text", None))
    if text:
        yield text
    text = _extract_value(getattr(response, "text", None))
    if text:
        yield text


def clean_csv(raw_text: str) -> str:
    lines = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            continue
        if stripped.startswith("```") or stripped.endswith("```"):
            continue
        if not stripped:
            continue
        lines.append(stripped)
    cleaned = "\n".join(lines).strip()
    if not cleaned:
        raise ValueError("Received empty CSV content from model.")
    header = [h.strip() for h in cleaned.splitlines()[0].split(",")]
    if header != CSV_HEADER:
        raise ValueError(
            f"Unexpected CSV header {header}. Expected {CSV_HEADER}. "
            "Please refine the model output."
        )
    return cleaned + ("\n" if not cleaned.endswith("\n") else "")


def call_model(pdf_path: Path, prompt: str, model_name: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=api_key)
    uploaded = client.files.create(file=pdf_path.open("rb"), purpose="assistants")
    try:
        response = client.responses.create(
            model=model_name,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_file", "file_id": uploaded.id},
                    ],
                }
            ],
            temperature=0,
        )
    finally:
        client.files.delete(uploaded.id)

    text_blocks = list(extract_text_blocks(response))
    if not text_blocks:
        raise ValueError("Model returned no text content.")
    combined = "\n".join(text_blocks)
    return clean_csv(combined)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert timetable PDF to CSV via GPT.")
    parser.add_argument("username", help="Student username (folder inside users/)")
    parser.add_argument(
        "--week",
        choices=["a", "b"],
        required=True,
        help="Which week PDF to parse.",
    )
    parser.add_argument(
        "--prompt",
        type=Path,
        default=Path("table_prompt.txt"),
        help="Path to the GPT prompt used for extraction.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="OpenAI model name, defaults to gpt-4.1-mini.",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        help="Override the input PDF path. Defaults to the student's week PDF.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Override the CSV output path. Defaults to the student's week CSV.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    repo_root = Path(__file__).resolve().parent
    user_dir = repo_root / "users" / args.username
    pdf_path = args.pdf or user_dir / f"{args.username}_week_{args.week}.pdf"
    output_path = args.output or user_dir / f"{args.username}_week_{args.week}.csv"
    prompt_text = load_prompt(args.prompt)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    csv_text = call_model(pdf_path, prompt_text, args.model)
    output_path.write_text(csv_text, encoding="utf-8")
    print(f"✅ Wrote CSV for Week {args.week.upper()} to {output_path}")


if __name__ == "__main__":
    main()
