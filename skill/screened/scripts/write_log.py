#!/usr/bin/env python3
"""Merge parsed records with screening decisions into a CSV log.

Refuses to write invented PMIDs or DOIs. Decisions may not introduce
identifiers that were not present in the parsed source records.

Usage:
  python write_log.py records.jsonl decisions.jsonl -o screening_log.csv
  python write_log.py records.jsonl decisions.jsonl -o log_a.csv --screener A --progress progress_a.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MISSING = "MISSING"
VALID_DECISIONS = {"include", "maybe", "exclude"}
VALID_CONFIDENCE = {"high", "low"}
PMID_RE = re.compile(r"^\d{1,8}$")

COLUMNS = [
    "record_id",
    "decision",
    "reason",
    "criteria_hit",
    "confidence",
    "title",
    "abstract_present",
    "abstract",
    "authors",
    "year",
    "journal",
    "pmid",
    "doi",
    "source_format",
    "source_file",
    "missing_fields",
    "identifier_status",
    "reviewer",
    "screened_at",
    "notes",
    "human_confirmed",
    "screener",
    "dup_flag",
    "dup_of",
    "dup_key",
]


def die(msg: str, code: int = 1) -> None:
    print(f"write_log: {msg}", file=sys.stderr)
    raise SystemExit(code)


def load_jsonl(path: str) -> list[dict[str, Any]]:
    rows = []
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    for i, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            die(f"{path}:{i}: {e}")
        if not isinstance(obj, dict):
            die(f"{path}:{i}: expected object")
        rows.append(obj)
    return rows


def same_id(a: str, b: str) -> bool:
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b or a == MISSING or b == MISSING:
        return False
    return a.lower() == b.lower()


def guard_identifier(kind: str, source_val: str, decision_val: str, record_id: str) -> str:
    """Return the source identifier. Reject invented or altered values."""
    src = (source_val or "").strip() or MISSING
    proposed = (decision_val or "").strip()
    if not proposed or proposed == MISSING:
        return src
    if src == MISSING:
        die(
            f"{record_id}: decision tried to add {kind} '{proposed}' but source has none. "
            "Never invent identifiers. Leave it MISSING."
        )
    if not same_id(src, proposed):
        die(
            f"{record_id}: decision {kind} '{proposed}' does not match source '{src}'. "
            "Do not alter identifiers."
        )
    return src


def one_line(text: str, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Write a screening log CSV. Blocks invented identifiers.")
    p.add_argument("records", help="JSONL from parse_records.py")
    p.add_argument("decisions", help="JSONL of {record_id, decision, reason, ...}")
    p.add_argument("-o", "--out", required=True, help="Output CSV path")
    p.add_argument(
        "--reviewer",
        default=None,
        help="Value for the reviewer column (default depends on --screener)",
    )
    p.add_argument(
        "--screener",
        choices=["A", "B"],
        help="Independent screener label written to the screener column",
    )
    p.add_argument(
        "--progress",
        help="Write a JSON progress file (completed vs remaining record_ids) so a long run can resume",
    )
    args = p.parse_args(argv)

    if args.reviewer is None:
        if args.screener:
            args.reviewer = f"screener-{args.screener} (human must confirm)"
        else:
            args.reviewer = "AI-draft (human must confirm)"

    records = load_jsonl(args.records)
    decisions = load_jsonl(args.decisions)
    if not records:
        die("no records")
    if not decisions:
        die("no decisions")

    by_id = {r["record_id"]: r for r in records}
    if len(by_id) != len(records):
        die("duplicate record_id in records JSONL")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    unseen = []
    for d in decisions:
        rid = str(d.get("record_id", "")).strip()
        if rid not in by_id:
            unseen.append(rid or "<empty>")
            continue
        rec = by_id[rid]
        decision = str(d.get("decision", "")).strip().lower()
        if decision not in VALID_DECISIONS:
            die(f"{rid}: decision must be include|maybe|exclude, got '{decision}'")
        reason = one_line(str(d.get("reason", "")))
        if not reason:
            die(f"{rid}: reason is required (one line)")
        confidence = str(d.get("confidence", "low")).strip().lower()
        if confidence not in VALID_CONFIDENCE:
            die(f"{rid}: confidence must be high|low")

        pmid = guard_identifier("pmid", rec.get("pmid", MISSING), str(d.get("pmid", "")), rid)
        doi = guard_identifier("doi", rec.get("doi", MISSING), str(d.get("doi", "")), rid)
        if pmid != MISSING and not PMID_RE.match(pmid):
            die(f"{rid}: source PMID is not a digit string; refusing to emit it as a PMID")

        rows.append(
            {
                "record_id": rid,
                "decision": decision,
                "reason": reason,
                "criteria_hit": one_line(str(d.get("criteria_hit", "")), 160),
                "confidence": confidence,
                "title": rec.get("title", MISSING),
                "abstract_present": rec.get("abstract_present", "no"),
                "abstract": rec.get("abstract", MISSING),
                "authors": rec.get("authors", MISSING),
                "year": rec.get("year", MISSING),
                "journal": rec.get("journal", MISSING),
                "pmid": pmid,
                "doi": doi,
                "source_format": rec.get("source_format", ""),
                "source_file": rec.get("source_file", ""),
                "missing_fields": rec.get("missing_fields", ""),
                "identifier_status": rec.get("identifier_status", ""),
                "reviewer": args.reviewer,
                "screened_at": str(d.get("screened_at") or now),
                "notes": one_line(str(d.get("notes", "")), 240),
                "human_confirmed": "no",
                "screener": args.screener or str(d.get("screener") or ""),
                "dup_flag": rec.get("dup_flag") or "no",
                "dup_of": rec.get("dup_of") or "",
                "dup_key": rec.get("dup_key") or "",
            }
        )

    if unseen:
        die("decisions reference unknown record_id(s): " + ", ".join(unseen[:8]))

    decided = {r["record_id"] for r in rows}
    leftover = [r["record_id"] for r in records if r["record_id"] not in decided]
    if leftover:
        print(
            f"write_log: warning: {len(leftover)} records have no decision "
            f"(first: {', '.join(leftover[:5])})",
            file=sys.stderr,
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

    counts = {k: sum(1 for r in rows if r["decision"] == k) for k in ("include", "maybe", "exclude")}
    n_missing_abs = sum(1 for r in rows if r["abstract_present"] == "no")
    print(
        f"write_log: {len(rows)} rows → {out_path} | "
        f"include {counts['include']} / maybe {counts['maybe']} / exclude {counts['exclude']} | "
        f"{n_missing_abs} without abstract. human_confirmed=no for every row"
        + (f" | screener {args.screener}" if args.screener else "")
        + ".",
        file=sys.stderr,
    )

    if args.progress:
        import json as _json
        completed = [r["record_id"] for r in rows]
        remaining = leftover
        payload = {
            "version": "0.2.0",
            "screener": args.screener or "",
            "log": str(out_path),
            "total": len(records),
            "n_completed": len(completed),
            "n_remaining": len(remaining),
            "completed": completed,
            "remaining": remaining,
            "counts": counts,
        }
        prog = Path(args.progress)
        prog.parent.mkdir(parents=True, exist_ok=True)
        prog.write_text(_json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(
            f"write_log: progress → {prog} ({len(completed)} done, {len(remaining)} remaining).",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
