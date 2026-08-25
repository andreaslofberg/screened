#!/usr/bin/env python3
"""Export included records as Zotero-readable RIS.

Only rows already labelled include. Dual mode (optional -b): both screeners
must include. Never invents PMIDs or DOIs; MISSING fields are omitted.

Usage:
  python export_ris.py screening_log.csv -o includes.ris
  python export_ris.py log_a.csv -b log_b.csv -o includes.ris
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

MISSING = "MISSING"


def die(msg: str, code: int = 1) -> None:
    print(f"export_ris: {msg}", file=sys.stderr)
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


def present(val: str | None) -> str:
    v = (val or "").strip()
    if not v or v == MISSING:
        return ""
    return v


def ris_escape(text: str) -> str:
    return re.sub(r"\r\n|\r|\n", " ", text).strip()


def record_to_ris(row: dict[str, str]) -> str:
    lines = ["TY  - JOUR"]
    title = present(row.get("title"))
    if title:
        lines.append(f"TI  - {ris_escape(title)}")
    authors = present(row.get("authors"))
    if authors:
        for au in re.split(r";\s*", authors):
            au = au.strip()
            if au:
                lines.append(f"AU  - {ris_escape(au)}")
    year = present(row.get("year"))
    if year:
        lines.append(f"PY  - {year}")
    journal = present(row.get("journal"))
    if journal:
        lines.append(f"JO  - {ris_escape(journal)}")
    abstract = present(row.get("abstract"))
    if abstract:
        lines.append(f"AB  - {ris_escape(abstract)}")
    doi = present(row.get("doi"))
    if doi:
        lines.append(f"DO  - {doi}")
    pmid = present(row.get("pmid"))
    if pmid:
        lines.append(f"AN  - {pmid}")
        lines.append(f"C2  - {pmid}")
    rid = present(row.get("record_id"))
    if rid:
        lines.append(f"ID  - {rid}")
    lines.append("ER  - ")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="RIS export of includes. No invented identifiers.")
    p.add_argument("log_a", help="Screening log CSV")
    p.add_argument("-b", "--log-b", dest="log_b", help="Optional screener B; then both must include")
    p.add_argument("-o", "--out", required=True, help="Output .ris path")
    p.add_argument(
        "--any-include",
        action="store_true",
        help="With -b, export if either screener included (default: both)",
    )
    args = p.parse_args(argv)

    a_map = load_csv(args.log_a)
    b_map = load_csv(args.log_b) if args.log_b else None
    ids = list(a_map.keys()) if not b_map else list(dict.fromkeys([*a_map.keys(), *b_map.keys()]))

    chosen: list[dict[str, str]] = []
    for rid in ids:
        a = a_map.get(rid)
        da = (a or {}).get("decision", "").strip().lower()
        if b_map is None:
            if da == "include" and a:
                chosen.append(a)
            continue
        db = (b_map.get(rid) or {}).get("decision", "").strip().lower()
        ok = (da == "include" and db == "include") if not args.any_include else (da == "include" or db == "include")
        if ok:
            chosen.append(a or b_map[rid])

    blocks = [record_to_ris(r) for r in chosen]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")
    print(f"export_ris: {len(chosen)} include(s) → {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
