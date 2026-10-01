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
  - **Proposed plan (not approved), revised after the 2026-10-01 research report:** `src/harvest.py`, using stdlib `urllib` so CI deps don't change. (1) Page through Discovery (~21 requests at `limit=100`) and fail hard if the count doesn't match `resultSetSize`. (2) Call `/api/views/{id}.json` for assets that have columns: all of them on the first run; on weekly runs, only assets whose `data_updated_at`/`metadata_updated_at` changed. Requests go one at a time, about 1 s apart, with the token in `X-App-Token` (`SOCRATA_APP_TOKEN`). Back off on 429 and design for the conservative 1000 requests/hour. The User-Agent names the repo URL, no email. Failed ids go in the manifest. (3) **Storage (owner-decided):** full raw `{catalog,views}.json.gz` + `manifest.json` go to a new **private** GitHub snapshots repo (create it when the harvest is approved). This public repo gets a reduced snapshot with no `top`/`smallest`/`largest`. Guard test: the reduced snapshot contains none of those keys. (4) Offline fixture tests for paging, count mismatch, failures and layout.
- [ ] **M1b — Start weekly snapshots right after M1a.** Manual pulls until cron exists (ask `server` about cron). An unsnapshotted week is lost change history (spec, Data sources).
- [ ] **M1c — Inventory and de-duplication.** Count assets by type; link derived views to parents; detect yearly series. Every later number depends on this. Make the spec's "real dataset" rule concrete. Also classify each asset's **licence** (City / third-party / community view) from `provenance`, category, `Internal or External` and description keywords (`data/DATA.md`). Done when a table of "real" datasets exists with dropped/merged items flagged, not silently removed.
- [ ] **M2 — Descriptive metrics notebook.** Size, age, claimed update frequency, column counts; test whether per-column summaries (spec pitfall 4) are available.
- [ ] **M3 — Similarity signals and clustering.** Text embeddings and IDF-weighted schema overlap kept separate first; compare with portal categories (ARI/NMI) with bootstrap intervals — categories are a reference, not ground truth. Joinability: normalised names + targeted `distinct` queries on candidate key columns.
- [ ] **Hand-label a ~20-dataset neighbour spot-check** before showing any neighbour output (spec, Outputs).
- [ ] **M4 — Graph and landscape visualisation.**
- [ ] **M5 — Publish** with attribution and unofficial-status note. Blocked on licence wording and the City's reply. Checklist (research report, spec Review log): attribution + licence link on every page, the README and notebooks; third-party assets get their own attribution line; non-endorsement disclaimer; no City crest, logo or official-sounding name; no unfiltered top/min/max; short titles plus links to `data.edmonton.ca/d/{id}` rather than full descriptions; mark removed datasets "removed from portal as of [date]".
- [ ] **Confirm licence and attribution wording.** Read the live licence page (`data.edmonton.ca/stories/s/City-of-Edmonton-Open-Data-Terms-of-Use/msh8-if28/`), including its version and whether it still cites FOIP. Also read the portal's Developer, User's Guide and Open City Policy pages, and check whether the January 2016 Terms of Use still apply. Working attribution string and open points: spec, Data sources. Before M5, not before harvesting.
- [ ] **Ask the City (opendata@edmonton.ca)** the report's 5 questions: does the licence cover metadata, attribution string, 2016 terms, public reduced snapshots, rate/contact, disclaimer wording. Draft: `research/edmonton-open-data-landscape/city_opendata_email_draft_2026-10-01.md`. **Owner sends.** Record the sent date here and file the reply next to the draft. Only a written answer counts; silence is not permission.
- [ ] **GitHub name-conflict search** for `edmonton-open-data-landscape`.
- [ ] **Pick the reference for "what's missing"** (core question 3): another Socrata city (e.g. Calgary) or a standard expected-datasets list. Cross-city needs a category mapping.
- [ ] **Fill the rest of the CLAUDE.md template placeholders** (domain invariants) once the harvest shows what they are.

## Done
