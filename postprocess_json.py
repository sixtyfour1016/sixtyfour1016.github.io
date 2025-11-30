"""Post-process raw timetable JSON into a cleaned version per user preferences."""
import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

DEFAULT_MODEL = "gpt-4.1"

# Per-user rules can live in rules/<user>.txt or be provided via --rules-file
USER_RULES: dict[str, str] = {}


def load_rules(username: str, rules_file: Path | None) -> str:
    if rules_file:
        return rules_file.read_text(encoding="utf-8").strip()
    rules_dir = Path(__file__).resolve().parent / "rules"
    candidate = rules_dir / f"{username}.txt"
    if candidate.exists():
        return candidate.read_text(encoding="utf-8").strip()
    return USER_RULES.get(username, "").strip()


def extract_text_blocks(response) -> list[str]:
    """Extract text blocks from Responses API output."""
    blocks: list[str] = []
    if hasattr(response, "output"):
        for output in response.output:
            for item in getattr(output, "content", []):
                text_obj = getattr(item, "text", None)
                text = getattr(text_obj, "value", None)
                if isinstance(text, str) and text.strip():
                    blocks.append(text.strip())
    if not blocks and hasattr(response, "content"):
        for item in getattr(response, "content", []):
            text_obj = getattr(item, "text", None)
            text = getattr(text_obj, "value", None)
            if isinstance(text, str) and text.strip():
                blocks.append(text.strip())
    if not blocks:
        # fallbacks
        text = getattr(response, "output_text", None)
        if isinstance(text, str) and text.strip():
            blocks.append(text.strip())
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            blocks.append(text.strip())
    return blocks


def call_model(raw_json: str, rules: str, model: str) -> str:
    prompt = (
        "You are a timetable post-processor. You are given JSON with Week A and Week B "
        "entries. Apply the provided user-specific rules. Do not invent fields. "
        "Return JSON only, no markdown or commentary."
    )
    input_text = f"{prompt}\n\nUser rules:\n{rules or 'None; return input as-is.'}\n\nRaw JSON:\n{raw_json}"
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.responses.create(
        model=model,
        input=[{"role": "user", "content": [{"type": "input_text", "text": input_text}]}],
        temperature=0,
    )
    texts = extract_text_blocks(response)
    if not texts:
        print("⚠️ Model returned no text; raw response follows:")
        print(response)
        raise ValueError("Model returned no text")
    return texts[0]


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Apply per-user preferences to raw timetable JSON via GPT."
    )
    parser.add_argument("username", help="Student username (dotted, e.g., k.thang19)")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"OpenAI model name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--rules-file",
        type=Path,
        help="Optional path to a text file containing user-specific rules.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Override path to raw JSON (default: json/{user}/raw.json).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Override path to cleaned JSON (default: json/{user}/{user}.json).",
    )
    parser.add_argument(
        "--copy-if-no-rules",
        action="store_true",
        help="If no rules are found and no rules file is provided, copy raw to output.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    json_dir = repo_root / "json" / args.username
    raw_path = args.input or json_dir / "raw.json"
    out_path = args.output or json_dir / f"{args.username}.json"

    if not raw_path.exists():
        raise SystemExit(f"Raw JSON not found: {raw_path}")

    rules = load_rules(args.username, args.rules_file)
    raw_text = raw_path.read_text(encoding="utf-8")

    if not rules:
        if args.copy_if_no_rules:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(raw_text, encoding="utf-8")
            print(f"ℹ️ No rules provided. Copied raw -> {out_path}")
            return
        else:
            print("⚠️ No rules provided; run with --copy-if-no-rules to copy raw.")
            return

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set; cannot post-process via GPT.")

    cleaned_text = call_model(raw_text, rules, args.model)
    try:
        cleaned_json = json.loads(cleaned_text)
    except json.JSONDecodeError:
        raise SystemExit("Model response was not valid JSON.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(cleaned_json, indent=2), encoding="utf-8")
    print(f"✅ Wrote cleaned JSON to {out_path}")


if __name__ == "__main__":
    main()
