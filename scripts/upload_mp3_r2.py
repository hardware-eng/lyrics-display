#!/usr/bin/env python3
"""
upload_mp3_r2.py — upload z_mp3/ files to Cloudflare R2 and write urls.json

Usage:
  python3 upload_mp3_r2.py                  # upload new/changed files
  python3 upload_mp3_r2.py --dry-run        # preview without uploading
  python3 upload_mp3_r2.py --folder shiva   # single top-level folder only

Config: reads from ~/.r2_config (created on first run if missing).

urls.json is written next to each z_mp3/ folder:
  spiritual/bhagvad_gita/z_mp3/urls.json
  spiritual/pushtimarg/z_mp3/urls.json
  ...

Format:
  { "adhyay_01": "https://pub-XXX.r2.dev/bhagvad_gita/adhyay_01.mp3", ... }
"""

import argparse
import json
import sys
import os
from pathlib import Path

SCRIPT_DIR    = Path(__file__).resolve().parent
STAGING_DIR   = SCRIPT_DIR.parent
SPIRITUAL_DIR = STAGING_DIR.parent
CONFIG_PATH   = Path.home() / ".r2_config"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    print("No ~/.r2_config found. Let's create it.")
    cfg = {
        "account_id":      input("Cloudflare Account ID: ").strip(),
        "access_key_id":   input("R2 Access Key ID: ").strip(),
        "secret_key":      input("R2 Secret Access Key: ").strip(),
        "bucket":          input("Bucket name (e.g. spiritual-audio): ").strip(),
        "public_url":      input("Public bucket URL (e.g. https://pub-XXX.r2.dev): ").strip().rstrip("/"),
    }
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    CONFIG_PATH.chmod(0o600)
    print(f"Saved to {CONFIG_PATH}\n")
    return cfg


def get_s3_client(cfg: dict):
    sys.path.insert(0, '/home/nirav/.local/lib/python3.12/site-packages')
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=f"https://{cfg['account_id']}.r2.cloudflarestorage.com",
        aws_access_key_id=cfg["access_key_id"],
        aws_secret_access_key=cfg["secret_key"],
        region_name="auto",
    )


def upload_folder(z_mp3_dir: Path, cfg: dict, s3, dry: bool) -> dict:
    """Upload all mp3s in z_mp3_dir, return {stem: public_url} map."""
    rel_parent = z_mp3_dir.parent.relative_to(SPIRITUAL_DIR)
    urls = {}

    # Load existing urls.json if present
    urls_path = z_mp3_dir / "urls.json"
    if urls_path.exists():
        urls = json.loads(urls_path.read_text())

    for src in sorted(z_mp3_dir.rglob("*.mp3")):
        rel = src.relative_to(z_mp3_dir)
        key = str(rel_parent / rel).replace("\\", "/")   # e.g. bhagvad_gita/adhyay_01.mp3
        stem = src.stem
        public_url = f"{cfg['public_url']}/{key}"

        # Check if already uploaded (URL already in map and matches)
        if stem in urls and urls[stem] == public_url:
            print(f"  skip   {key}")
            continue

        print(f"  upload {key}  ({src.stat().st_size // 1024 // 1024}MB)", end=" ", flush=True)
        if not dry:
            s3.upload_file(
                str(src), cfg["bucket"], key,
                ExtraArgs={"ContentType": "audio/mpeg"}
            )
            urls[stem] = public_url
            print("✓")
        else:
            print("[dry]")

    if not dry:
        urls_path.write_text(json.dumps(urls, indent=2, sort_keys=True))
        print(f"  wrote  {urls_path.relative_to(SPIRITUAL_DIR)}")

    return urls


def main():
    parser = argparse.ArgumentParser(description="Upload z_mp3/ folders to Cloudflare R2")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--folder", help="Limit to one top-level folder (e.g. bhagvad_gita)")
    args = parser.parse_args()

    cfg = load_config()
    s3  = None if args.dry_run else get_s3_client(cfg)

    total = 0
    for z_mp3 in sorted(SPIRITUAL_DIR.rglob("z_mp3")):
        if not z_mp3.is_dir():
            continue
        try:
            z_mp3.relative_to(STAGING_DIR)
            continue  # skip staging area itself
        except ValueError:
            pass

        if args.folder:
            rel = z_mp3.relative_to(SPIRITUAL_DIR)
            if rel.parts[0] != args.folder:
                continue

        print(f"\n── {z_mp3.relative_to(SPIRITUAL_DIR)} ──")
        urls = upload_folder(z_mp3, cfg, s3, args.dry_run)
        total += len(urls)

    print(f"\nDone: {total} file(s) tracked in urls.json")


if __name__ == "__main__":
    main()
