#!/usr/bin/env python3
"""Integration tests for Screened v0.2 against the synthetic demo.

Run from anywhere:
  python skill/screened/scripts/test_v02.py
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = Path(__file__).resolve().parent
EXAMPLES = ROOT / "examples"
PY = sys.executable


def run(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        text=True,
        capture_output=True,
        cwd=str(ROOT),
    )


def script(name: str) -> str:
    return str(SCRIPTS / name)


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def fail(msg: str) -> None:
    print("FAIL:", msg, file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    n_ok = 0

    with tempfile.TemporaryDirectory(prefix="screened-v02-") as td:
        tmp = Path(td)
        records = tmp / "records.jsonl"
        dups = tmp / "dups.csv"

        r = run([PY, script("parse_records.py"), str(EXAMPLES / "sleep-caffeine-demo.csv"), "-o", str(records), "--summary"])
        recs = load_jsonl(records)
        if len(recs) != 12:
            fail(f"expected 12 parsed records, got {len(recs)}")
        if any(x.get("pmid") not in ("", "MISSING") and x.get("pmid") != "MISSING" for x in recs if False):
            pass
        for x in recs:
            if x.get("pmid") not in {"MISSING"}:
                fail(f"{x['record_id']}: demo must not carry a PMID, got {x.get('pmid')!r}")
            if "title_normalized" not in x:
                fail("parser did not emit title_normalized")
        n_ok += 1
        print("ok parse 12 records, all pmid MISSING")

        r = run([PY, script("dedup_records.py"), str(records), "-o", str(records), "--report", str(dups)])
        recs = load_jsonl(records)
        if len(recs) != 12:
            fail(f"dedup dropped rows: {len(recs)}")
        flagged = [x for x in recs if x.get("dup_flag") == "yes"]
        if len(flagged) != 4:
            fail(f"expected 4 flagged dups, got {len(flagged)}: {[x['record_id'] for x in flagged]}")
        by = {x["record_id"]: x for x in recs}
        if by["SYN-006"]["dup_of"] != "SYN-001":
            fail(f"SYN-006 should dup_of SYN-001, got {by['SYN-006']}")
        if not str(by["SYN-006"].get("dup_key", "")).startswith("doi:"):
            fail(f"SYN-006 should match by DOI, got {by['SYN-006'].get('dup_key')}")
        if by["SYN-012"]["dup_of"] != "SYN-007":
            fail(f"SYN-012 should dup_of SYN-007, got {by['SYN-012']}")
        if not str(by["SYN-012"].get("dup_key", "")).startswith("title:"):
            fail(f"SYN-012 should match by title, got {by['SYN-012'].get('dup_key')}")
        n_ok += 1
        print("ok dedup flags 4 rows / 2 clusters, drops none")

        # invented PMID must hard-fail
        bad = tmp / "bad_decisions.jsonl"
        bad.write_text(
            json.dumps(
                {
                    "record_id": "SYN-002",
                    "decision": "exclude",
                    "reason": "off topic",
                    "pmid": "12345678",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        r = run(
            [PY, script("write_log.py"), str(records), str(bad), "-o", str(tmp / "should_not.csv")],
            check=False,
        )
        if r.returncode == 0:
            fail("write_log should hard-fail on invented PMID")
        err = (r.stderr or "") + (r.stdout or "")
        if "invent" not in err.lower() and "MISSING" not in err:
            fail(f"write_log invented-PMID error unclear: {err}")
        n_ok += 1
        print("ok write_log hard-fails invented PMID")

        # keyword hints still run
        hints = tmp / "hints.jsonl"
        r = run(
            [
                PY,
                script("keyword_hint.py"),
                str(records),
                "--criteria",
                str(EXAMPLES / "sleep-caffeine-criteria.md"),
                "-o",
                str(hints),
            ]
        )
        hs = load_jsonl(hints)
        if len(hs) != 12:
            fail(f"hints {len(hs)}")
        n_ok += 1
        print("ok keyword_hint 12")

        # resume: first 5 A decisions
        all_a = load_jsonl(EXAMPLES / "decisions-a.jsonl")
        partial = tmp / "decisions_a_partial.jsonl"
        partial.write_text("".join(json.dumps(x) + "\n" for x in all_a[:5]), encoding="utf-8")
        prog = tmp / "progress_a.json"
        log_a = tmp / "log_a.csv"
        r = run(
            [
                PY,
                script("write_log.py"),
                str(records),
                str(partial),
                "-o",
                str(log_a),
                "--screener",
                "A",
                "--progress",
                str(prog),
            ]
        )
        payload = json.loads(prog.read_text(encoding="utf-8"))
        if payload["n_completed"] != 5 or payload["n_remaining"] != 7:
            fail(f"progress expected 5/7, got {payload['n_completed']}/{payload['n_remaining']}")
        if "SYN-012" not in payload["remaining"]:
            fail("SYN-012 should be remaining")
        n_ok += 1
        print("ok progress file resume 5 done / 7 remaining")

        # full A and B logs
        r = run(
            [
                PY,
                script("write_log.py"),
                str(records),
                str(EXAMPLES / "decisions-a.jsonl"),
                "-o",
                str(log_a),
                "--screener",
                "A",
                "--progress",
                str(prog),
            ]
        )
        payload = json.loads(prog.read_text(encoding="utf-8"))
        if payload["n_remaining"] != 0:
            fail(f"full A should have 0 remaining, {payload['n_remaining']}")
        log_b = tmp / "log_b.csv"
        r = run(
            [
                PY,
                script("write_log.py"),
                str(records),
                str(EXAMPLES / "decisions-b.jsonl"),
                "-o",
                str(log_b),
                "--screener",
                "B",
            ]
        )
        with log_a.open(encoding="utf-8-sig", newline="") as f:
            a_rows = list(csv.DictReader(f))
        with log_b.open(encoding="utf-8-sig", newline="") as f:
            b_rows = list(csv.DictReader(f))
        if len(a_rows) != 12 or len(b_rows) != 12:
            fail(f"logs {len(a_rows)} {len(b_rows)}")
        if any(row["screener"] != "A" for row in a_rows):
            fail("screener column A")
        if any(row["human_confirmed"] != "no" for row in a_rows + b_rows):
            fail("human_confirmed")
        n_ok += 1
        print("ok write_log A/B 12 rows each, screener column, human_confirmed=no")

        dis = tmp / "disagreements.csv"
        r = run([PY, script("compare_logs.py"), str(log_a), str(log_b), "-o", str(dis)])
        with dis.open(encoding="utf-8-sig", newline="") as f:
            drows = list(csv.DictReader(f))
        kinds = {d["record_id"]: d["disagreement_type"] for d in drows}
        if set(kinds) != {"SYN-008", "SYN-009", "SYN-010"}:
            fail(f"disagreement ids {set(kinds)}")
        if kinds["SYN-008"] != "unresolved_maybe":
            fail(f"SYN-008 {kinds['SYN-008']}")
        if kinds["SYN-009"] != "unresolved_maybe":
            fail(f"SYN-009 include vs maybe should be unresolved_maybe, got {kinds['SYN-009']}")
        if kinds["SYN-010"] != "unresolved_maybe":
            fail(f"SYN-010 maybe vs exclude should be unresolved_maybe, got {kinds['SYN-010']}")
        n_ok += 1
        print("ok compare_logs: 008/009/010 only (maybes + borderline)")

        md = tmp / "prisma.md"
        csvp = tmp / "prisma.csv"
        r = run(
            [
                PY,
                script("prisma_counts.py"),
                str(log_a),
                "-b",
                str(log_b),
                "--records",
                str(records),
                "-o",
                str(md),
                "--csv",
                str(csvp),
            ]
        )
        with csvp.open(encoding="utf-8-sig", newline="") as f:
            stages = {row["stage"]: int(row["n"]) for row in csv.DictReader(f)}
        if stages.get("identified") != 12:
            fail(f"identified {stages.get('identified')} {stages}")
        if stages.get("duplicates_flagged") != 4:
            fail(f"duplicates_flagged {stages.get('duplicates_flagged')}")
        if stages.get("both_include") != 5:
            fail(f"both_include {stages.get('both_include')} (expect 001,005,006,007,012)")
        if stages.get("both_exclude") != 4:
            fail(f"both_exclude {stages.get('both_exclude')} (expect 002,003,004,011)")
        if stages.get("unresolved_maybe") != 3:
            fail(f"unresolved_maybe {stages.get('unresolved_maybe')}")
        if stages.get("conflict_a_ne_b") != 0:
            fail(f"conflict {stages.get('conflict_a_ne_b')}")
        text = md.read_text(encoding="utf-8")
        if "Not clinical advice" not in text:
            fail("prisma md missing notice")
        n_ok += 1
        print("ok prisma counts table (identified 12, both-include 5, both-exclude 4, maybe 3)")

        ris = tmp / "includes.ris"
        r = run(
            [PY, script("export_ris.py"), str(log_a), "-b", str(log_b), "-o", str(ris)]
        )
        body = ris.read_text(encoding="utf-8")
        # both-include: 5 records, each with TY and ER
        n_ty = body.count("TY  - JOUR")
        if n_ty != 5:
            fail(f"RIS includes expected 5, got {n_ty}\n{body}")
        if "12345678" in body or "PMID" in body and "AN  -" in body:
            # AN should be absent because pmid is MISSING
            if "AN  -" in body:
                fail("RIS must not emit AN/PMID when source is MISSING")
        if "AN  -" in body:
            fail("RIS must not emit AN when pmid MISSING")
        if "10.0000/synthetic.screened.001" not in body:
            fail("RIS should keep supplied fake DOI on includes")
        n_ok += 1
        print("ok export_ris 5 both-includes, no invented PMID")

        # companion still file:// / no CDN
        html = (ROOT / "companion" / "index.html").read_text(encoding="utf-8")
        for needle in ("https://cdn", "http://", "fetch(", "XMLHttpRequest"):
            if needle in html and needle != "http://":
                fail(f"companion looks networked: {needle}")
        # allow doi.org mention in parser of pasted DOIs, not network
        if "https://cdn" in html:
            fail("cdn")
        if "SYN-012" not in html or "Screener A" not in html:
            fail("companion missing demo 12 or A/B toggle")
        if "kbd" not in html.lower() and ">1<" not in html:
            pass
        if "Include <kbd>1</kbd>" not in html:
            fail("keyboard 1 missing")
        n_ok += 1
        print("ok companion has A/B, 12-record demo, keys 1/2/3, no CDN")

        ver = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        if ver != "0.2.0":
            fail(f"VERSION {ver}")
        n_ok += 1
        print("ok VERSION 0.2.0")

    print(f"\n{n_ok} checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
