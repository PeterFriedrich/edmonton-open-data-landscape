# SPEC — Edmonton Open Data Landscape

Starter spec, 2026-09-30. Candidates to test, not commitments — nothing here is
locked until it has a row in `docs/DECISIONS.md`.

## Purpose

Map the structure of Edmonton's open data catalogue as a whole, so datasets can
be explored by how they relate to each other rather than one at a time.

- **In scope:** similarity between datasets, metrics across the catalogue, and
  the meta-structure (clusters, gaps, links).
- **Non-goal:** replicating the City's own per-dataset exploration tools (e.g.
  311 Explorer, the portal's built-in previews).

## Core questions

1. Which datasets are most alike, and by what measure (topic, schema, geography,
   time coverage)?
2. What clusters emerge, and how do they compare with the portal's own categories?
3. Where is the catalogue dense or sparse, and what looks missing?
   *Needs an external reference — see pitfall 7.*
4. How are size, update frequency, age and column counts distributed?
5. Which datasets share fields or keys, and so could be joined?
6. How does the catalogue change over time (additions, removals, updates)?

## Data sources

data.edmonton.ca (Socrata): SODA API plus catalogue metadata.

- **Pull:** name, description, category, tags, column names and types, row
  counts, update frequency, created/updated dates, licence **per asset** (some
  may not fall under the City licence — matters for publishing).
- **Snapshots:** store each harvest with its date. The catalogue API keeps no
  history, so an unsnapshotted week is lost for good — snapshots start right
  after the first harvest (manual weekly pulls until cron exists), not after
  the analysis milestones. Each snapshot records the publisher's own
  data-updated and metadata-updated timestamps plus a cheap fingerprint (row
  count + column summary), so a real change can be told from an automated
  refresh that only bumps the timestamp. After the first pull, estimate
  snapshot size and set a retention rule.
  *Owner, 2026-10-02:* snapshots start **metadata only** (Discovery listing,
  ~21 requests). Until the per-asset statistics pull is decided (`TODO.md`),
  the fingerprint is timestamps + a hash of the column list + the
  `Automated or Manual` field, with no row count.
- **Snapshot storage (owner, 2026-10-01):** full raw snapshots go to a
  **private** GitHub repo. This repo is public, so it gets only *reduced*
  snapshots (ids, titles, categories, tags, column names/types, counts, dates,
  licence class; no `cachedContents.top`/`smallest`/`largest`, and no dataset
  or column descriptions) and derived outputs. Reasons: column summaries can
  hold personal names and addresses (e.g. Business Licences), which the
  licence does not cover; and whether the licence covers the catalogue's own
  prose is unclear (owner, 2026-10-02: keep anything uncertain private).
- **Privacy:** never publish per-column top values or min/max unless the column
  is on an allow-list of clearly non-personal columns (ward, category codes).
- **Backfill:** check whether the Wayback Machine holds old copies of
  `data.edmonton.ca/data.json`; if so, they partly recover pre-project history.
- **Attribution:** the licence field says "See Terms of Use" on most assets
  (88 of 100 in the probe). That page is the Open Government Licence – City of
  Edmonton (an Alberta OGL variant, July 2022 per OSM sources, not yet read
  live). Working string, still to confirm: "Contains information licensed under
  the Open Government Licence – City of Edmonton." Third-party assets (e.g.
  OGL–Alberta, OGL–Canada, Environment Canada) carry their own terms, often
  only in the description, so classify each asset's licence before publishing.
  Whether catalogue metadata itself is licensed "Information" is unconfirmed;
  unconfirmed; reading the live licence page comes first, then optionally
  asking the City (`TODO.md`).
- **Status:** unofficial; built on City of Edmonton open data, not affiliated
  with the City.

## Harvest pitfalls (from spec review — confirm in milestone 1)

Based on general Socrata knowledge. Pitfalls 1, 3 and 4 were partly checked by
the 2026-10-01 probe (`data/DATA.md` has the field table); the rest are unchecked.

1. **Catalogue ≠ datasets.** Filtered views, maps, charts, stories and external
   links sit alongside the datasets they come from. Derived views share their
   parent's columns and description, so they would dominate nearest-neighbour
   results. Filter by asset type and link each view to its parent before any
   similarity work. *Probe:* the Discovery API's `parent_fxf` gives the parent
   (37 of the first 100 assets have one). Maps carry no columns of their own.
   **Community views** (user-created, `provenance` ≠ `official`) carry
   user-edited titles and descriptions that the City hasn't reviewed. Keep
   them apart from official assets.
