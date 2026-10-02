# TODO

The source of truth for what's left. Read first every session; update in place.

**Format contract** (`tools/todo_archive.py` depends on it): top-level items are
`- [ ]` / `- [x]` lines directly under `## Open work`; `###` sub-headings may
group them; closed items are moved to `docs/TODO_archive.md` by the tool, which
leaves a one-line stub under `## Done`. An open item can be stale — reproduce the
symptom and re-measure the stated cause before acting on it.

## Open work

- [ ] **M1b — Start weekly snapshots right after M1a.** First snapshot 2026-10-02; next due ~2026-10-09. Each run: `python -m src.harvest`, then `python -m src.reduce_snapshot data/raw/private-snapshots/<date>`, commit + push in both repos. Manual pulls until cron exists (ask `server` about cron, ~02:00 America/Edmonton). An unsnapshotted week is lost change history (spec, Data sources).
- [ ] **M1c — Inventory and de-duplication.** Count assets by type; link derived views to parents; detect yearly series. Every later number depends on this. Make the spec's "real dataset" rule concrete. Normalise custom-field values first (trailing spaces, synonyms, case: `data/DATA.md`). Check whether the Discovery API leaves out community assets by default (all 2088 harvested were `official`). Also classify each asset's **licence** (City / third-party / community view) from `provenance`, category, `Internal or External` and description keywords (`data/DATA.md`). Done when a table of "real" datasets exists with dropped/merged items flagged, not silently removed.
- [ ] **Decide on the per-asset column-statistics pull** (`/api/views/{id}.json`, one call per asset), before M2. It gets row counts (size, Q4), measured time coverage (min/max, Q1), join-key evidence (distinct counts/top values, Q5) and row-count fingerprints (real change vs refresh, Q6). Without it: column counts only, the claimed "Period of Coverage" text, name-matching joins, timestamp-only change detection. **Cost estimate (exact counts from the 2026-10-02 snapshot):** first pass = **1421 calls** (every dataset; filters inherit their parent's data), ~27 KB each (≈1.6 KB/column × median 17 columns) → ~38 MB raw / ~6–7 MB gzipped. At 1 call per 5 s that's ~2 h, or ~7 nights at 200 a night. Refresh only datasets whose `data_updated_at` changed: a stable set of ~440 (438 moved within 7 days, 450 within 30), so ~440 calls per refresh whatever the cadence → ~23k calls/yr weekly, ~11.5k biweekly, ~5.3k monthly. Collapsing yearly series in M1c doesn't cut calls (each series member has its own rows), but sampling one member per series would.
- [ ] **M2 — Descriptive metrics notebook.** Size, age, claimed update frequency, column counts; test whether per-column summaries (spec pitfall 4) are available.
- [ ] **M3 — Similarity signals and clustering.** Text embeddings and IDF-weighted schema overlap kept separate first; compare with portal categories (ARI/NMI) with bootstrap intervals — categories are a reference, not ground truth. Joinability: normalised names + targeted `distinct` queries on candidate key columns.
- [ ] **Hand-label a ~20-dataset neighbour spot-check** before showing any neighbour output (spec, Outputs).
- [ ] **M4 — Graph and landscape visualisation.**
- [ ] **M5 — Publish** with attribution and unofficial-status note. Blocked on licence wording. Checklist (research report, spec Review log): attribution + licence link on every page, the README and notebooks; third-party assets get their own attribution line; non-endorsement disclaimer; no City crest, logo or official-sounding name; no unfiltered top/min/max; short titles plus links to `data.edmonton.ca/d/{id}` rather than full descriptions; mark removed datasets "removed from portal as of [date]".
- [ ] **Confirm licence and attribution wording.** Read the live licence page (`data.edmonton.ca/stories/s/City-of-Edmonton-Open-Data-Terms-of-Use/msh8-if28/`), including its version and whether it still cites FOIP. Also read the portal's Developer, User's Guide and Open City Policy pages, and check whether the January 2016 Terms of Use still apply. Working attribution string and open points: spec, Data sources. Before M5, not before harvesting.
- [ ] **Optional, before M5: ask the City (opendata@edmonton.ca).** Not needed while uncertain material (column summaries, descriptions) stays in the private repo. Read the live licence page first; it may answer questions 1–2 without asking. Draft with 5 questions: `research/edmonton-open-data-landscape/city_opendata_email_draft_2026-10-01.md`. **Owner sends.** If you do send it, record the date here and file the reply next to the draft. Only a written answer counts.
- [ ] **GitHub name-conflict search** for `edmonton-open-data-landscape`.
- [ ] **Pick the reference for "what's missing"** (core question 3): another Socrata city (e.g. Calgary) or a standard expected-datasets list. Cross-city needs a category mapping.
- [ ] **Fill the rest of the CLAUDE.md template placeholders** (domain invariants) once the harvest shows what they are.

## Done

Closed items moved out of `## Open work` live in **`docs/TODO_archive.md`** — one line each below, reasoning there.

- [x] **M1a — Harvest first catalogue snapshot (metadata only).** — CLOSED 2026-10-02 · `docs/TODO_archive.md`
