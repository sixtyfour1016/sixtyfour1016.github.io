"""Upload user tokens to Cloudflare KV using the REST API."""
import argparse
import json
import os
from pathlib import Path
from typing import Dict

import requests
from dotenv import load_dotenv


def load_tokens(source: Path) -> Dict[str, str]:
    tokens: Dict[str, str] = {}
    if source.is_file():
        data = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Token file must be a JSON object of user -> token.")
        for k, v in data.items():
            tokens[str(k)] = str(v)
        return tokens

    # If source is a directory, build from ICS filenames (stem) with random tokens
    from secrets import token_urlsafe

    for ics_file in source.glob("*.ics"):
        user = ics_file.stem
        tokens[user] = token_urlsafe(32)
    return tokens


def put_token(session: requests.Session, account_id: str, namespace_id: str, user: str, token: str):
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/storage/kv/namespaces/{namespace_id}/values/{user}"
    resp = session.put(url, data=token.encode("utf-8"), headers={"Content-Type": "text/plain"})
    if not resp.ok:
        raise RuntimeError(f"Failed to put {user}: {resp.status_code} {resp.text}")


def get_token(session: requests.Session, account_id: str, namespace_id: str, user: str) -> str | None:
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/storage/kv/namespaces/{namespace_id}/values/{user}"
    resp = session.get(url)
    if resp.status_code == 404:
        return None
    if not resp.ok:
        raise RuntimeError(f"Failed to get {user}: {resp.status_code} {resp.text}")
    return resp.text


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Sync user tokens into Cloudflare KV.")
    parser.add_argument(
        "--tokens",
        type=Path,
        required=True,
        help="Path to JSON file of {user: token} or a directory of ICS files to generate tokens from.",
    )
    args = parser.parse_args()

    account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    namespace_id = os.environ["CLOUDFLARE_KV_NAMESPACE_ID"]
    api_token = os.environ["CLOUDFLARE_API_TOKEN"]  # needs KV write

    tokens = load_tokens(args.tokens)
    if not tokens:
        raise SystemExit("No tokens to sync.")

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {api_token}"})

    for user, token in tokens.items():
        existing = get_token(session, account_id, namespace_id, user)
        if existing:
            print(f"Skip {user} (already exists)")
            continue
        put_token(session, account_id, namespace_id, user, token)
        print(f"Synced {user}")

    print(f"✅ Processed {len(tokens)} token(s) for KV namespace {namespace_id}")


if __name__ == "__main__":
    main()
