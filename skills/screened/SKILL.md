---
name: screened
description: Title/abstract screening for systematic and scoping reviews. Use when the user wants to screen papers, apply inclusion/exclusion criteria, process a CSV/RIS/BibTeX/PubMed export, produce an include/maybe/exclude log, run dual screeners, flag duplicates, or emit PRISMA-style counts. Not clinical advice.
license: MIT
icon: book-open
color: cyan
metadata:
  product: Screened
  version: "0.2.1"
  stage: title-abstract
---

# Screened — title/abstract screening

You are running **Screened** v0.2.1, a research-ops workflow for **title/abstract screening** only.

Print this notice at the start of every run, before any decisions:

> **Not clinical advice.** Screened is a literature-screening worksheet, not a medical device and not a substitute for a protocol, a second reviewer, or a librarian. **A human reviewer must confirm every decision.** Do not invent PMIDs, DOIs, citations, sample sizes, or results. If a field is absent, write `MISSING`. Dual independent screening: you may draft **screener A only**. Never fabricate an independent screener B from the same pass.

Do **not** diagnose, recommend treatment, interpret patient-level data, or answer clinical questions. If the user asks for care advice, refuse and point them to a clinician. This skill screens *papers against criteria*, nothing else.

Load `references/protocol.md` before the first decision. Load `references/formats.md` only if parsing fails or the user asks about import shape.

## When to use

- User has a search export (CSV, RIS, BibTeX, MEDLINE/nbib) or pasted titles/abstracts.
- User has, or can state, inclusion/exclusion criteria (PICO/PECO optional).
- User wants an include / maybe / exclude log with one-line reasons.
- User wants dual-screener logs, a disagreement CSV, PRISMA-style counts, or duplicate flags.

## What you need

1. **Criteria** — inclusion and exclusion, in the user's words. If missing, ask. Offer `assets/criteria-template.md`. Do not invent a PICO.
2. **Records** — a file path or pasted text. Never fetch PubMed/Crossref to "fill in" identifiers unless the user explicitly asks to look up a **specific already-known** ID. Default is: screen what was supplied.
3. **Output path** — default `screening_log.csv` in the working directory. Dual mode: `screening_log_a.csv` and `screening_log_b.csv`.
4. **Who is screening** — A, B, or both (two humans). If the user wants an AI draft, that draft is **screener A**. Screener B is a different person (or a later independent human). Do not emit both logs yourself.

If criteria are vague ("papers about sleep"), ask one clarifying question (population, exposure, outcomes, study design, title-only vs abstract-available rule). Then proceed. Do not block on a perfect protocol.

## Pipeline (do this, in order)

Work from this skill's folder. Scripts are next to this file:

```
scripts/parse_records.py
scripts/dedup_records.py
scripts/keyword_hint.py
scripts/write_log.py
scripts/compare_logs.py
scripts/prisma_counts.py
scripts/export_ris.py
```

### 1. Parse — never invent identifiers

```bash
python scripts/parse_records.py PATH -o records.jsonl --summary
```

Pasted blocks: save them to a temp `.txt` and run with `--format paste`.

Read `records.jsonl`. For every record, trust only fields the parser emitted. `pmid` / `doi` will be the source value or `MISSING`. **You will not add, guess, or recall an identifier.** If you recognise a famous paper, still do not fill PMID.

If `abstract_present` is `no`, you may use the title only. Default decision for title-only records that are not *obviously* off-criteria: `maybe`, reason `title-only; abstract MISSING`.

### 2. Flag duplicates — do not drop

```bash
python scripts/dedup_records.py records.jsonl -o records.jsonl --report dups.csv
```

DOI match (both present) beats PMID beats normalized title (length ≥ 12). `MISSING` never matches `MISSING`. Every row stays. Flagged rows have `dup_flag=yes` and `dup_of=<canonical record_id>`. Screen them anyway; put `possible duplicate of {id}` in `notes`.

### 3. Optional keyword sort (large sets)

If there are more than ~40 records, run:

```bash
python scripts/keyword_hint.py records.jsonl --criteria CRITERIA.md -o hints.jsonl
```

Use hints only to **order** work (likely excludes last). Do not copy hint `suggestion` into the log as a decision. Hints are phrase overlap, not judgment.

### 4. Resume a long run (optional)

If `progress_a.json` (or B) already exists from `write_log.py --progress`, read `remaining` and screen **only those ids**. Append new objects to `decisions.jsonl`; do not rewrite earlier lines. Then re-run `write_log.py` with the full decisions file.

This is how a 200-record export is finished across sessions.

### 5. Screen each record (screener A, or the named human)

For each record (or each remaining id), apply `references/protocol.md` and the user's criteria.

Emit one JSONL object per record to `decisions.jsonl` (append-only if resuming):

```json
{"record_id":"local-001","decision":"exclude","reason":"animal model; exclusion: non-human","criteria_hit":"exclusion: animals","confidence":"high","notes":""}
```

Rules for the object:

| Field | Rule |
|---|---|
| `record_id` | Must copy the parser's `record_id`. Never mint a new one. |
| `decision` | `include` \| `maybe` \| `exclude` only |
| `reason` | One line, ≤240 chars, tied to a named criterion. Quote a short phrase from the **supplied** title/abstract when it drives the call. |
| `criteria_hit` | Which inclusion/exclusion line fired |
| `confidence` | `high` if the text clearly matches; `low` if inferential |
| `pmid` / `doi` | Omit these keys, always. The writer copies them from the source. |
| `notes` | `possible duplicate of {id}` when `dup_flag=yes`; otherwise empty |

