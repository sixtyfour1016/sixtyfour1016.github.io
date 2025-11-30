"""Generate long random tokens for each user based on ICS files in ics/."""
import argparse
import json
import secrets
from pathlib import Path

ICS_DIR = Path(__file__).resolve().parent / "ics"


def generate_tokens() -> dict[str, str]:
    tokens: dict[str, str] = {}
    for ics_file in sorted(ICS_DIR.glob("*.ics")):
        user_id = ics_file.stem
        tokens[user_id] = secrets.token_urlsafe(32)
    return tokens


def main():
    parser = argparse.ArgumentParser(
        description="Generate random tokens for all users with ICS files in ics/."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print tokens as JSON instead of lines.",
    )
    args = parser.parse_args()

    tokens = generate_tokens()

    if args.json:
        print(json.dumps(tokens, indent=2))
    else:
        for user_id, token in tokens.items():
            print(f"{user_id} {token}")

    print(
        "\nUse these in Cloudflare KV (binding TOKENS), e.g.: "
        "wrangler kv:key put --binding TOKENS <user_id> <token>"
    )


if __name__ == "__main__":
    main()
