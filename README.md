# Screened

**Title/abstract screening for systematic and scoping reviews.**  
A Cursor/Claude skill plus a one-page static worksheet. Research ops, not care.

v0.2.1 · MIT (skill files) · Polar listing live at 199 SEK.

## What it is

You already have a search export and inclusion/exclusion criteria. Screened
turns that into a **screening log**: `include` / `maybe` / `exclude` plus a
one-line reason, without inventing PMIDs or citations.

v0.2 adds what a methods-competent reviewer actually needs before paying:

- **Dual screeners** — independent logs A and B, plus a disagreement CSV
  (A≠B and unresolved maybes).
- **PRISMA 2020-style counts** — identified, screened, included, excluded,
  maybe/unresolved — as a table in the companion and as markdown/CSV. Not a
  fake flow-diagram library.
- **Dedup by DOI / PMID / normalized title** — flagged, never silently dropped.
- **Resume** — `progress_*.json` so a 200-record run can stop and continue.
- **Zotero RIS** of includes.

Two surfaces:

| Surface | For | Calls a model? |
|---|---|---|
| `skill/screened/` | People in Cursor or Claude Code | Yes — draft labels only, screener A |
| `companion/index.html` | Everyone else, offline | No — you click; keyword hints are phrase overlap |

`include` at this stage means **retrieve full text**, not “this paper is in the review”.

## Who it’s for

Researchers, students, and clinician-researchers who already run reviews
(thesis, grant, Cochrane-style, scoping). Not patients. Not a diagnostic
product. Not for treatment decisions.

If your actual job is care, do not use Screened as advice. It screens *records
against criteria you wrote*.

## What is AI vs human

- **You** supply criteria and the list of papers.
- **The parser** (Python, deterministic) normalises CSV / RIS / BibTeX / MEDLINE / paste. Missing identifiers become the string `MISSING`. Nothing is looked up unless you later ask a separate tool to do so.
- **The skill** (LLM) reads title/abstract and drafts a decision for **screener A only**. Conservative default: thin evidence → `maybe`, not `exclude`. It will not invent an independent screener B.
- **The worksheet** never drafts for you. It can *hint* from keyword overlap. You still press Include / Maybe / Exclude. Toggle A/B; the other log stays hidden while you work.
- **A human reviewer** must confirm every row (`human_confirmed=no` is written on purpose). Dual independent human screening remains best practice.

The skill will refuse to emit a PMID or DOI that was not in the source file.
`scripts/write_log.py` hard-fails if a decision tries to add one.

## What’s in the box

```
README.md                 this file
TRY.md                    offline try guide + disclosures
CHANGELOG.md              version notes
LICENSE                   MIT + note that the Polar listing is paid
NOTICE.md                 not-clinical / AI vs human / dual screening
companion/index.html      static worksheet (open as a file)
examples/                 12 synthetic “sleep and caffeine” records + dual decisions
skill/screened/           Cursor / Claude skill
  SKILL.md
  scripts/parse_records.py
  scripts/dedup_records.py
  scripts/keyword_hint.py
  scripts/write_log.py
  scripts/compare_logs.py
  scripts/prisma_counts.py
  scripts/export_ris.py
  references/protocol.md
  references/formats.md
  assets/criteria-template.md
```

## Install the skill (Cursor)

1. Copy the folder `skill/screened/` to one of:
   - project: `.cursor/skills/screened/`
   - user: `~/.cursor/skills/screened/`
2. Restart Agent chat, or type `/screened`.
3. Give it your criteria file and a CSV/RIS/BibTeX export.

Claude Code / Codex-compatible agents also load `SKILL.md` from
`.claude/skills/screened/` or `~/.claude/skills/screened/` — same copy.

Do not paste the skill into a patient-facing product. It is a reviewer aid.

### Example (synthetic demo)

From this directory, with the skill scripts:

```bash
python skill/screened/scripts/parse_records.py \
  examples/sleep-caffeine-demo.csv -o /tmp/screened/records.jsonl --summary

python skill/screened/scripts/dedup_records.py \
  /tmp/screened/records.jsonl -o /tmp/screened/records.jsonl \
  --report /tmp/screened/dups.csv

python skill/screened/scripts/keyword_hint.py \
  /tmp/screened/records.jsonl --criteria examples/sleep-caffeine-criteria.md

python skill/screened/scripts/write_log.py \
  /tmp/screened/records.jsonl examples/decisions-a.jsonl \
  -o /tmp/screened/log_a.csv --screener A --progress /tmp/screened/progress_a.json

python skill/screened/scripts/write_log.py \
  /tmp/screened/records.jsonl examples/decisions-b.jsonl \
  -o /tmp/screened/log_b.csv --screener B --progress /tmp/screened/progress_b.json

python skill/screened/scripts/compare_logs.py \
  /tmp/screened/log_a.csv /tmp/screened/log_b.csv \
  -o /tmp/screened/disagreements.csv

python skill/screened/scripts/prisma_counts.py \
  /tmp/screened/log_a.csv -b /tmp/screened/log_b.csv \
  --records /tmp/screened/records.jsonl \
  -o /tmp/screened/prisma_summary.md --csv /tmp/screened/prisma_counts.csv

python skill/screened/scripts/export_ris.py \
  /tmp/screened/log_a.csv -b /tmp/screened/log_b.csv \
  -o /tmp/screened/includes.ris
```

