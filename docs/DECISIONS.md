# Decisions Index

Append-only. **One ROW per locked decision** — when, what, why (including what
was rejected), and a pointer to where the argument lives in full. When a decision
locks, add a row; when one is superseded, strike it (`~~...~~`) or mark it
`SUPERSEDED <date>` in place and add the successor — don't delete history.

**What a row owes you:**

1. ⚠️ **EVERY ROW CARRIES A POINTER TO A DOC** — not only to code. Code moves;
   the argument has to live somewhere prose can hold it.
   `scripts/check_doc_citations.py` checks that every pointer resolves.
2. **The row is a self-contained summary** and may paraphrase the argument.
3. **The pointer is the authority.** When a row and its target disagree, the
   target wins and the row gets fixed.
4. **A row names the test that protects it**, or carries `[unverifiable]`.
   `scripts/check_decisions_log.py` enforces this on the merge gate (and that a
   superseded row is marked where it stands).

| When | Decision | Full reasoning |
|------|----------|----------------|
| 2026-10-01 | **Full raw snapshots go in a private repo; this public repo holds only reduced snapshots** (no `cachedContents.top`/`smallest`/`largest`) and derived outputs. Rejected: committing full raw snapshots here (column summaries can carry personal information, which the licence excludes), and keeping them only on the server (no off-server copy). Owner decision. [unverifiable] until the harvest PR adds its reduced-snapshot guard test. | `docs/SPEC_landscape.md` §Data sources, Review log 2026-10-01 |
