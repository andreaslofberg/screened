# Try Screened (offline)

Research ops, not care. Not a medical device. AI drafts are **screener A only**.

## 1. Open the companion offline

No build, no network, no account.

```bash
# from this folder
# macOS
open companion/index.html

# Linux
xdg-open companion/index.html
```

Or double-click `companion/index.html`. It must work as `file://`.

**First time?** On the setup screen, click **Load synthetic demo**, then **Start screening**. Keys `1` / `2` / `3` = Include / Maybe / Exclude. Toggle Screener A / B. Open **Counts / disagreements** when done.

Demo records are labelled `[SYNTHETIC]` (fake sleep/caffeine papers). No real PMIDs.

## 2. Install the `/screened` skill (Cursor)

Copy the folder `skill/screened/` to one of:

- project: `.cursor/skills/screened/`
- user: `~/.cursor/skills/screened/`

Restart Agent chat, or type `/screened`.

Claude Code / Codex-compatible agents: same folder under `.claude/skills/screened/` or `~/.claude/skills/screened/`.

Give the skill your criteria file and a CSV / RIS / BibTeX / MEDLINE export. It drafts labels for **screener A only**. It will not invent an independent screener B. It will not invent PMIDs or DOIs.

## 3. Buy the packaged zip (optional)

Polar checkout (one-time, not a seat):

https://buy.polar.sh/polar_cl_bGBPHTpDvx1yZyV4B1U4RpaENrdNPAuSOA4wN0n0xZ0

You get the same folder as a download. MIT skill files stay MIT; Polar is Merchant of Record for the paid package.

## 4. Source / public repo

https://github.com/andreaslofberg/screened

## Disclosures (read once)

| Claim | Truth |
|---|---|
| What it is | Title/abstract screening worksheet + Cursor/Claude skill for systematic / scoping reviews |
| What it is not | Clinical advice, diagnosis, treatment, or a medical device |
| AI | Skill drafts are AI-assisted labels for **screener A only**, written `human_confirmed=no`. A human must confirm every row. Companion does not call a model (keyword hints = phrase overlap). |
| Dual screening | Log A and log B are independent. Disagreement CSV lists A≠B and unresolved maybes. Humans resolve them. |
| PRISMA | Counts table (identified / screened / included / excluded / maybe). Not a certified flow diagram. |
| Citations | Missing PMIDs/DOIs stay missing. Nothing is invented. Duplicates are flagged, never silently dropped. |
| Audience | Researchers / students / clinician-researchers running reviews — not patients, not care workflows |

If you publish a review that used skill drafts, disclose AI assistance in the methods (ordinary honesty; EU AI Act Art. 50 for AI-generated/assisted content).

See also `NOTICE.md` and `README.md`.
