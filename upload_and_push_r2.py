"""Temporary script to ensure dotted ICS filenames and upload them to Cloudflare R2."""
import os
from pathlib import Path

import boto3
from botocore.client import Config
from dotenv import load_dotenv


ICS_DIR = Path(__file__).parent / "ics"


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
    s3 = session.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
    )
    return s3, bucket


def main():
    load_dotenv()

    s3, bucket = build_s3_client()

    if not ICS_DIR.exists():
        raise SystemExit(f"ICS directory not found: {ICS_DIR}")

    for src in sorted(ICS_DIR.glob("*.ics")):
        base_name = src.stem
        new_base = insert_dot_after_first_char(base_name)
        dst = src if new_base == base_name else src.with_name(f"{new_base}.ics")

        if src != dst:
            if dst.exists():
                dst.unlink()
            src.rename(dst)
            print(f"Renamed {src.name} -> {dst.name}")
        else:
            print(f"Keeping existing name {dst.name}")

        key = f"ics/{dst.name}"
        with open(dst, "rb") as fh:
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=fh,
                ContentType="text/calendar",
            )
        print(f"Uploaded to s3://{bucket}/{key}")


if __name__ == "__main__":
    main()
