#!/usr/bin/env python3
"""
collect_lyrics.py — walk the spiritual/ tree, copy every z_lyrics/ folder
                    into z-temp-github-lyrics/lyrics/<parent-path>/
                    then write manifest.json listing all folders and files.

Usage:
  python3 collect_lyrics.py            # copy new/changed files + update manifest
  python3 collect_lyrics.py --dry-run  # preview without writing anything
"""

import argparse
import json
import shutil
from pathlib import Path

SCRIPT_DIR    = Path(__file__).resolve().parent
STAGING_DIR   = SCRIPT_DIR.parent          # z-temp-github-lyrics/
SPIRITUAL_DIR = STAGING_DIR.parent         # spiritual/
DEST_ROOT     = STAGING_DIR / "lyrics"


def to_label(name: str) -> str:
    return name.replace("_", " ").title()


def collect(dry: bool) -> None:
    if dry:
        print("[DRY RUN] — no files will be written\n")

    copied = skipped = 0

    for z_dir in sorted(SPIRITUAL_DIR.rglob("z_lyrics")):
        if not z_dir.is_dir():
            continue

        # Skip anything that lives inside our own staging folder (avoid loop)
        try:
            z_dir.relative_to(STAGING_DIR)
            continue
        except ValueError:
            pass

        # e.g. bhagvad_gita  or  bhagvad_gita/adhyay_01
        rel_parent = z_dir.parent.relative_to(SPIRITUAL_DIR)
        dest_dir   = DEST_ROOT / rel_parent

        for src in sorted(z_dir.rglob("*.txt")):
            if not src.is_file():
                continue
            dst = dest_dir / src.relative_to(z_dir)

            if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
                print(f"  skip   {dst.relative_to(STAGING_DIR)}")
                skipped += 1
                continue

            tag = " new " if not dst.exists() else "update"
            print(f"  {tag}  {src.relative_to(SPIRITUAL_DIR)}  →  {dst.relative_to(STAGING_DIR)}")
            if not dry:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            copied += 1

    action = "would copy" if dry else "copied"
    print(f"\nDone: {copied} file(s) {action}, {skipped} already up to date.")

    # Build manifest from whatever is now in lyrics/
    manifest = build_manifest()
    folder_count = len(manifest["folders"])
    def _count_files(folder):
        if "files" in folder:
            return len(folder["files"])
        return sum(_count_files(s) for s in folder.get("folders", []))
    file_count = sum(_count_files(f) for f in manifest["folders"])

    manifest_path = STAGING_DIR / "manifest.json"
    if not dry:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        print(f"  wrote  manifest.json  ({folder_count} folder(s), {file_count} file(s))")
    else:
        print(f"  [dry]  would write manifest.json  ({folder_count} folder(s), {file_count} file(s))")

    if not dry:
        print(f"""
── Next steps to publish ─────────────────────────────────────────────
1. Sync everything to repo:
     rsync -av --delete \\
       --exclude=.git/ --exclude=memory/ \\
       {STAGING_DIR}/ ~/lyrics-display/

2. Commit and push:
     cd ~/lyrics-display && git add -A && git commit -m "update lyrics" && git push
──────────────────────────────────────────────────────────────────────
""")


def load_mp3_urls() -> dict:
    """
    Walk source tree for z_mp3/urls.json files.
    Returns {(top_folder_name, stem): url}.
    """
    urls = {}
    for urls_file in sorted(SPIRITUAL_DIR.rglob("z_mp3/urls.json")):
        try:
            urls_file.relative_to(STAGING_DIR)
            continue  # skip staging area
        except ValueError:
            pass
        top_folder = urls_file.relative_to(SPIRITUAL_DIR).parts[0]
        data = json.loads(urls_file.read_text(encoding="utf-8"))
        for stem, url in data.items():
            urls[(top_folder, stem)] = url
    return urls


def _file_entry(f: Path, mp3_urls: dict) -> dict:
    rel_file  = f.relative_to(DEST_ROOT)
    top_folder = rel_file.parts[0]
    entry = {"label": to_label(f.stem),
             "path": "lyrics/" + str(rel_file).replace("\\", "/")}
    url = mp3_urls.get((top_folder, f.stem))
    if url:
        entry["mp3"] = url
    return entry


def build_manifest() -> dict:
    """
    Build a manifest that preserves folder hierarchy.
    - Leaf folder (only .txt files, no subdirs): {"id", "label", "files"}
    - Nested folder (has subdirs with .txt files): {"id", "label", "folders"}
    Each file entry gets an optional "mp3" key when a URL exists in z_mp3/urls.json.
    """
    mp3_urls = load_mp3_urls()
    folders  = []
    if not DEST_ROOT.exists():
        return {"folders": folders}

    for folder_dir in sorted(DEST_ROOT.iterdir()):
        if not folder_dir.is_dir():
            continue

        label    = to_label(folder_dir.name)
        subdirs  = sorted(d for d in folder_dir.iterdir() if d.is_dir())
        direct   = sorted(f for f in folder_dir.iterdir()
                          if f.is_file() and f.suffix == ".txt")

        if subdirs:
            # Nested folder — build one entry per person subfolder
            subfolders = []
            for sub in subdirs:
                sub_files = sorted(sub.rglob("*.txt"))
                if sub_files:
                    subfolders.append({
                        "id":    sub.name,
                        "label": to_label(sub.name),
                        "files": [_file_entry(f, mp3_urls) for f in sub_files],
                    })
            if subfolders:
                folders.append({"id": folder_dir.name, "label": label,
                                "folders": subfolders})
        elif direct:
            # Leaf folder — files sit directly here
            folders.append({"id": folder_dir.name, "label": label,
                            "files": [_file_entry(f, mp3_urls) for f in direct]})

    return {"folders": folders}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect z_lyrics/ files into the staging area"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be copied without writing")
    args = parser.parse_args()
    collect(dry=args.dry_run)


if __name__ == "__main__":
    main()
