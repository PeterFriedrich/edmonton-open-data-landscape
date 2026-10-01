# TODO

The source of truth for what's left. Read first every session; update in place.

**Format contract** (`tools/todo_archive.py` depends on it): top-level items are
`- [ ]` / `- [x]` lines directly under `## Open work`; `###` sub-headings may
group them; closed items are moved to `docs/TODO_archive.md` by the tool, which
leaves a one-line stub under `## Done`. An open item can be stale — reproduce the
symptom and re-measure the stated cause before acting on it.

## Open work

- [ ] **M1a — Harvest first catalogue snapshot.** Pull data.edmonton.ca catalogue metadata into a dated, gzipped raw snapshot; record which fields actually exist and where (confirm/correct pitfall 3 in `docs/SPEC_landscape.md`, write findings to `data/DATA.md`). Also capture publisher data/metadata-updated timestamps, a fingerprint (row count + column summary) and **per-asset licence**; test whether column top-value lists are capped and which columns have summaries; check Wayback Machine for old `data.json` copies. Done when a snapshot is committed, DATA.md lists the fields, and snapshot size is estimated with a retention rule proposed.
  - **Probe done 2026-10-01** (4 requests; findings in `data/DATA.md`): 2088 assets; Discovery carries almost every field; views API is needed only for column summaries (row count proxy, min/max, top values capped at 20).
  - **Full harvest waits on the owner**, who is still researching it. Don't run it, or write `src/harvest.py`, until the plan below is approved.
  - **Proposed plan (not approved):** `src/harvest.py`, using stdlib `urllib` so CI deps don't change. (1) Page through Discovery (~21 requests at `limit=100`) and fail hard if the count doesn't match `resultSetSize`. (2) Call `/api/views/{id}.json` only for assets that have columns, to get summaries. Pace at ≤2 req/s, send a User-Agent naming the repo, and use `SOCRATA_APP_TOKEN` if set. Failed ids go in the manifest. (3) Write `data/snapshots/YYYY-MM-DD/{catalog,views}.json.gz` + `manifest.json`, with a `.gitignore` exception for `data/snapshots/`. If one snapshot is >~20 MB, revisit committing it weekly. (4) Offline fixture tests for paging, count mismatch, failures and layout.
- [ ] **M1b — Start weekly snapshots right after M1a.** Manual pulls until cron exists (ask `server` about cron). An unsnapshotted week is lost change history (spec, Data sources).
- [ ] **M1c — Inventory and de-duplication.** Count assets by type; link derived views to parents; detect yearly series. Every later number depends on this. Make the spec's "real dataset" rule concrete. Done when a table of "real" datasets exists with dropped/merged items flagged, not silently removed.
- [ ] **M2 — Descriptive metrics notebook.** Size, age, claimed update frequency, column counts; test whether per-column summaries (spec pitfall 4) are available.
- [ ] **M3 — Similarity signals and clustering.** Text embeddings and IDF-weighted schema overlap kept separate first; compare with portal categories (ARI/NMI) with bootstrap intervals — categories are a reference, not ground truth. Joinability: normalised names + targeted `distinct` queries on candidate key columns.
- [ ] **Hand-label a ~20-dataset neighbour spot-check** before showing any neighbour output (spec, Outputs).
- [ ] **M4 — Graph and landscape visualisation.**
- [ ] **M5 — Publish** with attribution and unofficial-status note. Blocked on licence wording.
- [ ] **Confirm licence and attribution wording.** The probe found most assets say "See Terms of Use" (a few "Canada Open Government Licence", some none), so read the portal's Terms of Use. Also check whether the catalogue metadata itself (titles, descriptions) carries its own licence. Before M5, not before harvesting.
- [ ] **GitHub name-conflict search** for `edmonton-open-data-landscape`.
- [ ] **Pick the reference for "what's missing"** (core question 3): another Socrata city (e.g. Calgary) or a standard expected-datasets list. Cross-city needs a category mapping.
- [ ] **Fill the rest of the CLAUDE.md template placeholders** (domain invariants) once the harvest shows what they are.

## Done
