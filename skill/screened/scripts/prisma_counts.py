#!/usr/bin/env python3
"""PRISMA 2020-style title/abstract counts from one or two screening logs.

A counts table, not a flow-diagram library. Dual logs add agreement rows.

Usage:
  python prisma_counts.py log_a.csv -o prisma_summary.md --csv prisma_counts.csv
  python prisma_counts.py log_a.csv -b log_b.csv --records records.jsonl -o prisma_summary.md
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID = {"include", "maybe", "exclude"}


def die(msg: str, code: int = 1) -> None:
    print(f"prisma_counts: {msg}", file=sys.stderr)
    raise SystemExit(code)


def load_csv(path: str) -> dict[str, dict[str, str]]:
    by_id: dict[str, dict[str, str]] = {}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "record_id" not in (reader.fieldnames or []):
            die(f"{path}: need a record_id column")
        for row in reader:
            rid = (row.get("record_id") or "").strip()
            if rid:
                by_id[rid] = row
    return by_id


def load_jsonl(path: str) -> list[dict[str, Any]]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def dec(row: dict[str, str] | None) -> str:
    if not row:
        return ""
    return (row.get("decision") or "").strip().lower()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="PRISMA-style counts table from screening log(s).")
    p.add_argument("log_a", help="Primary screening log CSV (screener A, or sole screener)")
    p.add_argument("-b", "--log-b", dest="log_b", help="Optional screener B log CSV")
    p.add_argument("--records", help="Optional records.jsonl (identified N + dup flags)")
    p.add_argument("-o", "--out", required=True, help="Markdown summary path")
    p.add_argument("--csv", dest="csv_out", help="Also write a two-column CSV of counts")
    p.add_argument("--title", default="Screened — PRISMA-style title/abstract counts")
    args = p.parse_args(argv)

    a_map = load_csv(args.log_a)
    b_map: dict[str, dict[str, str]] = load_csv(args.log_b) if args.log_b else {}

    records: list[dict[str, Any]] = []
    if args.records:
        records = load_jsonl(args.records)

    ids = list(dict.fromkeys(
        [str(r.get("record_id")) for r in records if r.get("record_id")]
        + list(a_map.keys())
        + list(b_map.keys())
    ))
    identified = len(ids) if ids else max(len(a_map), len(b_map))

    def row_for(rid: str) -> dict[str, str]:
        return a_map.get(rid) or b_map.get(rid) or {}

    rec_by_id = {str(r.get("record_id")): r for r in records}

    n_dup_records = 0
    n_dup_clusters = set()
    n_missing_abs = 0
    n_missing_pmid = 0
    n_missing_doi = 0
    for rid in ids:
        src = rec_by_id.get(rid) or row_for(rid)
        flag = str(src.get("dup_flag") or "")
        if flag == "yes":
            n_dup_records += 1
            n_dup_clusters.add(str(src.get("dup_of") or rid))
        if str(src.get("abstract_present") or "") == "no" or str(src.get("abstract") or "") in {"", "MISSING"}:
            n_missing_abs += 1
        if str(src.get("pmid") or "MISSING") in {"", "MISSING"}:
            n_missing_pmid += 1
        if str(src.get("doi") or "MISSING") in {"", "MISSING"}:
            n_missing_doi += 1

    def tally(mmap: dict[str, dict[str, str]]) -> dict[str, int]:
        c = Counter()
        for rid in ids:
            d = dec(mmap.get(rid))
            if d in VALID:
                c[d] += 1
            else:
                c["unlabelled"] += 1
        c["screened"] = c["include"] + c["maybe"] + c["exclude"]
        return dict(c)

    tall_a = tally(a_map) if a_map or not b_map else tally({})
    # If only A, tally from union ids using A.
    if not a_map and ids:
        tall_a = tally(a_map)

    dual = bool(args.log_b)
    tall_b = tally(b_map) if dual else {}

    agree_include = agree_exclude = conflict = unresolved = missing = 0
    if dual:
        for rid in ids:
            da, db = dec(a_map.get(rid)), dec(b_map.get(rid))
            if not da or not db:
                missing += 1
                continue
            if da == "include" and db == "include":
                agree_include += 1
            elif da == "exclude" and db == "exclude":
                agree_exclude += 1
            elif da == "maybe" or db == "maybe":
                unresolved += 1
            elif da != db:
                conflict += 1
            else:
                unresolved += 1  # both maybe already caught

    # Conservative "forward to full text" figure:
    # single log: includes; dual: both-include (conflicts stay unresolved).
    if dual:
        included_forward = agree_include
        excluded_consensus = agree_exclude
        maybe_unresolved = unresolved + conflict + missing
        screened_n = identified - missing if identified else (agree_include + agree_exclude + unresolved + conflict)
        # screened = both labelled
        both_labelled = identified - missing
        screened_n = both_labelled
    else:
        included_forward = tall_a.get("include", 0)
        excluded_consensus = tall_a.get("exclude", 0)
        maybe_unresolved = tall_a.get("maybe", 0) + tall_a.get("unlabelled", 0)
        screened_n = tall_a.get("screened", 0)

    items: list[tuple[str, int, str]] = [
        ("identified", identified, "Records entering title/abstract screening (parser output; nothing invented)"),
        ("duplicates_flagged", n_dup_records, "Rows flagged as DOI/PMID/title duplicates — not dropped"),
        ("duplicate_clusters", len(n_dup_clusters), "Duplicate clusters (canonical + copies)"),
        ("screened", screened_n, "Records with a decision" + (" from both screeners" if dual else "")),
        ("included_retrieve_full_text", included_forward, "include = retrieve full text, not a final include"),
        ("excluded", excluded_consensus, "Title/abstract excludes" + (" (both screeners)" if dual else "")),
        ("maybe_or_unresolved", maybe_unresolved, "maybe, conflicts, and/or unlabelled"),
    ]
    if not dual:
        items.extend(
            [
                ("include", tall_a.get("include", 0), "Decision = include"),
                ("maybe", tall_a.get("maybe", 0), "Decision = maybe"),
                ("exclude", tall_a.get("exclude", 0), "Decision = exclude"),
                ("unlabelled", tall_a.get("unlabelled", 0), "No decision yet"),
            ]
        )
    else:
        items.extend(
            [
                ("screener_a_include", tall_a.get("include", 0), "A include (independent)"),
                ("screener_a_maybe", tall_a.get("maybe", 0), "A maybe"),
                ("screener_a_exclude", tall_a.get("exclude", 0), "A exclude"),
                ("screener_b_include", tall_b.get("include", 0), "B include (independent)"),
                ("screener_b_maybe", tall_b.get("maybe", 0), "B maybe"),
                ("screener_b_exclude", tall_b.get("exclude", 0), "B exclude"),
                ("both_include", agree_include, "A and B both include"),
                ("both_exclude", agree_exclude, "A and B both exclude"),
                ("conflict_a_ne_b", conflict, "A and B differ (neither maybe)"),
                ("unresolved_maybe", unresolved, "Either/both maybe"),
                ("missing_a_or_b", missing, "One or both screeners have not labelled"),
            ]
        )

    items.extend(
        [
            ("abstract_missing", n_missing_abs, "abstract MISSING"),
            ("pmid_missing", n_missing_pmid, "pmid MISSING (not invented)"),
            ("doi_missing", n_missing_doi, "doi MISSING (not invented)"),
        ]
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        f"# {args.title}",
        "",
        f"_Generated {now} by Screened v0.2. Counts table, not a PRISMA flow-diagram drawing._",
        "",
        "**Not clinical advice.** `include` at this stage means retrieve full text.",
        "Human confirmation is still required. Dual independent screening is the methods standard.",
        "",
        "| Stage | N | Note |",
        "|---|---:|---|",
    ]
    for key, n, note in items:
        label = key.replace("_", " ")
        lines.append(f"| {label} | {n} | {note} |")
    lines += [
        "",
        "## How to read this",
        "",
        "- **Identified** is the number of records the parser emitted. Duplicates are *flagged*, not silently removed, so identified is not reduced.",
        "- **Included** here is title/abstract include (forward to full text). Final inclusion is a later human stage this tool does not do.",
        "- **Maybe / unresolved** includes thin abstracts, title-only records, and (in dual mode) conflicts plus maybes. Resolve those by consensus or a third reviewer — not by re-running the model as both A and B.",
        "",
        "EU AI Act Art. 50: if labels came from the Cursor/Claude skill they are AI-assisted drafts, not determinations.",
        "No PMIDs or DOIs were invented by this script.",
        "",
    ]
    md = "\n".join(lines)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")

    if args.csv_out:
        with Path(args.csv_out).open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["stage", "n", "note"])
            for key, n, note in items:
                w.writerow([key, n, note])
        print(f"prisma_counts: csv → {args.csv_out}", file=sys.stderr)

    print(f"prisma_counts: identified {identified} → {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
