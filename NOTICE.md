# Notice

Screened is a **research-ops** tool for title/abstract screening in systematic
and scoping reviews.

It is **not**:

- clinical advice, a medical device, or a diagnostic/treatment product
- a substitute for a review protocol, a second human reviewer, or a librarian
- a citation database (it will not invent PMIDs, DOIs, or references)

AI vs human:

- The **Cursor/Claude skill** produces **AI-assisted draft** labels. Every row
  is written `human_confirmed=no`. A human must review decisions.
- The **static companion** (`companion/index.html`) does not call a model.
  Keyword hints are phrase overlap only.

If you use the skill in a review that you publish, disclose AI assistance in
the methods (ordinary reporting honesty, and EU AI Act Art. 50 transparency
for AI-generated/assisted content).

Synthetic examples in `examples/` are labelled `[SYNTHETIC]` and are not real
patient or trial data.

Dual screening and PRISMA counts:

- Screener A and screener B logs are independent. A model draft may stand in for A only.
- Disagreement CSVs list A≠B plus unresolved maybes. Humans resolve them.
- PRISMA 2020-style output is a counts table (identified, screened, included, excluded, maybe/unresolved). It is not a certified flow diagram and does not drop duplicates — it flags them.