Then in Cursor: `/screened` → point at those files → get logs + disagreements.

Expected demo shape (bundled A/B decisions, given the bundled criteria):

| ID | A | B | Notes |
|---|---|---|---|
| SYN-001 | include | include | adults, caffeine, PSG |
| SYN-002 | exclude | exclude | interiors review |
| SYN-003 | exclude | exclude | mice |
| SYN-004 | exclude | exclude | protocol, no results |
| SYN-005 | include | include | caffeine gum, sleep diary; small n ok |
| SYN-006 | include | include | **duplicate of SYN-001** (same invented DOI) |
| SYN-007 | include | include | coffee + actigraphy |
| SYN-008 | maybe | maybe | title-only; abstract MISSING |
| SYN-009 | include | maybe | borderline adolescents / bedtime — disagreement |
| SYN-010 | maybe | exclude | matcha “restfulness” — disagreement |
| SYN-011 | exclude | exclude | in vitro slices |
| SYN-012 | include | include | **duplicate of SYN-007** (normalized title) |

All twelve are labelled `[SYNTHETIC]`. No real PMIDs. Invented DOIs use the
non-registrant prefix `10.0000/synthetic.screened.*`.

## Open the worksheet

No build step. In a browser:

```bash
# macOS
open companion/index.html

# Linux
xdg-open companion/index.html
```

Or double-click `companion/index.html`. It works as `file://` (no network).

Use **Load synthetic demo**, screen with keys `1` / `2` / `3`, toggle
**Screener A / B**, then **Counts / disagreements**. Download log A, log B,
disagreements CSV, PRISMA markdown/CSV, progress JSON (resume), and includes RIS.

Later it can sit on Cloudflare Pages as a static site. This v0 does not require
an account anywhere.

## Polar listing copy (draft — not published)

**Title:** Screened — dual-screener title/abstract logs (Cursor skill + offline worksheet)

**Price hypothesis:** $19 one-time  
(Polar Starter has $0 listing / monthly fee; they take a per-sale cut as Merchant of Record.)

**Three bullets**

1. Dual independent screening: log A, log B, and a disagreement CSV (conflicts + unresolved maybes). PRISMA-style counts table. Duplicates flagged by DOI/PMID/title, never silently dropped.
2. Cursor/Claude skill that screens a CSV, RIS, or BibTeX export against *your* criteria (AI draft = screener A only) plus an offline one-page worksheet (`1`/`2`/`3`, A/B toggle, file://).
3. Does not invent PMIDs or citations. Missing data is flagged. Resume a 200-record run. Zotero RIS of includes. A human reviewer remains responsible.

**EU AI Act Art. 50 — AI-assistance disclosure (paste into the listing)**

> This product includes an AI-assisted workflow (the Cursor/Claude skill). Screening labels produced by the skill are **AI-generated drafts** for screener A, not determinations, not medical advice, and not a systematic-review substitute. The skill will not generate an independent screener B from the same pass. Outputs must be reviewed by a human. The static worksheet does not call a model; its “keyword hints” are string overlap. If you use skill drafts in a published review, disclose that assistance in the methods. Screened is not a medical device and must not be used for diagnosis or treatment decisions. PRISMA-style output is a counts table, not a certified flow diagram.

**What Polar would deliver:** a zip of this folder (see `pack-for-polar.sh`). File download, not a SaaS seat.

## Limits of v0.2 (honest)

- Title/abstract only. No full-text stage, no RoB, no extraction, no kappa statistic (disagreement CSV is the input to that conversation).
- Dedup flags; it does not merge or delete records.
- PRISMA output is a counts table, not a generated flow drawing.
- Companion is for a handful to a few dozen records; the skill is for an export.
- Keyword hints are dumb on purpose so they cannot be mistaken for judgment.

## License

MIT for the files. A future Polar listing is a **paid packaged copy**, not extra rights and not clinical certification. See `LICENSE`.
