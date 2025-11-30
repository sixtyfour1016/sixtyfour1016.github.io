"""Upload a single user's ICS file to Cloudflare R2 without touching git."""
import argparse
import os
import secrets
from pathlib import Path

import boto3
import requests
from botocore.client import Config
from dotenv import load_dotenv


def insert_dot_after_first_char(name: str) -> str:
    """Ensure there is a dot after the first character in the base name."""
    if len(name) < 2 or name[1] == ".":
        return name
    return f"{name[0]}.{name[1:]}"


def build_s3_client():
    account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    access_key = os.environ["CLOUDFLARE_ACCESS_KEY_ID"]
    secret_key = os.environ["CLOUDFLARE_SECRET_ACCESS_KEY"]
    bucket = os.environ["R2_BUCKET"]
    endpoint = os.environ.get(
        "R2_ENDPOINT", f"https://{account_id}.r2.cloudflarestorage.com"
    )

    session = boto3.session.Session()
    client = session.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
    )
    return client, bucket


def build_kv_session():
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN")
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    namespace_id = os.environ.get("CLOUDFLARE_KV_NAMESPACE_ID")
    if not (api_token and account_id and namespace_id):
        return None, None, None
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {api_token}"})
    return session, account_id, namespace_id


def kv_get(session: requests.Session, account_id: str, namespace_id: str, key: str) -> str | None:
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/storage/kv/namespaces/{namespace_id}/values/{key}"
    resp = session.get(url)
    if resp.status_code == 404:
        return None
    if not resp.ok:
        raise RuntimeError(f"Failed to get KV key {key}: {resp.status_code} {resp.text}")
    return resp.text


def kv_put(session: requests.Session, account_id: str, namespace_id: str, key: str, value: str):
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/storage/kv/namespaces/{namespace_id}/values/{key}"
    resp = session.put(url, data=value.encode("utf-8"), headers={"Content-Type": "text/plain"})
    if not resp.ok:
        raise RuntimeError(f"Failed to put KV key {key}: {resp.status_code} {resp.text}")


def ensure_token(user: str) -> str | None:
    session, account_id, namespace_id = build_kv_session()
    if not session:
        print("⚠️ KV env vars missing; skipping token generation.")
        return None

    existing = kv_get(session, account_id, namespace_id, user)
    if existing:
        return existing

    token = secrets.token_urlsafe(32)
    kv_put(session, account_id, namespace_id, user, token)
    print(f"Generated new token for {user}")
    return token


def find_local_ics(user_dir: Path, username: str) -> Path:
    primary = user_dir / f"{insert_dot_after_first_char(username)}.ics"
    if primary.exists():
        return primary
    raise FileNotFoundError(f"No ICS found for {username} (looked for {primary.name})")


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Upload a user's ICS file to Cloudflare R2."
    )
    parser.add_argument("username", help="Student username (dotted, e.g., k.thang19)")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Path to the repo root (default: script directory).",
    )
    args = parser.parse_args()

    repo_root = args.repo_root
    ics_dir = repo_root / "ics"

    local_ics = find_local_ics(ics_dir, args.username)
    remote_name = f"{insert_dot_after_first_char(args.username)}.ics"
    key = f"ics/{remote_name}"

    s3, bucket = build_s3_client()
    print(f"▶️ Uploading {local_ics} to s3://{bucket}/{key}")
    with open(local_ics, "rb") as fh:
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=fh,
            ContentType="text/calendar",
        )
    print("✅ Upload complete")

    token = ensure_token(args.username)
    base_url = os.environ.get("ICS_BASE_URL")
    if token and base_url:
        url = f"{base_url.rstrip('/')}/ics/{remote_name}?t={token}"
        print(f"🔗 ICS feed: {url}")
    elif token:
        print(f"🔗 Token created for {args.username}: {token} (set ICS_BASE_URL to print full link)")
    else:
        print("ℹ️ Token not created; ensure CLOUDFLARE_API_TOKEN and CLOUDFLARE_KV_NAMESPACE_ID are set.")


if __name__ == "__main__":
    main()
