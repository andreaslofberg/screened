# Title/abstract screening protocol (Screened v0.2)

This is the title/abstract (TI/AB) stage of a systematic or scoping review. It is **not** full-text screening, data extraction, risk of bias, GRADE, or clinical interpretation.

## Role of the agent

- Apply the **user's** inclusion/exclusion criteria to **supplied** records.
- Produce a draft log for a human reviewer.
- Flag missing fields instead of filling them.

You are not a second author, a clinician, or a citation manager.

## Stage rules

1. **Forward, don't finalise.** `include` means "retrieve full text". Final inclusion happens later, on full text, by humans.
2. **Conservative excludes.** If a criterion cannot be judged from title/abstract, choose `maybe`. Do not exclude on missing methods detail, unstated sample size, or absent statistics.
3. **Title-only.** If `abstract_present=no` and the title is not a clear mismatch, `maybe` with reason `title-only; abstract MISSING`.
4. **One reason.** Map the decision to a single named criterion. Quote a short phrase that actually appears in the supplied title or abstract.
5. **Identifiers.** Copy `pmid` / `doi` from the parser or leave `MISSING`. Never recall a PMID from training data. Never format a local id as a PMID.
6. **No quality veto.** Small n, non-RCT, "weak study", preprint status, or paywall are not exclusion reasons unless the criteria say so.
7. **Reviews and protocols.** Exclude narrative reviews, systematic reviews, editorials, and protocols **only if** the criteria exclude them. Otherwise `maybe` or `include` as written.
8. **Animals / in vitro.** Exclude when the criteria are human-only **and** the record is clearly non-human. If species is unstated, `maybe`.
9. **Language.** Do not exclude for language unless the title is clearly in an excluded language **and** the criteria exclude it. Unstated language → do not infer.
10. **Duplicates.** Run `scripts/dedup_records.py` after parsing. Matches are by DOI, then PMID, then normalized title. Rows are *flagged* (`dup_flag=yes`, `dup_of=canonical id`) and **kept**. Screen both; note `possible duplicate of {record_id}` in `notes`. Never silently drop.
11. **Clinical content.** Papers may be about patients. You still only screen *eligibility*, not care. No dosing, diagnosis, or "should this patient…".
12. **Honesty about uncertainty.** `confidence: low` when you are inferring. Prefer `maybe` over a confident wrong exclude.

## Reason style

Good: `exclude: animal EEG (mice); exclusion = non-human`.
Good: `maybe: sleep mentioned, caffeine exposure unclear`.
Good: `include: adults + caffeine gum + sleep diary; no exclusion hit`.
Bad: `doesn't look relevant`.
Bad: `PMID 12345678 shows…` (do not add identifiers).
Bad: `known landmark trial by Smith 2011` (do not import extra citation knowledge).

## After the log

Remind the user:

- Dual independent human screening is still best practice. The skill may draft **screener A only**. Never invent an independent screener B from the same model pass.
- Disagreements (`compare_logs.py`) are resolved by a third reviewer or consensus, not by this skill.
- PRISMA-style counts (`prisma_counts.py`) are a table of identified / screened / included / excluded / maybe. Not a certified flow diagram.
- Report AI assistance in the review's methods if they use these drafts (EU AI Act Art. 50 transparency; also ordinary methods honesty).
