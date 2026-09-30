# TODO

The source of truth for what's left. Read first every session; update in place.

**Format contract** (`tools/todo_archive.py` depends on it): top-level items are
`- [ ]` / `- [x]` lines directly under `## Open work`; `###` sub-headings may
group them; closed items are moved to `docs/TODO_archive.md` by the tool, which
leaves a one-line stub under `## Done`. An open item can be stale — reproduce the
symptom and re-measure the stated cause before acting on it.

## Open work

- [ ] **M1a — Harvest first catalogue snapshot.** Pull data.edmonton.ca catalogue metadata into a dated, gzipped raw snapshot; record which fields actually exist and where (confirm/correct pitfall 3 in `docs/SPEC_landscape.md`, write findings to `data/DATA.md`). Done when a snapshot is committed and DATA.md lists the fields.
- [ ] **M1b — Inventory and de-duplication.** Count assets by type; link derived views to parents; detect yearly series. Every later number depends on this. Done when a table of "real" datasets exists with dropped/merged items flagged, not silently removed.
- [ ] **M2 — Descriptive metrics notebook.** Size, age, claimed update frequency, column counts; test whether per-column summaries (spec pitfall 4) are available.
- [ ] **M3 — Similarity signals and clustering.** Text embeddings and IDF-weighted schema overlap kept separate first; compare with portal categories (ARI/NMI).
- [ ] **M4 — Graph and landscape visualisation.**
- [ ] **M5 — Scheduled weekly snapshots** for change tracking (ask `server` about cron).
- [ ] **M6 — Publish** with attribution and unofficial-status note. Blocked on licence wording.
- [ ] **Confirm Open Government Licence – City of Edmonton attribution wording.**
- [ ] **GitHub name-conflict search** for `edmonton-open-data-landscape`.
- [ ] **Pick the reference for "what's missing"** (core question 3): another Socrata city (e.g. Calgary) or a standard expected-datasets list.
- [ ] **Fill the rest of the CLAUDE.md template placeholders** (domain invariants) once the harvest shows what they are.

## Done