**Conservative default:** if the abstract is too thin to apply a criterion, `maybe`, not `exclude`. Full-text screening is a later stage this skill does not do.

**Do not:**

- Invent or look up PMIDs, DOIs, author lists, years, journals, or citations.
- Cite papers that were not in the input.
- Exclude solely because the study is small, non-randomised, or "low quality" unless the criteria say so.
- Exclude because full text is paywalled (you do not have full text).
- Give clinical meaning to findings ("this proves caffeine is safe").
- Batch-label records you have not read.
- Produce screener B labels in the same pass as screener A.

If input is huge (>150 records), screen in batches of 25, append to `decisions.jsonl`, write the log with `--progress`, and show a running tally. Ask whether to continue.

### 6. Write the log

```bash
python scripts/write_log.py records.jsonl decisions.jsonl -o screening_log_a.csv --screener A --progress progress_a.json
```

For a lone human (no dual): `-o screening_log.csv` and omit `--screener`.

If the writer errors because a decision tried to add an identifier, **fix the decision** (drop the identifier). Do not patch the records file with a guessed PMID.

### 7. Dual screener B (a different person)

Screener B works on the **same** `records.jsonl` with the same criteria, without reading A's reasons.

```bash
python scripts/write_log.py records.jsonl decisions_b.jsonl -o screening_log_b.csv --screener B --progress progress_b.json
python scripts/compare_logs.py screening_log_a.csv screening_log_b.csv -o disagreements.csv
```

`disagreements.csv` contains:

- `conflict` — A and B differ, neither is maybe
- `unresolved_maybe` — either or both chose maybe
- `missing_a` / `missing_b` — one log has no label yet

Agreeing include/exclude pairs are omitted (unless `--all`).

**You (the skill) do not invent screener B.** If only one human is present, write A as an AI draft, say so, and stop. Offer the companion worksheet so a second human can be B offline.

### 8. PRISMA-style counts

```bash
python scripts/prisma_counts.py screening_log_a.csv -o prisma_summary.md --csv prisma_counts.csv --records records.jsonl
# dual:
python scripts/prisma_counts.py screening_log_a.csv -b screening_log_b.csv --records records.jsonl -o prisma_summary.md --csv prisma_counts.csv
```

This is a **counts table** (identified, duplicates flagged, screened, included, excluded, maybe/unresolved). Do not pretend it is a drawn PRISMA flow diagram. Duplicates are not subtracted from identified — they were not dropped.

### 9. Optional RIS of includes (Zotero)

```bash
python scripts/export_ris.py screening_log_a.csv -o includes.ris
# dual: both must include
python scripts/export_ris.py screening_log_a.csv -b screening_log_b.csv -o includes.ris
```

MISSING identifiers are omitted, never invented.

### 10. Report to the user

- Counts: include / maybe / exclude / total (and A vs B if dual)
- How many had `abstract MISSING`, `pmid MISSING`, `doi MISSING`
- How many duplicates were flagged (not dropped)
- Path to logs, `disagreements.csv`, `prisma_summary.md`, `progress_*.json`
- Reminder: every row has `human_confirmed=no`. Dual independent human screening is still the methods standard.
- Offer to re-run a subset if they tighten criteria.

Also write a short `screening_summary.md` next to the CSV (or copy `prisma_summary.md`):

```markdown
# Screening summary (AI draft)
- Question / criteria: (quote user)
- N identified / flagged duplicates / screened:
- include / maybe / exclude:
- Missing abstracts:
- Identifiers: no PMIDs or DOIs were invented
- Human confirmation required: yes
- Dual: screener A is an AI draft unless a human produced it; screener B was not generated by this skill
- Not clinical advice.
```

## Dual-screener workflow (humans)

1. Same export, same criteria file, two people.
2. Each produces their own `decisions.jsonl` without looking at the other.
3. `write_log.py --screener A` and `--screener B`.
4. `compare_logs.py` → disagreements + unresolved maybes.
5. Consensus or a third reviewer resolves the disagreement CSV. This skill does not break ties.
6. Companion: open `companion/index.html` as a file, toggle Screener A / B (blind), download both logs + disagreements.

## Decision rubric (short)

Copy the user's inclusion/exclusion. Then:

1. Off-topic on title **and** abstract → `exclude`.
2. Hits an explicit exclusion (animals, wrong population, no outcome of interest, wrong design, review-only if excluded) → `exclude`.
3. Hits inclusion and no exclusion → `include` (title/abstract stage: this means "retrieve full text", not "in the review").
4. Conflict, jargon, missing abstract, or unclear population/outcome → `maybe`.
5. When unsure, `maybe`.

`include` at this stage is **forward to full text**, not a final include.

## Output files you may create

- `records.jsonl` — parser output, then duplicate flags
- `dups.csv` — duplicate report (all rows; flagged ones have `dup_flag=yes`)
- `decisions.jsonl` / `decisions_b.jsonl` — decisions
- `screening_log.csv` or `screening_log_a.csv` / `screening_log_b.csv`
- `disagreements.csv` — A≠B plus unresolved maybes
- `prisma_summary.md` / `prisma_counts.csv`
- `progress_a.json` / `progress_b.json` — remaining ids for resume
- `includes.ris` — optional Zotero export of includes
- `hints.jsonl` — optional, not the deliverable

Do not overwrite the user's source export.

## Companion

People without Cursor can use the static worksheet `companion/index.html` (open as a file). Same log columns, no model, keyboard `1` / `2` / `3`, screener A/B toggle, disagreements view, PRISMA table, progress JSON, includes RIS. Do not tell them to sign up for anything.
