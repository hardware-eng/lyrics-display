#!/usr/bin/env python3
"""
docx_to_txt.py — convert a .docx to a cleaned shloka .txt via pandoc

Usage:
  python3 docx_to_txt.py <src.docx> <dst.txt>
  python3 docx_to_txt.py --strip-anvaya <src.docx> <dst.txt>
  python3 docx_to_txt.py --strip-english <src.docx> <dst.txt>

--strip-english: for bhajan-style docs that interleave English translations
  after each verse. Strips non-Devanagari paragraphs, converts .. N.. markers
  to ॥ N ॥, fixes dandas, and groups N-pada verses into single blocks.
"""

import argparse
import subprocess
import sys
import tempfile
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CLEAN_SCRIPT = SCRIPT_DIR / "clean_shloka.py"

_DEVANAGARI = re.compile(r'[ऀ-ॿ]')


def pandoc_to_plain(docx_path: Path) -> str:
    result = subprocess.run(
        ["pandoc", "-t", "plain", "--wrap=none", str(docx_path)],
        capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        print(f"pandoc error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def join_split_verses(text: str) -> str:
    """
    For Gita-style docs: pandoc emits each half-verse as a separate paragraph.
    Join pairs where paragraph A has no ॥ AND paragraph B has ॥.
    """
    paragraphs = re.split(r'\n\n+', text.strip())
    result = []
    i = 0
    while i < len(paragraphs):
        p = paragraphs[i]
        if (i + 1 < len(paragraphs)
                and '॥' not in p
                and '॥' in paragraphs[i + 1]):
            result.append(p + '\n' + paragraphs[i + 1])
            i += 2
        else:
            result.append(p)
            i += 1
    return '\n\n'.join(result)


def strip_english_and_group(text: str) -> str:
    """
    For bhajan-style docs with English translations after each verse:
    1. Convert .. N.. markers → ॥ N ॥
    2. Fix trailing single-danda: ' .' → ' ।'
    3. Strip non-Devanagari paragraphs (translations, attributions, appendix)
    4. Group consecutive padas into verse blocks (flush on ॥)
    """
    # Fix double-dot verse markers: .. १.. → ॥ १ ॥
    text = re.sub(r'\.\.\s*([^\s.]+)\s*\.\.',
                  lambda m: f'॥ {m.group(1)} ॥', text)

    # Fix trailing single danda: word . → word ।
    text = re.sub(r'\s+\.\s*$', ' ।', text, flags=re.MULTILINE)

    paragraphs = re.split(r'\n\n+', text.strip())
    result = []
    buf = []
    in_appendix = False

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue

        # Detect appendix / word-meanings section and stop
        if re.search(r'Appendix|Word meanings', p, re.IGNORECASE):
            in_appendix = True
            if buf:
                result.append('\n'.join(buf))
                buf = []
            continue
        if in_appendix:
            continue

        # Skip non-Devanagari paragraphs (English translations, stanza credits)
        if not _DEVANAGARI.search(p):
            continue

        # Accumulate Devanagari padas
        buf.append(p)

        # Flush the buffer when we reach a verse-ending marker ॥
        if '॥' in p:
            result.append('\n'.join(buf))
            buf = []

    if buf:
        result.append('\n'.join(buf))

    return '\n\n'.join(result)


def run_clean_shloka(text: str, strip_anvaya: bool) -> str:
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt',
                                    encoding='utf-8', delete=False) as tmp_in:
        tmp_in.write(text)
        tmp_in_path = tmp_in.name

    tmp_out_path = tmp_in_path + '.out'
    cmd = [sys.executable, str(CLEAN_SCRIPT)]
    if strip_anvaya:
        cmd.append('--strip-anvaya')
    cmd += [tmp_in_path, tmp_out_path]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"clean_shloka error: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    out = Path(tmp_out_path).read_text(encoding='utf-8')
    Path(tmp_in_path).unlink(missing_ok=True)
    Path(tmp_out_path).unlink(missing_ok=True)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--strip-anvaya', action='store_true')
    parser.add_argument('--strip-english', action='store_true',
                        help='Strip English translations (bhajan-style docs)')
    parser.add_argument('src', help='source .docx file')
    parser.add_argument('dst', help='destination .txt file')
    args = parser.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)

    print(f"  pandoc  {src.name} …", end=' ', flush=True)
    raw = pandoc_to_plain(src)

    print(f"join …", end=' ', flush=True)
    if args.strip_english:
        joined = strip_english_and_group(raw)
    else:
        joined = join_split_verses(raw)

    print(f"clean …", end=' ', flush=True)
    final = run_clean_shloka(joined, args.strip_anvaya)

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(final, encoding='utf-8')
    lines = final.count('\n') + 1
    print(f"done  ({lines} lines → {dst})")


if __name__ == "__main__":
    main()
