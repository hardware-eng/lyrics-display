#!/usr/bin/env python3
"""
Clean a Devanagari shloka text file for the lyrics-display site.

Modes:
- default: BOM removal, drop *...* lines, strip indents, collapse spaces,
  normalize verse markers (॥ X-Y ॥), insert blanks around speaker labels,
  collapse 3+ blanks to 1.
- --strip-anvaya: also remove the duplicate "anvaya" (sandhi-broken) shloka
  blocks and the prose-explanation blocks that follow each shloka. Source
  files where each shloka appears as: sandhi block → anvaya block → prose
  block (each separated by blank lines).

Usage:
    python3 clean_shloka.py <input.txt> <output.txt>
    python3 clean_shloka.py --in-place <file.txt>
    python3 clean_shloka.py --strip-anvaya <input.txt> <output.txt>
"""
import re
import sys
from pathlib import Path

MARKER_RE = re.compile(r"॥\s*([०-९]+)\s*-\s*([०-९]+)\s*॥")


def is_speaker_line(line: str) -> bool:
    s = line.strip().rstrip("।").strip()
    return s.endswith("उवाच") or s.endswith("ुवाच") or s.endswith("नमः")


def is_prose_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if "(" in s or ")" in s:
        return True
    if s.rstrip("।॥ ").rstrip().endswith(","):
        return True
    return False


def force_prose_boundary(text: str) -> str:
    """Insert a blank line after any prose line that is immediately followed
    by a non-prose, non-blank line. Handles source files where the blank line
    between a prose-explanation block and the next shloka block is missing.
    """
    lines = text.split("\n")
    out = []
    for i, line in enumerate(lines):
        out.append(line)
        if i + 1 >= len(lines):
            continue
        nxt = lines[i + 1]
        if line.strip() == "" or nxt.strip() == "":
            continue
        if is_prose_line(line) and not is_prose_line(nxt):
            out.append("")
    return "\n".join(out)


def strip_anvaya(text: str) -> str:
    """Drop anvaya (duplicate) shloka blocks and prose-explanation blocks.

    Heuristic: blocks are separated by blank lines. Track shloka markers
    (॥ X-Y ॥) seen so far. For each block:
      - if it contains a marker we've seen before → drop (anvaya).
      - if it contains a new marker → keep entire block (sandhi shloka).
      - if no marker:
          * if any line is a speaker label (ends उवाच/ुवाच/नमः) → keep first line only.
          * if no markers seen yet (intro header) → keep first line only.
          * else → drop (prose explanation following anvaya).
    """
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    text = force_prose_boundary(text)
    raw_blocks = re.split(r"\n\s*\n", text)
    blocks = [[ln for ln in b.split("\n") if ln != ""] for b in raw_blocks]
    blocks = [b for b in blocks if b]

    seen = set()
    out_blocks: list[list[str]] = []

    for block in blocks:
        block_text = "\n".join(block)
        m = MARKER_RE.search(block_text)
        if m:
            key = (m.group(1), m.group(2))
            if key in seen:
                continue
            seen.add(key)
            out_blocks.append(block)
        else:
            has_speaker = any(is_speaker_line(ln) for ln in block)
            is_intro = not seen
            if has_speaker or is_intro:
                out_blocks.append([block[0]])
    return "\n\n".join("\n".join(b) for b in out_blocks) + "\n"


def clean(text: str) -> str:
    text = text.lstrip("﻿")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    out_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if re.fullmatch(r"\*[^*]+\*", stripped):
            continue
        if stripped == "":
            out_lines.append("")
        else:
            collapsed = re.sub(r" {2,}", " ", stripped)
            out_lines.append(collapsed)

    text = "\n".join(out_lines)

    text = MARKER_RE.sub(r"॥ \1-\2 ॥", text)
    text = re.sub(r"(॥ [०-९]+-[०-९]+ ॥)\s*॥+", r"\1", text)

    lines = text.split("\n")
    spaced = []
    for i, line in enumerate(lines):
        spaced.append(line)
        if i + 1 < len(lines):
            stripped = line.strip()
            next_stripped = lines[i + 1].strip()
            is_speaker = (
                stripped.endswith("उवाच")
                or stripped.endswith("ुवाच")
                or stripped.endswith("नमः")
            )
            if is_speaker and next_stripped:
                spaced.append("")
    text = "\n".join(spaced)

    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip("\n") + "\n"
    return text


def process(text: str, do_strip_anvaya: bool) -> str:
    if do_strip_anvaya:
        text = strip_anvaya(text)
    return clean(text)


def main():
    args = sys.argv[1:]
    do_anvaya = False
    if args and args[0] == "--strip-anvaya":
        do_anvaya = True
        args = args[1:]
    if len(args) == 2 and args[0] == "--in-place":
        path = Path(args[1])
        path.write_text(process(path.read_text(encoding="utf-8"), do_anvaya), encoding="utf-8")
    elif len(args) == 2:
        src, dst = Path(args[0]), Path(args[1])
        dst.write_text(process(src.read_text(encoding="utf-8"), do_anvaya), encoding="utf-8")
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
