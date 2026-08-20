#!/usr/bin/env python3
"""Flag duplicate records by DOI, PMID, or normalized title.

Does NOT drop rows. Clusters are flagged so a human can decide. Missing
identifiers never match (MISSING != MISSING).

Usage:
  python dedup_records.py records.jsonl -o records.jsonl --report dups.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

MISSING = "MISSING"
MIN_TITLE_LEN = 12


def die(msg: str, code: int = 1) -> None:
    print(f"dedup_records: {msg}", file=sys.stderr)
    raise SystemExit(code)


def normalize_title(title: str) -> str:
    text = (title or "").lower()
    if text == MISSING.lower():
        return ""
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class UF:
    def __init__(self, n: int) -> None:
        self.p = list(range(n))

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def load_jsonl(path: str) -> list[dict[str, Any]]:
    rows = []
    for i, line in enumerate(Path(path).read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
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


def key_doi(rec: dict[str, Any]) -> str:
    v = str(rec.get("doi") or "").strip()
    if not v or v == MISSING:
        return ""
    return "doi:" + v.lower()


def key_pmid(rec: dict[str, Any]) -> str:
    v = str(rec.get("pmid") or "").strip()
    if not v or v == MISSING:
        return ""
    return "pmid:" + v


def key_title(rec: dict[str, Any]) -> str:
    t = str(rec.get("title_normalized") or "").strip()
    if not t:
        t = normalize_title(str(rec.get("title") or ""))
    if not t or t == MISSING.lower() or len(t) < MIN_TITLE_LEN:
        return ""
    return "title:" + t


def strongest_shared_key(a: dict[str, Any], b: dict[str, Any]) -> str:
    da, db = key_doi(a), key_doi(b)
    if da and da == db:
        return da
    pa, pb = key_pmid(a), key_pmid(b)
    if pa and pa == pb:
        return pa
    ta, tb = key_title(a), key_title(b)
    if ta and ta == tb:
        return ta
    return ""


def flag_duplicates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    n = len(records)
    uf = UF(n)
    buckets: dict[str, list[int]] = {}

    for i, rec in enumerate(records):
        if not rec.get("title_normalized"):
            rec["title_normalized"] = normalize_title(str(rec.get("title") or ""))
        for key in (key_doi(rec), key_pmid(rec), key_title(rec)):
            if not key:
                continue
            buckets.setdefault(key, []).append(i)

    for idxs in buckets.values():
        if len(idxs) < 2:
            continue
        head = idxs[0]
        for j in idxs[1:]:
            uf.union(head, j)

    clusters: dict[int, list[int]] = {}
    for i in range(n):
        clusters.setdefault(uf.find(i), []).append(i)

    n_flagged = 0
    n_clusters = 0
    for members in clusters.values():
        members.sort()
        if len(members) == 1:
            rec = records[members[0]]
            rec["dup_flag"] = "no"
            rec["dup_of"] = ""
            rec["dup_key"] = ""
            rec["dup_cluster_size"] = 1
            rec["dup_canonical"] = "yes"
            continue
        n_clusters += 1
        canonical_i = members[0]
        canonical_id = str(records[canonical_i].get("record_id", ""))
        # Prefer a DOI/PMID key that actually ties the cluster.
        shared = ""
        for i in members[1:]:
            shared = strongest_shared_key(records[canonical_i], records[i])
            if shared:
                break
        if not shared:
            shared = key_title(records[canonical_i]) or "cluster"
        for i in members:
            rec = records[i]
            rec["dup_flag"] = "yes"
            rec["dup_of"] = canonical_id
            rec["dup_key"] = shared
            rec["dup_cluster_size"] = len(members)
            rec["dup_canonical"] = "yes" if i == canonical_i else "no"
            n_flagged += 1
    return records


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Flag duplicates by DOI/PMID/title. Never drops rows.")
    p.add_argument("records", help="JSONL from parse_records.py")
    p.add_argument("-o", "--out", help="Write flagged JSONL (default: stdout)")
    p.add_argument("--report", help="Write a CSV of flagged clusters")
    args = p.parse_args(argv)

    records = load_jsonl(args.records)
    if not records:
        die("no records")

    records = flag_duplicates(records)
    payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)

    flagged = [r for r in records if r.get("dup_flag") == "yes"]
    clusters = {r.get("dup_of") for r in flagged}
    print(
        f"dedup_records: {len(records)} records; "
        f"{len(flagged)} flagged in {len(clusters)} cluster(s). "
        f"No rows dropped.",
        file=sys.stderr,
    )

    if args.report:
        cols = ["record_id", "dup_flag", "dup_of", "dup_key", "dup_cluster_size", "dup_canonical", "title", "pmid", "doi"]
        with Path(args.report).open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in records:
                w.writerow({k: r.get(k, "") for k in cols})
        print(f"dedup_records: report → {args.report}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
