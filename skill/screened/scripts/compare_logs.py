#!/usr/bin/env python3
"""Compare two independent screening logs (screener A vs screener B).

Writes a disagreement CSV: rows where A and B differ, plus unresolved maybes
(either screener chose maybe, or a label is missing).

Usage:
  python compare_logs.py log_a.csv log_b.csv -o disagreements.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

VALID = {"include", "maybe", "exclude"}


def die(msg: str, code: int = 1) -> None:
    print(f"compare_logs: {msg}", file=sys.stderr)
    raise SystemExit(code)


def load_csv(path: str) -> dict[str, dict[str, str]]:
    text_path = Path(path)
    if not text_path.exists():
        die(f"not found: {path}")
    by_id: dict[str, dict[str, str]] = {}
    with text_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "record_id" not in reader.fieldnames:
            die(f"{path}: need a record_id column")
        for row in reader:
            rid = (row.get("record_id") or "").strip()
            if not rid:
                continue
            by_id[rid] = row
    return by_id


def classify(a: str, b: str) -> str | None:
    """Return disagreement_type or None if this row is a clean agreement."""
    a = (a or "").strip().lower()
    b = (b or "").strip().lower()
    if not a and not b:
        return "missing_both"
    if not a:
        return "missing_a"
    if not b:
        return "missing_b"
    if a not in VALID:
        return "invalid_a"
    if b not in VALID:
        return "invalid_b"
    if a == "maybe" or b == "maybe":
        if a == b:
            return "unresolved_maybe"
        return "unresolved_maybe"
    if a != b:
        return "conflict"
    return None  # both include or both exclude


def pick(row: dict[str, str] | None, key: str, default: str = "") -> str:
    if not row:
        return default
    return row.get(key) or default


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Diff screener A vs B. Keep maybes as unresolved.")
    p.add_argument("log_a", help="CSV from write_log.py --screener A")
    p.add_argument("log_b", help="CSV from write_log.py --screener B")
    p.add_argument("-o", "--out", required=True, help="Disagreement CSV")
    p.add_argument("--all", action="store_true", help="Also emit agreeing rows (type=agree)")
    args = p.parse_args(argv)

    a_map = load_csv(args.log_a)
    b_map = load_csv(args.log_b)
    ids = list(dict.fromkeys([*a_map.keys(), *b_map.keys()]))

    cols = [
        "record_id",
        "disagreement_type",
        "decision_a",
        "decision_b",
        "reason_a",
        "reason_b",
        "confidence_a",
        "confidence_b",
        "title",
        "pmid",
        "doi",
        "dup_flag",
        "dup_of",
    ]
    rows: list[dict[str, str]] = []
    stats = {"conflict": 0, "unresolved_maybe": 0, "missing_a": 0, "missing_b": 0, "missing_both": 0, "agree": 0}

    for rid in ids:
        a = a_map.get(rid)
        b = b_map.get(rid)
        dec_a = pick(a, "decision")
        dec_b = pick(b, "decision")
        kind = classify(dec_a, dec_b)
        if kind is None:
            stats["agree"] += 1
            if not args.all:
                continue
            kind = "agree"
        else:
            stats[kind] = stats.get(kind, 0) + 1
        src = a or b or {}
        rows.append(
            {
                "record_id": rid,
                "disagreement_type": kind,
                "decision_a": dec_a,
                "decision_b": dec_b,
                "reason_a": pick(a, "reason"),
                "reason_b": pick(b, "reason"),
                "confidence_a": pick(a, "confidence"),
                "confidence_b": pick(b, "confidence"),
                "title": pick(src, "title"),
                "pmid": pick(src, "pmid"),
                "doi": pick(src, "doi"),
                "dup_flag": pick(src, "dup_flag"),
                "dup_of": pick(src, "dup_of"),
            }
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    n_dis = sum(stats[k] for k in stats if k != "agree")
    print(
        f"compare_logs: {len(ids)} paired · {stats['agree']} agree · "
        f"{n_dis} in disagreement file "
        f"(conflict {stats['conflict']}, unresolved_maybe {stats['unresolved_maybe']}, "
        f"missing_a {stats['missing_a']}, missing_b {stats['missing_b']}) → {out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
