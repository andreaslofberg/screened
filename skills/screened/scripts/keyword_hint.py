#!/usr/bin/env python3
"""Cheap keyword overlap hints for title/abstract screening.

NOT a screening decision. Use to sort obvious excludes to the bottom, or to
show matched phrases next to a record. The human (and the skill's LLM pass)
still decide.

Usage:
  python keyword_hint.py records.jsonl --include inc.txt --exclude exc.txt
  python keyword_hint.py records.jsonl --criteria criteria.md -o hints.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

STOP = {
    "a", "an", "the", "of", "and", "or", "to", "in", "for", "with", "on",
    "by", "from", "at", "as", "is", "are", "be", "this", "that", "these",
    "those", "study", "studies", "effect", "effects", "using", "based",
    "among", "into", "than", "yes", "both", "either", "only", "least",
    "one", "at",
}
# Keep negations in phrases ("no sleep outcome" must not become "sleep outcome").
NEG = {"no", "not", "without", "non", "nor"}

MIN_PHRASE = 4


def die(msg: str, code: int = 1) -> None:
    print(f"keyword_hint: {msg}", file=sys.stderr)
    raise SystemExit(code)


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def phrases_from(text: str) -> list[str]:
    lines = []
    for raw in re.split(r"[\n;]+", text):
        raw = raw.strip()
        raw = re.sub(r"^[\-\*\d\.\)\]]+\s*", "", raw)
        if not raw:
            continue
        if re.search(r"\bor\b", raw, flags=re.I):
            raw = re.sub(r"\s*,\s*", " or ", raw)
        parts = re.split(r"\s+\bor\b\s+", raw, flags=re.I)
        for part in parts:
            part = normalize(part)
            words = part.split()
            while words and words[0] in STOP and words[0] not in NEG:
                words.pop(0)
            phrase = " ".join(words)
            if len(phrase) >= MIN_PHRASE:
                lines.append(phrase)
    seen = set()
    out = []
    for p in lines:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def split_criteria_file(text: str) -> tuple[str, str]:
    inc, exc = [], []
    bucket = None
    for line in text.splitlines():
        h = line.strip().lower()
        if re.match(r"^#{1,3}\s*inclu", h) or h.startswith("inclusion"):
            bucket = "inc"
            continue
        if re.match(r"^#{1,3}\s*exclu", h) or h.startswith("exclusion"):
            bucket = "exc"
            continue
        if re.match(r"^#{1,3}\s+", h):
            bucket = None
            continue
        if bucket == "inc":
            inc.append(line)
        elif bucket == "exc":
            exc.append(line)
    return "\n".join(inc), "\n".join(exc)


def _matches(hay: str, phrase: str) -> bool:
    if not phrase:
        return False
    if phrase in hay:
        return True
    # light plural: criteria "protocols" vs abstract "protocol"
    if " " not in phrase and phrase.endswith("s") and len(phrase) >= 5 and phrase[:-1] in hay:
        return True
    return False


def hits(hay: str, phrases: list[str]) -> list[str]:
    found = []
    for p in phrases:
        if _matches(hay, p):
            found.append(p)
    return found


def hint_for(title: str, abstract: str, inc: list[str], exc: list[str]) -> dict[str, Any]:
    hay = normalize(f"{title} {abstract}")
    inc_hits = hits(hay, inc)
    exc_hits = hits(hay, exc)
    if exc_hits and not inc_hits:
        suggestion = "exclude"
        why = "exclude-phrase match, no include-phrase match"
    elif inc_hits and not exc_hits:
        suggestion = "include"
        why = "include-phrase match, no exclude-phrase match"
    elif inc_hits and exc_hits:
        suggestion = "maybe"
        why = "both include and exclude phrases matched"
    else:
        suggestion = "maybe"
        why = "no phrase overlap — insufficient for a keyword hint"
    return {
        "suggestion": suggestion,
        "why": why,
        "include_hits": inc_hits,
        "exclude_hits": exc_hits,
        "note": "keyword hint only; not a screening decision",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Keyword overlap hints. Not a screening decision.")
    p.add_argument("records", help="JSONL from parse_records.py")
    p.add_argument("--include", dest="inc_file", help="Inclusion criteria text file")
    p.add_argument("--exclude", dest="exc_file", help="Exclusion criteria text file")
    p.add_argument("--criteria", help="Markdown with Inclusion / Exclusion headings")
    p.add_argument("-o", "--out", help="Write hints JSONL (default stdout)")
    args = p.parse_args(argv)

    inc_text, exc_text = "", ""
    if args.criteria:
        inc_text, exc_text = split_criteria_file(Path(args.criteria).read_text(encoding="utf-8"))
    if args.inc_file:
        inc_text = Path(args.inc_file).read_text(encoding="utf-8")
    if args.exc_file:
        exc_text = Path(args.exc_file).read_text(encoding="utf-8")
    if not inc_text and not exc_text:
        die("provide --criteria or --include/--exclude", 2)

    inc = phrases_from(inc_text)
    exc = phrases_from(exc_text)
    rows = []
    for i, line in enumerate(Path(args.records).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        rec = json.loads(line)
        h = hint_for(str(rec.get("title", "")), str(rec.get("abstract", "")), inc, exc)
        h["record_id"] = rec.get("record_id")
        rows.append(h)

    payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)

    counts = {k: sum(1 for r in rows if r["suggestion"] == k) for k in ("include", "maybe", "exclude")}
    print(
        f"keyword_hint: {len(rows)} hints | "
        f"include-ish {counts['include']} / maybe {counts['maybe']} / exclude-ish {counts['exclude']} | "
        f"{len(inc)} include phrases, {len(exc)} exclude phrases. NOT decisions.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
