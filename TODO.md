# TODO

The source of truth for what's left. Read first every session; update in place.

**Format contract** (`tools/todo_archive.py` depends on it): top-level items are
`- [ ]` / `- [x]` lines directly under `## Open work`; `###` sub-headings may
group them; closed items are moved to `docs/TODO_archive.md` by the tool, which
leaves a one-line stub under `## Done`. An open item can be stale — reproduce the
symptom and re-measure the stated cause before acting on it.

## Open work

- [ ] **M1a — Harvest first catalogue snapshot.** Pull data.edmonton.ca catalogue metadata into a dated, gzipped raw snapshot; record which fields actually exist and where (confirm/correct pitfall 3 in `docs/SPEC_landscape.md`, write findings to `data/DATA.md`). Also capture publisher data/metadata-updated timestamps, a fingerprint (row count + column summary) and **per-asset licence**; test whether column top-value lists are capped and which columns have summaries; check Wayback Machine for old `data.json` copies. Done when a snapshot is committed, DATA.md lists the fields, and snapshot size is estimated with a retention rule proposed.
- [ ] **M1b — Start weekly snapshots right after M1a.** Manual pulls until cron exists (ask `server` about cron). An unsnapshotted week is lost change history (spec, Data sources).
- [ ] **M1c — Inventory and de-duplication.** Count assets by type; link derived views to parents; detect yearly series. Every later number depends on this. Make the spec's "real dataset" rule concrete. Done when a table of "real" datasets exists with dropped/merged items flagged, not silently removed.
- [ ] **M2 — Descriptive metrics notebook.** Size, age, claimed update frequency, column counts; test whether per-column summaries (spec pitfall 4) are available.
- [ ] **M3 — Similarity signals and clustering.** Text embeddings and IDF-weighted schema overlap kept separate first; compare with portal categories (ARI/NMI) with bootstrap intervals — categories are a reference, not ground truth. Joinability: normalised names + targeted `distinct` queries on candidate key columns.
- [ ] **Hand-label a ~20-dataset neighbour spot-check** before showing any neighbour output (spec, Outputs).
- [ ] **M4 — Graph and landscape visualisation.**
- [ ] **M5 — Publish** with attribution and unofficial-status note. Blocked on licence wording.
- [ ] **Confirm Open Government Licence – City of Edmonton attribution wording.**
- [ ] **GitHub name-conflict search** for `edmonton-open-data-landscape`.
- [ ] **Pick the reference for "what's missing"** (core question 3): another Socrata city (e.g. Calgary) or a standard expected-datasets list. Cross-city needs a category mapping.
- [ ] **Fill the rest of the CLAUDE.md template placeholders** (domain invariants) once the harvest shows what they are.

## Done
