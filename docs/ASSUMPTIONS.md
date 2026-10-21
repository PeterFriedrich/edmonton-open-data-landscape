# Assumptions index

One row per premise a published number rests on that no guard proves. Use it to
come back to an assumption, and read it before scoping an audit. **This is an
index, not an argument:** each row points at the place that holds the evidence,
and the reasoning stays there. A row copies no figures, so it can't drift from
its source. Only a rough size is kept here, for ranking.

How this differs from the other docs:
- `docs/DECISIONS.md` records *choices*. An `[unverifiable]` decision row is
  not a premise; add one here only if a published number rests on it.
- `docs/DATA_ISSUES.md` records *defects* in other people's data. One belongs
  here only once a number rests on working around it.
- `docs/AUDIT_LEDGER.md` records *what has been checked*.
- This index records *what we take as true without having proven it*.

Rules:
- **Add a row when a number starts depending on something unproven.** That
  includes a "looks like" or "probably" inference written in `data/DATA.md`.
- **Point at the machine-readable source when there is one** (a data file's
  field, a notebook row), not at prose that describes it. Prose about a field
  goes stale while the field moves.
- **Update a row in place when its status changes; never reuse an ID.** A row a
  test now proves becomes `VERIFIED`, naming the test. A premise found wrong
  gets a test before it gets a new status.
- **Keep the pointer live.** When the evidence moves, move the pointer.
- **Add a completeness test once the project keeps a register of its own** (a
  verified notebook's sized rows, a `confidence` field in a data file): it fails
  when a register entry has no row here. The template can't write it, because
  every project's registers differ.

Status values:
- `VERIFIED`: a guard proves it; the row names the test.
- `SUPPORTED`: the evidence agrees, but doesn't cover every year or member the
  row applies to.
- `UNVERIFIED`: taken on trust.
- `ACCEPTED`: known to be off by a measured amount, and used anyway by decision.

`scripts/check_assumptions.py` fails on an unknown status, a VERIFIED row with
no existing test, a row other than VERIFIED with no size, a row with no evidence,
or a repeated ID. `scripts/check_doc_citations.py` checks the `.md` pointers.
Extra columns (`Build`, `Lens`) and several tables are fine: columns are found
by header name, and any table with a `Status` column is part of the index.

| ID | Assumption | Status | If wrong (rough size) | Evidence and test |
|----|------------|--------|-----------------------|-------------------|