2. **Yearly series** ("Property Assessment 2019 / 2020 / …") form trivial tight
   clusters. Collapse to one entry per series, or flag them.
3. **Field locations.** *Probe confirmed:* the Discovery API
   (`api.us.socrata.com/api/catalog/v1`) carries name, description, category,
   tags, columns, data/metadata-updated dates, licence, parent link and custom
   fields, but not row counts. `/api/views/{id}.json` has no row-count field
   either; a column summary's `count` stands in for one (SODA `count(*)` to
   check). "Update frequency" is a publisher-entered custom field: treat it as
   *claimed*. The same custom fields also give `Period of Coverage` (free text)
   and `Automated or Manual`. Measure *actual* frequency from the publisher timestamps recorded
   in each snapshot (weekly diffs alone can't resolve sub-weekly updates),
   checked against the fingerprint.
4. **Column summaries as a middle ground — for coverage, not keys.** The views
   API often exposes per-column summaries (null counts, min/max, top values).
   Min/max gives time coverage without rows. Top values are capped to a short
   list (*probe: capped at 20*, and not every column has a summary), so they
   can't show overlap on high-cardinality keys (IDs, addresses,
   permit numbers). Join-key overlap needs **targeted row access on candidate
   key columns only**: SODA `select distinct` / `count(distinct)` — cheap for
   low-cardinality keys like neighbourhood (~400) or ward (12).
5. **Generic column names** (`id`, `latitude`, `longitude`, `location`, `year`)
   swamp schema similarity. Weight rare columns up (IDF-style). A shared name is
   not a shared key, and a real key often appears under different names
   (`neighbourhood` vs `neighbourhood_name`). Normalise names, then decide on
   value overlap (pitfall 4) — this guards both false joins and missed ones.
   Embedding column descriptions is the fallback.
6. **Geographic coverage** is rarely in the metadata and almost everything is
   city-wide. Infer the spatial unit from columns (point, polygon, neighbourhood,
   ward) instead — that is what decides joinability anyway.
7. **"What's missing" needs a reference**: another city's catalogue (Calgary also
   runs Socrata) or a standard list of expected municipal datasets. So the
   city-comparison work is a dependency of core question 3, not a side project.
8. **Small n.** Likely hundreds to low thousands of real datasets once views are
   removed. A small local embedding model runs fine on the ARM CPU; cluster
   quality metrics will be noisy, so agreement with portal categories (ARI/NMI)
   is the more honest measure than silhouette. The categories are a coarse,
   noisy **reference, not ground truth** (some assets may be uncategorised):
   report bootstrap intervals, and treat the disagreements as the finding.

## Approach

Metadata first; row-level access only where a question can't be answered
without it (join-key overlap, pitfall 4). Build several similarity signals,
then combine and compare them.

**"Real dataset"** = an official (`provenance`), top-level tabular or
geospatial asset that is not a derived view of another asset; series members are grouped under one series id.
M1c makes the exact rule concrete and flags everything it excludes.

1. Text similarity: embed titles, descriptions and tags.
2. Schema similarity: IDF-weighted overlap in column names and types.
3. Operational metrics: size, claimed vs. measured update frequency, age,
   column counts.
4. Coverage: time extent from date-column min/max; spatial unit from columns.
5. Structure: cluster on the signals, build a graph (datasets as nodes,
   similarity or shared fields as edges), compare with portal categories.

## Outputs

- **Landscape view:** 2D map of all datasets, coloured by cluster.
- **Graph view:** datasets linked by similarity or shared fields.
- **Metrics view:** distributions of size, freshness, age, schema width.
- **Neighbours:** closest relatives of any dataset — a lookup into the
  landscape, not a replacement for the City's tools. Success check: a
  hand-labelled sample of ~20 datasets with their expected neighbours,
  scored before any neighbour output is shown.
- **Change log:** added / removed / updated between snapshots.

Notebooks first; a shareable static site later. Keep outputs as data files so a
site can read them.

## Scope and naming

- Name `edmonton-open-data-landscape`: no conflicts on PyPI, npm or web search;
  GitHub name search still to do.
