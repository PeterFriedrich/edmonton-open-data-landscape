# AUDIT LEDGER — what has been audited, when, and what came back

One row per **executed audit run**. This is the coverage map the audit docs
don't give individually: briefs are reusable *instruments*, findings docs record
*one run's output*, and the `project-audit` skill deliberately picks ONE target
per session — so nothing else says what has and hasn't been looked at. This does.

Rules: add a row when an audit **executes** (not when a brief is written); every
row carries a **pointer to the findings doc**; verdicts are **point-in-time** — a
row says the target was audited *as of that date*, not that it's still clean
after later changes. Not part of any session's mandatory reading — open it to
scope an audit or to check what has already been covered. Audits are framed
top-down, fundamental decisions first.

## Executed audits

| Date | Target / scope | Instrument | Output | Verdict (one line) | Outstanding |
|------|----------------|------------|--------|--------------------|-------------|

## Queued — briefed, not yet run

- **Neighbour spot-check** (decision audit): `docs/AUDIT_spotcheck.md`, briefed 2026-11-12. Run before the remaining labels, on a model other than Opus 5.5 (suggested Fable 5.1).

## Never audited (candidates, roughly ranked)

1. **Unit of analysis: series collapse** (`src/inventory.py` `series_key`). Every count, similarity and cluster rests on the 920 units; a key that is too greedy or too timid moves all of them.
2. **Harvest completeness and snapshot reduction** (`src/harvest.py`, `src/reduce_snapshot.py`). Weekly change history can't be recreated later: paging, the asset floor, fields dropped by the reduction.
3. **Programme detection** (`src/programmes.py`, 2026-11-03). Thresholds are starting guesses; later it removes siblings from the neighbour lists.
4. **Cluster–category agreement figures** (`src/clustering.py`; ARI with and without dominant categories). Quoted in the spec.
5. **Layout drift gate** (`src/layout.py`; 2.5% median / 5% p95 thresholds).
6. **M2 metrics notebook** (claimed vs actual update frequency, licence classes).
