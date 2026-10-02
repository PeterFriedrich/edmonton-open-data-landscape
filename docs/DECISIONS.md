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
| 2026-10-01 | SUPERSEDED 2026-10-02 by the next row (descriptions also kept private). **Full raw snapshots go in a private repo; this public repo holds only reduced snapshots** (no `cachedContents.top`/`smallest`/`largest`) and derived outputs. Rejected: committing full raw snapshots here (column summaries can carry personal information, which the licence excludes), and keeping them only on the server (no off-server copy). Owner decision. [unverifiable] until the harvest PR adds its reduced-snapshot guard test. | `docs/SPEC_landscape.md` §Data sources, Review log 2026-10-01 |
| 2026-10-02 | AMENDED 2026-10-02 by the next row (guard test now exists). **Full raw snapshots go in a private repo; this public repo holds only reduced snapshots**: no `cachedContents.top`/`smallest`/`largest` **and no dataset or column descriptions**, plus derived outputs. Rule: anything whose licence status is uncertain stays private. Rejected: committing full raw snapshots here (column summaries can carry personal information, which the licence excludes; coverage of the catalogue's own prose is unclear); keeping them only on the server (no off-server copy). Owner decision. [unverifiable] until the harvest PR adds its reduced-snapshot guard test. | `docs/SPEC_landscape.md` §Data sources |
| 2026-10-02 | **Public reduced snapshots are built from an allow-list** (`src/reduce_snapshot.py`), so a field Socrata adds later stays private until someone decides otherwise; dropped custom keys are counted in the reduced manifest, not silently lost. Same private/public split as the row above, now guarded by `test_reduced_snapshot_carries_no_descriptions` and `test_reduced_snapshot_keeps_every_asset`. Rejected: a deny-list of known prose fields (a new prose field would leak). | `docs/SPEC_landscape.md` §Data sources |
| 2026-10-02 | **Weekly snapshots run from cron and the reduced public copy is pushed straight to master** (`scripts/weekly_snapshot.sh`, Fri 08:00 UTC, in its own worktree on origin/master). Failures file a GitHub issue. Rejected: a weekly PR (a merge chore every week, and history is lost while a PR sits unmerged). Owner decision; cron conventions from `server`. [unverifiable] | `TODO.md` M1b |
| 2026-10-02 | **"Real dataset" = Discovery type `dataset` with no parent; series = same category + same name once numbers are replaced; members kept, counts reported both ways** (1421 / 920 on 2026-10-02). Every asset gets one row and a role, so nothing is dropped silently. Rejected: column-signature matching for series (only 23 shared signatures across 54 datasets, it misses most series); "Terms of Use" as a third-party signal (it usually means the City's own terms). Guarded by `test_every_asset_is_one_row_with_a_role`, `test_series_grouped_within_category_not_merged`, `test_city_wording_is_not_a_third_party_signal`. | `docs/SPEC_landscape.md` §Approach |
| 2026-10-02 | **Schema similarity ignores location-only columns** (geometry datatypes, bare lat/long, `location_address/_city/_state/_zip`, Socrata's `:@computed_region_*`); address, ward and neighbourhood columns stay because they are join keys. With them in, schema neighbours of unrelated datasets (Fire Response → drainage assets) were driven by `latitude`/`longitude`/`geometry_point`. Rejected: keeping them and relying on IDF (they are common enough to dominate short schemas but not common enough for IDF to silence). Guarded by `test_location_only_columns_are_not_schema_fields`. | `docs/SPEC_landscape.md` §Approach |
