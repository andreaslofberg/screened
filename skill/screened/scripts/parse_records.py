#!/usr/bin/env python3
"""Normalize literature records from CSV, RIS, BibTeX, MEDLINE, JSONL, or pasted text.

Never invents PMIDs, DOIs, or citations. Missing identifiers are flagged, not guessed.
Output: JSONL on stdout (or --out). Exit 0 on success, 2 on usage error, 1 on parse failure.

Usage:
  python parse_records.py INPUT [-o records.jsonl]
  python parse_records.py --paste PASTE.txt
  python parse_records.py --stdin --format csv
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
LOCAL_PREFIX = "local-"

PMID_RE = re.compile(r"^\d{1,8}$")
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.I)

TITLE_ALIASES = {
    "title", "ti", "article title", "primary title", "item title",
    "document title", "t1",
}
ABSTRACT_ALIASES = {
    "abstract", "ab", "abstract note", "n2", "summary", "abstracts",
}
AUTHOR_ALIASES = {
    "authors", "author", "au", "first author", "a1",
}
YEAR_ALIASES = {
    "year", "publication year", "py", "yr", "date", "publication_year",
    "year published",
}
PMID_ALIASES = {
    "pmid", "pubmed id", "pubmedid", "accession number", "pubmed",
}
DOI_ALIASES = {
    "doi", "digital object identifier", "do",
}
ID_ALIASES = {
    "id", "record_id", "record id", "key", "item key", "endnote id",
    "covidence #", "rayyan id", "number", "n", "ref", "refid",
}
JOURNAL_ALIASES = {
    "journal", "journal/book", "publication title", "source", "jo", "t2",
    "journal name", "periodical",
}


def die(msg: str, code: int = 1) -> None:
    print(f"parse_records: {msg}", file=sys.stderr)
    raise SystemExit(code)


def norm_header(name: str) -> str:
    return re.sub(r"[\s_]+", " ", name.strip().lower())


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = text.strip()
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def flag_or_value(value: str) -> str:
    return value if value else MISSING


def normalize_pmid(raw: str) -> str:
    if not raw:
        return ""
    text = raw.strip()
    text = re.sub(r"(?i)^pmid[:\s]*", "", text)
    text = text.replace(",", "").strip()
    if PMID_RE.match(text):
        return text
    # PubMed sometimes stores "PMID: 12345678" inside a longer accession field
    m = re.search(r"(?i)\bpmid[:\s]*(\d{1,8})\b", raw)
    if m:
        return m.group(1)
    digits = re.sub(r"\D", "", text)
    if PMID_RE.match(digits) and "pmc" not in text.lower():
        return digits
    return ""


def normalize_doi(raw: str) -> str:
    if not raw:
        return ""
    text = raw.strip()
    text = re.sub(r"(?i)^(doi:|https?://(dx\.)?doi\.org/)", "", text).strip()
    text = text.rstrip(".")
    if DOI_RE.match(text):
        return text
    m = re.search(r"(10\.\d{4,9}/\S+)", text)
    if m:
        candidate = m.group(1).rstrip(").,;")
        if DOI_RE.match(candidate):
            return candidate
    return ""


def year_from(raw: str) -> str:
    if not raw:
        return ""
    m = re.search(r"\b(19|20)\d{2}\b", raw)
    return m.group(0) if m else ""


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse space. Used for duplicate flagging."""
    text = (title or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def missing_fields(rec: dict[str, str]) -> list[str]:
    out = []
    if not rec.get("title") or rec["title"] == MISSING:
        out.append("title")
    if not rec.get("abstract") or rec["abstract"] == MISSING:
        out.append("abstract")
    if rec.get("pmid", MISSING) == MISSING:
        out.append("pmid")
    if rec.get("doi", MISSING) == MISSING:
        out.append("doi")
    if rec.get("authors", MISSING) == MISSING:
        out.append("authors")
    if rec.get("year", MISSING) == MISSING:
        out.append("year")
    return out


def identifier_status(rec: dict[str, str]) -> str:
    has_pmid = rec.get("pmid", MISSING) != MISSING
    has_doi = rec.get("doi", MISSING) != MISSING
    if has_pmid and has_doi:
        return "as-supplied"
    if not has_pmid and not has_doi:
        return "no-identifiers"
    if not has_pmid:
        return "no-pmid"
    return "no-doi"


def finish_record(raw: dict[str, Any], source_file: str, source_format: str, index: int) -> dict[str, Any]:
    title = clean_text(raw.get("title", ""))
    abstract = clean_text(raw.get("abstract", ""))
    authors = clean_text(raw.get("authors", ""))
    journal = clean_text(raw.get("journal", ""))
    year = year_from(clean_text(raw.get("year", "")))
    pmid = normalize_pmid(clean_text(raw.get("pmid", "")))
    doi = normalize_doi(clean_text(raw.get("doi", "")))
    supplied_id = clean_text(raw.get("record_id", ""))

    # Never mint a PMID-shaped local id.
    if supplied_id and not PMID_RE.match(supplied_id):
        record_id = supplied_id
    elif pmid:
        record_id = f"pmid-{pmid}"
    elif doi:
        record_id = "doi-" + re.sub(r"[^A-Za-z0-9._-]+", "-", doi)[:80]
    else:
        record_id = f"{LOCAL_PREFIX}{index:03d}"

    rec = {
        "record_id": record_id,
        "title": flag_or_value(title),
        "title_normalized": normalize_title(title),
        "abstract": flag_or_value(abstract),
        "abstract_present": "yes" if abstract else "no",
        "authors": flag_or_value(authors),
        "year": flag_or_value(year),
        "journal": flag_or_value(journal),
        "pmid": flag_or_value(pmid),
        "doi": flag_or_value(doi),
        "source_file": source_file,
        "source_format": source_format,
        "source_index": index,
    }
    rec["missing_fields"] = ";".join(missing_fields(rec))
    rec["identifier_status"] = identifier_status(rec)
    rec["invented"] = False  # parser never invents bibliographic facts
    return rec


def map_csv_row(row: dict[str, str]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    lookup = {norm_header(k): (v or "") for k, v in row.items() if k}
    for key, aliases in (
        ("title", TITLE_ALIASES),
        ("abstract", ABSTRACT_ALIASES),
        ("authors", AUTHOR_ALIASES),
        ("year", YEAR_ALIASES),
        ("pmid", PMID_ALIASES),
        ("doi", DOI_ALIASES),
        ("record_id", ID_ALIASES),
        ("journal", JOURNAL_ALIASES),
    ):
        for alias in aliases:
            if alias in lookup and lookup[alias].strip():
                mapped[key] = lookup[alias]
                break
    # PubMed "Citation" is not an abstract; ignore unless abstract missing and field looks long
    return mapped


def parse_csv(text: str, source_file: str) -> list[dict[str, Any]]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    if not reader.fieldnames:
        die("CSV has no header row")
    records = []
    for i, row in enumerate(reader, start=1):
        if not any((v or "").strip() for v in row.values()):
            continue
        records.append(finish_record(map_csv_row(row), source_file, "csv", i))
    return records


RIS_TAGS = re.compile(r"^([A-Z0-9]{2})\s*-\s?(.*)$")


def parse_ris_or_medline(text: str, source_file: str) -> list[dict[str, Any]]:
    # RIS uses "TY  - "; MEDLINE/PubMed uses "PMID- " / "TI  - "
    records_raw: list[dict[str, list[str]]] = []
    current: dict[str, list[str]] = {}
    last_tag = None
    fmt = "ris" if re.search(r"(?m)^TY\s+-", text) else "medline"

    for line in text.splitlines():
        if not line.strip():
            continue
        m = RIS_TAGS.match(line)
        if not m and re.match(r"^[A-Z]{2,4}-\s", line):
            tag, val = line.split("-", 1)
            m_tag, m_val = tag.strip()[:4], val.strip()
        elif m:
            m_tag, m_val = m.group(1), m.group(2)
        else:
            if last_tag and current:
                current[last_tag][-1] = current[last_tag][-1] + " " + line.strip()
            continue
        if m_tag in {"TY", "PMID"} and current and last_tag:
            records_raw.append(current)
            current = {}
        current.setdefault(m_tag, []).append(m_val.strip())
        last_tag = m_tag
        if m_tag == "ER":
            records_raw.append(current)
            current = {}
            last_tag = None
    if current:
        records_raw.append(current)

    out = []
    for i, raw in enumerate(records_raw, start=1):
        def first(*tags: str) -> str:
            for t in tags:
                if t in raw and raw[t]:
                    return " ".join(raw[t])
            return ""

        pmid = first("PMID") or ""
        if not pmid:
            for candidate in raw.get("AN", []) + raw.get("ID", []) + raw.get("M1", []):
                p = normalize_pmid(candidate)
                if p:
                    pmid = p
                    break
        rec = {
            "title": first("TI", "T1", "T2"),
            "abstract": first("AB", "N2", "N1"),
            "authors": "; ".join(raw.get("AU", []) or raw.get("A1", []) or raw.get("FAU", [])),
            "year": first("PY", "Y1", "DP", "YR"),
            "journal": first("JO", "T2", "JF", "JA", "JT"),
            "pmid": pmid,
            "doi": first("DO", "DOI", "M3"),
            "record_id": first("ID", "UR") if first("ID", "UR") and not PMID_RE.match(first("ID", "UR") or "") else "",
        }
        out.append(finish_record(rec, source_file, fmt, i))
    return out


BIB_ENTRY = re.compile(
    r"@(\w+)\s*\{\s*([^,]+)\s*,(.*?)\n\s*\}",
    re.S | re.I,
)
BIB_FIELD = re.compile(
    r"(\w+)\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\}|\"[^\"]*\"|[^,\n]+)\s*,?",
    re.S,
)


def unquote_bib(val: str) -> str:
    val = val.strip().rstrip(",").strip()
    if val.startswith("{") and val.endswith("}"):
        val = val[1:-1]
    elif val.startswith('"') and val.endswith('"'):
        val = val[1:-1]
    val = val.replace("\n", " ")
    val = re.sub(r"\s+", " ", val)
    val = re.sub(r"\{([^{}]*)\}", r"\1", val)
    return val.strip()


def parse_bibtex(text: str, source_file: str) -> list[dict[str, Any]]:
    out = []
    for i, m in enumerate(BIB_ENTRY.finditer(text), start=1):
        key = m.group(2).strip()
        body = m.group(3)
        fields: dict[str, str] = {}
        for fm in BIB_FIELD.finditer(body):
            fields[fm.group(1).lower()] = unquote_bib(fm.group(2))
        rec = {
            "title": fields.get("title", ""),
            "abstract": fields.get("abstract", "") or fields.get("annote", ""),
            "authors": fields.get("author", "").replace(" and ", "; "),
            "year": fields.get("year", ""),
            "journal": fields.get("journal", "") or fields.get("booktitle", ""),
            "pmid": fields.get("pmid", "") or fields.get("eprint", ""),
            "doi": fields.get("doi", ""),
            "record_id": key,
        }
        out.append(finish_record(rec, source_file, "bibtex", i))
    return out


def parse_jsonl(text: str, source_file: str) -> list[dict[str, Any]]:
    out = []
    for i, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            die(f"JSONL line {i}: {e}")
        if not isinstance(obj, dict):
            die(f"JSONL line {i}: expected object")
        out.append(finish_record(obj, source_file, "jsonl", i))
    return out


def parse_paste(text: str, source_file: str) -> list[dict[str, Any]]:
    """Pasted title/abstract pairs.

    Accepted shapes, records split on a --- line, or on blank lines when labelled:
      Title: ...
      Abstract: ...
    """
    text = text.strip()
    if not text:
        die("no pasted records found")

    if re.search(r"(?m)^---+\s*$", text):
        chunks = re.split(r"(?m)^---+\s*$", text)
    else:
        labelled = re.split(r"\n[ \t]*\n", text)
        labelled = [c.strip() for c in labelled if c.strip()]
        if len(labelled) > 1 and all(
            re.search(r"(?i)^(title|id)\s*[:=]", c) for c in labelled
        ):
            chunks = labelled
        else:
            chunks = re.split(r"\n\s*\n\s*\n", text)
    chunks = [c.strip() for c in chunks if c.strip()]
    if not chunks:
        die("no pasted records found")

    out = []
    for i, chunk in enumerate(chunks, start=1):
        labelled_fields: dict[str, str] = {}
        for line in chunk.splitlines():
            lm = re.match(
                r"(?i)^(title|abstract|authors?|year|pmid|doi|id|journal)\s*[:=]\s*(.*)$",
                line,
            )
            if lm:
                key = lm.group(1).lower()
                if key == "author":
                    key = "authors"
                labelled_fields[key] = lm.group(2).strip()
        title = labelled_fields.get("title", "")
        abstract = labelled_fields.get("abstract", "")
        if "abstract" in labelled_fields:
            am = re.search(r"(?im)^abstract\s*[:=]\s*(.*)$", chunk)
            if am:
                abstract = re.sub(
                    r"(?i)^abstract\s*[:=]\s*", "", chunk[am.start():], count=1
                ).strip()
        if not title and not abstract:
            lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
            if not lines:
                continue
            title = lines[0]
            abstract = " ".join(lines[1:]) if len(lines) > 1 else ""
        rec = {
            "title": title,
            "abstract": abstract,
            "authors": labelled_fields.get("authors", ""),
            "year": labelled_fields.get("year", ""),
            "pmid": labelled_fields.get("pmid", ""),
            "doi": labelled_fields.get("doi", ""),
            "journal": labelled_fields.get("journal", ""),
            "record_id": labelled_fields.get("id", ""),
        }
        out.append(finish_record(rec, source_file, "paste", i))
    return out


def detect_format(text: str, hint: str | None, path: str | None) -> str:
    if hint:
        return hint.lower()
    if path:
        suffix = Path(path).suffix.lower()
        mapping = {
            ".csv": "csv",
            ".tsv": "csv",
            ".ris": "ris",
            ".bib": "bibtex",
            ".bibtex": "bibtex",
            ".nbib": "medline",
            ".txt": None,
            ".jsonl": "jsonl",
            ".json": "jsonl",
        }
        if suffix in mapping and mapping[suffix]:
            return mapping[suffix]
    head = text.lstrip()[:800]
    if head.startswith("{") or head.startswith("{"):
        return "jsonl"
    if re.match(r"(?i)^@\w+\s*\{", head):
        return "bibtex"
    if re.search(r"(?m)^TY\s+-", text[:2000]):
        return "ris"
    if re.search(r"(?m)^PMID-", text[:2000]):
        return "medline"
    if re.search(r"(?i)^(title|abstract)\s*[:=]", head):
        return "paste"
    # CSV if first line has a comma and a known header
    first = text.splitlines()[0] if text.splitlines() else ""
    if "," in first and re.search(r"(?i)title|abstract|pmid", first):
        return "csv"
    return "paste"


def parse_text(text: str, source_file: str, fmt: str) -> list[dict[str, Any]]:
    if not text.strip():
        die("empty input")
    if fmt == "csv":
        return parse_csv(text, source_file)
    if fmt in {"ris", "medline"}:
        recs = parse_ris_or_medline(text, source_file)
        if not recs:
            die(f"no {fmt} records found")
        return recs
    if fmt == "bibtex":
        recs = parse_bibtex(text, source_file)
        if not recs:
            die("no BibTeX records found")
        return recs
    if fmt == "jsonl":
        return parse_jsonl(text, source_file)
    if fmt == "paste":
        return parse_paste(text, source_file)
    die(f"unknown format: {fmt}", 2)
    return []


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Normalize screening records. Never invents identifiers.")
    p.add_argument("input", nargs="?", help="Input file (CSV/RIS/BibTeX/MEDLINE/JSONL/txt)")
    p.add_argument("--paste", help="Pasted title/abstract file")
    p.add_argument("--stdin", action="store_true", help="Read from stdin")
    p.add_argument("--format", dest="fmt", help="Force format: csv, ris, medline, bibtex, jsonl, paste")
    p.add_argument("-o", "--out", help="Write JSONL here (default: stdout)")
    p.add_argument("--summary", action="store_true", help="Print counts to stderr")
    args = p.parse_args(argv)

    if args.paste:
        path = args.paste
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        source = path
        fmt = detect_format(text, args.fmt or "paste", path)
    elif args.stdin or args.input == "-":
        text = sys.stdin.read()
        source = "<stdin>"
        fmt = detect_format(text, args.fmt, None)
    elif args.input:
        path = args.input
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        source = path
        fmt = detect_format(text, args.fmt, path)
    else:
        p.print_help()
        return 2

    records = parse_text(text, source, fmt)
    if not records:
        die("parsed zero records")

    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    payload = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)

    if args.summary or args.out:
        n = len(records)
        n_abs = sum(1 for r in records if r["abstract_present"] == "yes")
        n_pmid = sum(1 for r in records if r["pmid"] != MISSING)
        n_title = sum(1 for r in records if r["title"] != MISSING)
        print(
            f"parse_records: {n} records ({fmt}); "
            f"{n_title} with title; {n_abs} with abstract; {n_pmid} with PMID. "
            f"No identifiers were invented.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