- Edmonton only for now. City comparison expected to stay small; if it grows,
  split into its own project rather than renaming this one. Any cross-city
  comparison needs a category mapping — Calgary's categories won't match
  Edmonton's.

## Tech stack

Python; requests (Socrata), pandas, scikit-learn, a sentence-embedding model,
networkx. Storage: dated snapshot files (gzipped JSON raw, Parquet derived).
Front end undecided; notebooks first.

## Milestones

1a. Harvest a first catalogue metadata snapshot (with timestamps, fingerprint,
    per-asset licence).
1b. Start weekly snapshots — manual until cron exists. Moved up from last-but-one:
    change history can't be recovered later.
1c. Inventory by asset type; parent/derived and series de-duplication.
2. Descriptive metrics and an exploratory notebook.
3. Similarity signals and clustering (incl. targeted key-column row access).
4. Graph and landscape visualisation.
5. Publish, with attribution and an unofficial-status note.

## Open questions (with proposed answers — not locked)

| Question | Proposal |
|---|---|
| Metadata only, or sample rows? | Metadata + column summaries for coverage; targeted `distinct` queries on candidate key columns for joinability (pitfall 4). No general row sampling. |
| Text vs. schema similarity, or weighted? | Keep separate first; report where they disagree (same topic/different schema and vice versa) — that is a finding. Weight later. |
| Snapshot cadence? | Weekly from M1b. Full raw snapshots go to a private repo; this public repo gets reduced snapshots (see Data sources). Weekly is enough because publisher timestamps are recorded (pitfall 3). Revisit size/retention after the first pull. |
| Notebooks or static site? | Notebooks through milestone 4; outputs as data files. |
| Where does city comparison live, when does it split? | Minimal reference catalogue here for core question 3; split if it grows past that. |
| Licence wording? | Working string in Data sources. Confirm on the live licence page before publishing; optionally ask the City (email drafted 2026-10-01). |
| GitHub name conflicts? | To check. |

## Review log

Responses to outside reviews, so settled points don't come back.

**2026-10-01, Claude web review 1.** Accepted: snapshots moved to M1b;
publisher timestamps per snapshot; pitfall 4 narrowed to coverage, key overlap
via targeted row access; name-variant keys; categories as reference with
bootstrap intervals; neighbour spot-check; per-asset licence; snapshot
size/retention; cross-city category mapping. Adjusted:
- Key overlap isn't uniformly hard — low-cardinality keys (neighbourhood, ward)
  are one cheap `distinct` query each; only high-cardinality keys need care.
- Publisher timestamps alone can over-count updates (automated refresh bumps
  them without content change), hence the fingerprint.
- Proposed DECISIONS rows not added: neither is locked yet, and one lacked a
  test or `[unverifiable]` tag. Both live here as spec revisions.
Added: Wayback Machine backfill check for `data.json`.

**2026-10-01, Claude web reply on probe licensing**
(`research/edmonton-open-data-landscape/harvest_licence_reply_2026-10-01.md`).
Accepted: a 4-request probe is fine; the licence binds at publishing, not
harvesting; record the licence text from the probe; pace requests, send a
User-Agent, use an app token if rate-limited; read the portal's Terms of Use
before publishing. Adjusted: the reply assumed the City licence, but the probe
found "See Terms of Use" on most assets, so the Terms of Use is the main
document to read. The reply also called publishing M6; it is M5.

**2026-10-01, Claude web research report on licence, harvest and publishing**
(`research/edmonton-open-data-landscape/licence_harvest_publish_reply_2026-10-01.md`). Accepted: the licence is the Alberta-template OGL – City of Edmonton
behind "See Terms of Use"; working attribution string; non-endorsement
disclaimer, no City branding; per-asset licence classes (City / third-party /
community view); provenance filter; suppress top/min/max in anything
published; full raw snapshots in a private repo with reduced public ones
(owner decision); `X-App-Token`, about 1 request/s, back off on 429; email the
City with the report's 5 questions (drafted, owner sends); show short titles
plus links rather than full descriptions; record the licence version in force
per snapshot. Adjusted:
- The User-Agent names the repo URL, not an email address (owner).
- "Fetch views only for changed assets" applies to weekly runs; the first
  harvest fetches all assets that have columns.
- Neither the licence text nor the attribution string has been checked
  against the live page. Both stay "to confirm".
