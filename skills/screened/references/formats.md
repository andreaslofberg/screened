# Input formats

`scripts/parse_records.py` detects format from extension or content.

| Format | Extensions | Notes |
|---|---|---|
| CSV / TSV | `.csv`, `.tsv` | Header row required. Delimiter sniffed. |
| RIS | `.ris` | Zotero / EndNote / many databases |
| BibTeX | `.bib` | `@article` and similar; `abstract` field used when present |
| MEDLINE / PubMed | `.nbib`, tagged text starting `PMID-` | |
| JSONL | `.jsonl` | Objects with title/abstract/… |
| Paste | `.txt` or stdin | `Title:` / `Abstract:` blocks, or title line + abstract paragraph, records split on `---` or blank lines |

## CSV column aliases

The parser is case-insensitive and maps common export names:

- title ← Title, TI, Article Title, Item Title
- abstract ← Abstract, Abstract Note, AB, Summary
- authors ← Authors, Author, AU, First Author
- year ← Year, Publication Year, PY
- pmid ← PMID, PubMed ID, Accession Number
- doi ← DOI
- record_id ← ID, Key, Item Key, Covidence #, Rayyan ID
- journal ← Journal, Journal/Book, Publication Title, Source

Unknown columns are ignored. No column is invented.

## What the parser will not do

- Look up a DOI from a title
- Complete a truncated author list
- Assign a PMID because the paper "looks familiar"
- Treat PubMed Central IDs (PMC…) as PMIDs
- Silently drop rows with missing abstracts — they are emitted with `abstract_present=no`

## Paste shape (recommended)

```
ID: SYN-001
Title: Example synthetic title
Abstract: Example abstract paragraph.

---

Title: Second record
Abstract: Second abstract.
```

## Output of the parser

JSONL, one object per record. Identifiers are the source value or the string `MISSING`. Local ids look like `local-001`, never like `12345678`.

## Duplicate flagging

`scripts/dedup_records.py` reads the parser JSONL and adds `dup_flag`, `dup_of`, `dup_key`, `dup_cluster_size`, `dup_canonical`. Matching order: DOI (both present), PMID (both present), then `title_normalized` (length ≥ 12). `MISSING` never matches `MISSING`. Rows are never dropped.

## Dual logs

`write_log.py --screener A|B` writes independent CSVs. `compare_logs.py` emits disagreements (A≠B) plus unresolved maybes. `prisma_counts.py` writes the counts table (markdown + optional CSV). `export_ris.py` writes Zotero-readable RIS of includes.
